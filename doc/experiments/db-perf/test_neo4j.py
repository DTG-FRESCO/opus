#! /usr/local/bin/python2.7
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from neo4j.v1 import GraphDatabase

import timer

track = timer.track("neo4j")

session = None

# Cache for latest file and process
cache = {}
cache['FILE'] = {}
cache['PROCESS'] = {}


def get_cached_data(cache_type, key):
    if key not in cache[cache_type]:
        return None
    else:
        return cache[cache_type][key]


def update_cached_data(cache_type, key, value):
    cache[cache_type][key] = value


class MsgFields(object):
    MSG_TYPE = 1

    # Optional fields
    FUNC_NAME = 2
    FILE_NAME = 3
    FILE_DESC = 4
    PID = 5
    FILE_MODE = 6


class EdgeStatus(object):
    NONE = 0
    CoT = 1
    READ = 2
    WRITE = 3
    RaW = 4
    CLOSED = 5
    DELETED = 6
    BIN = 7
    CoE = 8
    CLOEXEC = 9
    INACTIVE = 10


# Functions called from handle_msg and within a txn
def get_status_from_mode(mode):
    if mode == "r":
        return EdgeStatus.READ
    elif mode == "w":
        return EdgeStatus.WRITE
    elif mode == "rw":
        return EdgeStatus.RaW


def query(t, query, params):
    res = t.run(query, params)
    for result in res:
        return tuple(result[key] for key in res.keys())


@track
def version_local(t, old_loc_node, prev_glob_node, glob_node, proc_node):
    new_local, = query(t,
                       "MATCH (old_loc), (old_glob), (new_glob), (proc) "
                       "WHERE id(old_loc) = {old_loc_id} "
                       "  AND id(old_glob) = {old_glob_id} "
                       "  AND id(new_glob) = {new_glob_id} "
                       "  AND id(proc) = {proc_id} "
                       "MATCH (old_glob)-[old_glob_loc]->(old_loc) "
                       "MATCH (old_loc)-[old_loc_proc]->(proc) "
                       "CREATE (new_loc:LOCAL {name: old_loc.name}) "
                       "CREATE (new_glob)-[:GLOB_LOC "
                       "                   {status: old_glob_loc.status} "
                       "                   ]->(new_loc) "
                       "CREATE (new_loc)-[:LOC_PREV "
                       "                  {status: {status_none}}]->(old_loc) "
                       "CREATE (new_loc)-[:LOC_PROC "
                       "                  {status: {status_none}}]->(proc) "
                       "SET old_loc_proc.status = {status_inactive} "
                       "RETURN id(new_loc)",
                       {"old_loc_id": old_loc_node,
                        "old_glob_id": prev_glob_node,
                        "new_glob_id": glob_node,
                        "proc_id": proc_node,
                        "status_none": EdgeStatus.NONE,
                        "status_inactive": EdgeStatus.INACTIVE})
    return new_local


@track
def create_new_global(t, proc_node, prev_glob_node):
    new_glob, = query(t,
                      "MATCH (old_glob) "
                      "WHERE id(old_glob) = {old_glob_id} "
                      "CREATE (new_glob:GLOBAL {name: old_glob.name}) "
                      "CREATE (new_glob)-[:GLOB_PREV "
                      "                   {status: {status_none}}]->(old_glob) "
                      "RETURN id(new_glob)",
                      {"old_glob_id": prev_glob_node,
                       "status_none": EdgeStatus.NONE})
    return new_glob


@track
def version_global(t, proc_node, prev_glob_node):
    new_glob = create_new_global(t, proc_node, prev_glob_node)


    res = t.run("MATCH (old_glob)-[:GLOB_LOC]->(l) "
                "WHERE id(old_glob) = {old_glob_id} "
                "RETURN id(l) AS local",
                {"old_glob_id": prev_glob_node})
    
    new_local = None

    for result in res:
        new_local = version_local(t,
                                  result['local'],
                                  prev_glob_node,
                                  new_glob,
                                  proc_node)
    return new_glob, new_local


@track
def get_l(t, proc_node, fd):
    local, = query(t,
                   "MATCH (proc) "
                   "WHERE id(proc) = {proc_id} "
                   "CREATE (loc:LOCAL {name: {name}}) "
                   "CREATE (loc)-[:LOC_PROC {status: {status_none}}]->(proc) "
                   "RETURN id(loc)",
                   {"proc_id": proc_node,
                    "name": fd,
                    "status_none": EdgeStatus.NONE})
    return local


@track
def get_g(t, proc, loc, file_name):

    glob = None
    prev_glob = get_cached_data("FILE", file_name)

    if prev_glob is None:
        glob, = query(t,
                      "CREATE (global:GLOBAL {name:{name}}) "
                      "RETURN id(global)",
                      {"name": file_name})
    else:
        glob, _ = version_global(t, proc, prev_glob)

    update_cached_data("FILE", file_name, glob)

    # Bind local to global
    t.run("MATCH (global), (local) "
          "WHERE id(global) = {global} "
          "  AND id(local) = {local} "
          "CREATE (global)-[:GLOB_LOC {status: {status_none}}]->(local) ",
          {"global": glob,
           "local": loc,
           "status_none": EdgeStatus.NONE})
    return glob


@track
def drop_g(t, proc, loc, glob):
    new_glob, new_loc = version_global(t, proc, glob)
    t.run("MATCH (new_global)-[r:GLOB_LOC]->(local) "
          "WHERE id(local) = {local} "
          "  AND id(new_global) = {new_global} "
          "DELETE r",
          {"local": new_loc,
           "new_global": new_glob}).consume()

    return new_glob, new_loc


@track
def drop_l(t, proc, loc):
    t.run("MATCH (proc), (loc) "
          "WHERE id(proc) = {proc} "
          "  AND id(loc) = {loc} "
          "MATCH (loc)-[r:LOC_PROC]->(proc) "
          "SET r.status = {status_closed}",
          {"proc": proc,
           "loc": loc,
           "status_closed": EdgeStatus.CLOSED})


@track
def handle_process_start(t, pid, bin_name):
    proc, = query(t,
                  "CREATE (proc:PROC {name: {name}}) "
                  "RETURN id(proc)",
                  {"name": pid})
    loc = get_l(t, proc, "omega")
    glob = get_g(t, proc, loc, bin_name)

    t.run("MATCH (local), (global) "
          "WHERE id(local) = {local} "
          "  AND id(global) = {global} "
          "MATCH (global)-[r:GLOB_LOC]->(local) "
          "SET r.status = {status_bin}",
          {"local": loc,
           "global": glob,
           "status_bin": EdgeStatus.BIN})

    new_glob, new_loc = drop_g(t, proc, loc, glob)
    drop_l(t, proc, new_loc)

    update_cached_data("PROCESS", pid, proc)


@track
def handle_file_open(t, proc, file_name, fd, mode):
    loc = get_l(t, proc, fd)
    glob = get_g(t, proc, loc, file_name)

    t.run("MATCH (local), (global) "
          "WHERE id(local) = {local} "
          "  AND id(global) = {global} "
          "MATCH (global)-[r:GLOB_LOC]->(local) "
          "SET r.status = {status}",
          {"local": loc,
           "global": glob,
           "status": get_status_from_mode(mode)})


@track
def local_by_name(t, proc, name):
    return query(t,
                 "MATCH (local)-[r:LOC_PROC]->(proc) "
                 "WHERE local.name = {fd} "
                 "  AND id(proc) = {proc} "
                 "  AND NOT r.status IN {edge_status} "
                 "OPTIONAL MATCH (global)-[s:GLOB_LOC]->(local) "
                 "RETURN id(local), id(global)",
                 {"fd": name,
                  "proc": proc,
                  "edge_status": [EdgeStatus.CLOSED,
                                  EdgeStatus.INACTIVE]})


@track
def handle_file_close(t, proc, fd):
    loc, glob = local_by_name(t, proc, fd)
    if glob is not None:
        # Drop global
        new_glob, new_loc = drop_g(t, proc, loc, glob)

        # Drop local
        drop_l(t, proc, new_loc)


@track
def handle_file_touch(t, proc, file_name):
    loc, = get_l(t, proc, "omega")
    glob = get_g(t, proc, loc, file_name)
    _, new_loc = drop_g(t, proc, loc, glob)
    drop_l(t, proc, new_loc)


@track
def process_msg(msg):
    # TODO: Test out a workflow extraction query

    t = session.begin_transaction()
    if msg[MsgFields.MSG_TYPE] == "PROCESS_START":
        handle_process_start(t,
                             msg[MsgFields.PID], msg[MsgFields.FILE_NAME])
    elif msg[MsgFields.MSG_TYPE] == "FUNC_MSG":
        func_name = msg[MsgFields.FUNC_NAME]
        proc_node = get_cached_data("PROCESS", msg[MsgFields.PID])
        if func_name == "open":
            handle_file_open(t,
                             proc_node,
                             msg[MsgFields.FILE_NAME],
                             msg[MsgFields.FILE_DESC],
                             msg[MsgFields.FILE_MODE])
        elif func_name == "close":
            handle_file_close(t, proc_node, msg[MsgFields.FILE_DESC])
        elif func_name == "stat":
            handle_file_touch(t, proc_node, msg[MsgFields.FILE_NAME])
    else:
        print("Error!! Invalid message")
    t.commit()


def setup():
    global session
    drive = GraphDatabase.driver("bolt://localhost")
    session = drive.session()


def teardown():
    session.run("MATCH ()-[r]-() DELETE r")
    session.run("MATCH (n) DELETE n")
    session.close()
