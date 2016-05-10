#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os

from peewee import (SqliteDatabase, Model,
                    CharField, IntegerField, ForeignKeyField)
import timer

db = SqliteDatabase("testexample.db")

track = timer.track("sql")

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


class NodeTypes(object):
    FILE = 1
    PROCESS = 2
    LOCAL = 3


class EdgeTypes(object):
    LOC_PROC_REL = 1
    GLOB_LOC_REL = 2
    GLOB_PREV_REL = 3
    LOC_PREV_REL = 4


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


class BaseModel(Model):
    class Meta:
        database = db


class Nodes(BaseModel):
    name = CharField(index=True)
    node_type = IntegerField()


class Edges(BaseModel):
    start_id = ForeignKeyField(Nodes, related_name='source')
    end_id = ForeignKeyField(Nodes, related_name='dest')
    edge_type = IntegerField()
    edge_status = IntegerField()

    class Meta:
        indexes = ((('start_id', 'end_id'), True),)


# Functions called from handle_msg and within a txn
def get_status_from_mode(mode):
    if mode == "r":
        return EdgeStatus.READ
    elif mode == "w":
        return EdgeStatus.WRITE
    elif mode == "rw":
        return EdgeStatus.RaW


@track
def version_local(old_loc_node, prev_glob_node, glob_node, proc_node):
    # Create a new local node and copy over details from old_loc_node
    new_loc_node = Nodes.create(name=old_loc_node.name,
                                node_type=NodeTypes.LOCAL)

    # Copy over local global link state to the new link
    old_glob_loc_rel = Edges.get(Edges.start_id == prev_glob_node.id,
                                 Edges.end_id == old_loc_node.id)

    # Create a link from glob_node to new local node
    Edges.create(start_id=glob_node.get_id(),
                 end_id=new_loc_node.get_id(),
                 edge_type=EdgeTypes.GLOB_PREV_REL,
                 edge_status=old_glob_loc_rel.edge_status)

    # Create link from new local node to previous local node
    Edges.create(start_id=new_loc_node.get_id(),
                 end_id=old_loc_node.get_id(),
                 edge_type=EdgeTypes.LOC_PREV_REL,
                 edge_status=EdgeStatus.NONE)

    # Create new link from new local node to process node
    Edges.create(start_id=new_loc_node.get_id(),
                 end_id=proc_node.get_id(),
                 edge_type=EdgeTypes.LOC_PROC_REL,
                 edge_status=EdgeStatus.NONE)

    # Mark old link from local to process as inactive
    old_loc_proc_rel = Edges.get(Edges.start_id == old_loc_node.id,
                                 Edges.end_id == proc_node.id)
    old_loc_proc_rel.edge_status = EdgeStatus.INACTIVE
    old_loc_proc_rel.save()

    return new_loc_node


@track
def version_global(proc_node, prev_glob_node, track_loc_name=None):
    local_to_return = None
    file_name = prev_glob_node.name
    new_glob_node = Nodes.create(name=file_name, node_type=NodeTypes.FILE)

    Edges.create(start_id=new_glob_node.get_id(),
                 end_id=prev_glob_node.get_id(),
                 edge_type=EdgeTypes.GLOB_PREV_REL,
                 edge_status=EdgeStatus.NONE)

    # Get locals connected to prev_glob_node and version them

    query = "select n.* from nodes n, edges e where n.id = e.end_id_id "
    query += "and e.start_id_id = ? "
    query += "and n.node_type = ? "
    query += "and e.edge_type = ?"
    loc_nodes = Nodes.raw(query,
                          prev_glob_node.id,
                          NodeTypes.LOCAL,
                          EdgeTypes.GLOB_LOC_REL)
    for loc_node in loc_nodes:
        new_loc_node = version_local(loc_node,
                                     prev_glob_node,
                                     new_glob_node,
                                     proc_node)
        if track_loc_name is not None and track_loc_name == new_loc_node.name:
            local_to_return = new_loc_node

    return new_glob_node, local_to_return


@track
def get_l(proc_node, fd):
    loc_node = Nodes.create(name=fd, node_type=NodeTypes.LOCAL)
    loc_proc_rel = Edges.create(start_id=loc_node.get_id(),
                                end_id=proc_node.get_id(),
                                edge_type=EdgeTypes.LOC_PROC_REL,
                                edge_status=EdgeStatus.NONE)

    # TODO: Update process cache with local node and local process link
    return loc_node, loc_proc_rel


@track
def get_g(proc_node, loc_node, file_name):

    glob_node = None
    prev_glob_id = get_cached_data("FILE", file_name)

    if prev_glob_id is None:
        glob_node = Nodes.create(name=file_name, node_type=NodeTypes.FILE)
    else:
        prev_glob_node = Nodes.get(Nodes.id == prev_glob_id)
        glob_node, _ = version_global(proc_node, prev_glob_node)

    update_cached_data("FILE", file_name, glob_node.get_id())

    # Bind local to global
    glob_loc_rel = Edges.create(start_id=glob_node.get_id(),
                                end_id=loc_node.get_id(),
                                edge_type=EdgeTypes.GLOB_LOC_REL,
                                edge_status=EdgeStatus.NONE)
    return glob_node, glob_loc_rel


@track
def drop_g(proc_node, loc_node, glob_node):
    new_glob_node, new_loc_node = version_global(proc_node,
                                                 glob_node,
                                                 loc_node.name)

    del_qry = Edges.delete().where(Edges.start_id == new_glob_node.id,
                                   Edges.end_id == new_loc_node.id)
    del_qry.execute()

    return new_glob_node, new_loc_node


@track
def drop_l(proc_node, loc_node):
    upd_qry = Edges.update(edge_status=EdgeStatus.CLOSED
                           ).where(Edges.start_id == loc_node.id,
                                   Edges.end_id == proc_node.id)
    upd_qry.execute()


@track
def handle_process_start(pid, bin_name):
    proc_node = Nodes.create(name=pid, node_type=NodeTypes.PROCESS)

    loc_node, loc_proc_rel = get_l(proc_node, "omega")
    glob_node, glob_loc_rel = get_g(proc_node, loc_node, bin_name)
    glob_loc_rel.edge_status = EdgeStatus.BIN
    glob_loc_rel.save()

    new_glob_node, new_loc_node = drop_g(proc_node, loc_node, glob_node)
    drop_l(proc_node, new_loc_node)

    update_cached_data("PROCESS", pid, proc_node)


@track
def handle_file_open(proc_node, file_name, fd, mode):
    loc_node, loc_proc_rel = get_l(proc_node, fd)
    glob_node, glob_loc_rel = get_g(proc_node, loc_node, file_name)

    glob_loc_rel.edge_status = get_status_from_mode(mode)
    glob_loc_rel.save()


@track
def handle_file_close(proc_node, fd):

    # Get local from process
    query = "select n.* from nodes n, edges e "
    query += "where n.name = ? "
    query += "and n.id = e.start_id_id "
    query += "and e.end_id_id = ? "
    query += "and e.edge_status not in (?, ?) "
    query += "and e.edge_type = ? "
    query += "and n.node_type = ?"
    loc_nodes = Nodes.raw(query, fd, proc_node.id,
                          EdgeStatus.CLOSED, EdgeStatus.INACTIVE,
                          EdgeTypes.LOC_PROC_REL, NodeTypes.LOCAL)

    loc_node = None
    for ln in loc_nodes:
        loc_node = ln
        break

    # Get global from local
    query = "select n.* from nodes n, edges e "
    query += "where e.end_id_id = ? "
    query += "and n.node_type = ? "
    query += "and n.id = e.start_id_id"

    glob_nodes = Nodes.raw(query, loc_node.id, NodeTypes.FILE)

    glob_node = None
    for gn in glob_nodes:
        glob_node = gn
        break

    if glob_node is not None:
        # Drop global
        new_glob_node, new_loc_node = drop_g(proc_node, loc_node, glob_node)

        # Drop local
        drop_l(proc_node, new_loc_node)


@track
def handle_file_touch(proc_node, file_name):
    loc_node, loc_proc_rel = get_l(proc_node, "omega")
    glob_node, glob_loc_rel = get_g(proc_node, loc_node, file_name)
    _, new_loc_node = drop_g(proc_node, loc_node, glob_node)
    drop_l(proc_node, new_loc_node)


@track
def process_msg(msg):
    # TODO: Test out a workflow extraction query

    func_name = None
    with db.transaction():
        if msg[MsgFields.MSG_TYPE] == "PROCESS_START":
            handle_process_start(msg[MsgFields.PID], msg[MsgFields.FILE_NAME])
        elif msg[MsgFields.MSG_TYPE] == "FUNC_MSG":
            func_name = msg[MsgFields.FUNC_NAME]
            if func_name == "open":
                proc_node = get_cached_data("PROCESS", msg[MsgFields.PID])
                handle_file_open(proc_node, msg[MsgFields.FILE_NAME],
                                 msg[MsgFields.FILE_DESC],
                                 msg[MsgFields.FILE_MODE])
            elif func_name == "close":
                proc_node = get_cached_data("PROCESS", msg[MsgFields.PID])
                handle_file_close(proc_node, msg[MsgFields.FILE_DESC])
            elif func_name == "stat":
                proc_node = get_cached_data("PROCESS", msg[MsgFields.PID])
                handle_file_touch(proc_node, msg[MsgFields.FILE_NAME])
        else:
            print("Error!! Invalid message")


def setup():
    db.connect()
#    db.execute_sql('PRAGMA synchronous=OFF')
#    db.execute_sql('PRAGMA journal_mode=MEMORY')
    db.create_tables([Nodes, Edges])


def teardown():
    db.close()
    os.unlink("testexample.db")
