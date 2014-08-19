# -*- coding: utf-8 -*-
'''
The traversal module contains procedures for traversing the graph.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
from opus import storage


def get_latest_glob_version(db_iface, name):
    '''Gets the latest global version for the given name'''
    node = None

    result = db_iface.query("START n=node:FILE_INDEX('name:\"" + name + "\"') "
                            "RETURN n ORDER BY n.node_id DESC LIMIT 1")
    for row in result:
        node = row['n']
    return node


def is_glob_deleted(glob_node):
    '''Returns true if the global node has been deleted'''
    ret = False
    for rel in glob_node.relationships.outgoing:
        if rel['state'] == storage.LinkState.DELETED:
            ret = True
    return ret


@storage.CacheManager.dec(storage.CACHE_NAMES.LOCAL_GLOBAL,
                          lambda loc_node: loc_node.id)
def get_globals_from_local(db_iface, loc_node):
    '''Gets the global object nodes and relationship list
    associated with the local object node'''
    glob_node_link_list = []

    rows = db_iface.query("START loc_node=node({id}) "
                          "MATCH loc_node<-[rel:LOC_OBJ]-glob_node "
                          "RETURN glob_node, rel", id=loc_node.id)
    for row in rows:
        glob_node = row['glob_node']
        rel = row['rel']
        glob_node_link_list.append((glob_node, rel))
    return glob_node_link_list


def get_locals_from_global(db_iface, glob_node):
    '''Gets all local object nodes and the relationship
    links connected to the given global'''
    loc_node_link_list = []

    rows = db_iface.query("START glob_node=node({id}) "
                          "MATCH glob_node-[rel:LOC_OBJ]->loc_node "
                          "RETURN loc_node, rel", id=glob_node.id)
    for row in rows:
        loc_node = row['loc_node']
        rel = row['rel']
        loc_node_link_list.append((loc_node, rel))
    return loc_node_link_list


def get_process_from_local(db_iface, loc_node):
    '''Gets the process node and relationship link
    from the local obj'''
    proc_node = None
    rel = None

    rows = db_iface.query("START loc_node=node({id}) "
                          "MATCH loc_node-[rel:PROC_OBJ]->proc_node "
                          "WHERE rel.state <> {state} "
                          "RETURN proc_node, rel",
                          id=loc_node.id, state=storage.LinkState.CoT)
    for row in rows:
        proc_node = row['proc_node']
        rel = row['rel']
    return proc_node, rel


def get_locals_from_process(db_iface, proc_node):
    '''Returns all local object nodes and its links for the
    given process object node'''
    loc_node_link_list = []

    rows = db_iface.query("START proc_node=node({id}) "
                          "MATCH proc_node<-[rel:PROC_OBJ]-loc_node "
                          "WHERE rel.state <> {state} "
                          "RETURN loc_node, rel",
                          id=proc_node.id, state=storage.LinkState.INACTIVE)
    for row in rows:
        loc_node = row['loc_node']
        rel = row['rel']
        loc_node_link_list.append((loc_node, rel))
    return loc_node_link_list


def get_next_local_version(db_iface, loc_node):
    '''Gets the next local object version'''
    next_loc_node = None

    rows = db_iface.query("START loc_node=node({id}) "
                          "MATCH loc_node<-[rel:LOC_OBJ_PREV]-next_loc_node "
                          "RETURN next_loc_node", id=loc_node.id)
    for row in rows:
        next_loc_node = row['next_loc_node']
    return next_loc_node


@storage.CacheManager.dec(storage.CACHE_NAMES.VALID_LOCAL,
                          lambda proc_node, loc_name: (proc_node.id, loc_name))
def get_valid_local(db_iface, proc_node, loc_name):
    '''Returns a local, local->process link tuple
    filtered by local node name and link state'''
    loc_node = None
    loc_proc_rel = None

    rows = db_iface.query("START proc_node=node({id}) "
                          "MATCH proc_node<-[lp_rel:PROC_OBJ]-loc_node "
                          "WHERE lp_rel.state <> {state1} "
                          "AND lp_rel.state <> {state2} "
                          "AND loc_node.name = {name} "
                          "RETURN loc_node, lp_rel ",
                          id=proc_node.id, state1=storage.LinkState.CLOSED,
                          state2=storage.LinkState.INACTIVE, name=loc_name)
    for row in rows:
        loc_node = row['loc_node']
        loc_proc_rel = row['lp_rel']
    return loc_node, loc_proc_rel


def get_glob_latest_version(db_iface, loc_node):
    '''Returns the latest valid version of a global node'''
    ret_glob = None

    glob_node_list = get_globals_from_local(db_iface, loc_node)
    glob_list_len = len(glob_node_list)

    if glob_list_len == 0:
        return ret_glob

    if glob_list_len > 1:
        logging.error("Tracing latest global of invalid local.")
        return ret_glob

    glob_node, _ = glob_node_list[0]

    # If there are no new versions of the global node the
    # local is pointing to, then return the current global
    if len(glob_node.relationships.incoming) == 0:
        return glob_node

    # The global has versioned, traverse the graph until you find
    # the last global node that is not in deleted status. Avoid
    # taversing down deleted paths.
    found = False
    node_id = glob_node.id

    while 1:
        result = db_iface.query(
            "START src_node=node({id}) "
            "MATCH src_node<-[rel:GLOB_OBJ_PREV]-dest_node "
            "WHERE rel.state <> {state} "
            "RETURN dest_node "
            "ORDER BY dest_node.node_id",
            id=node_id, state=storage.LinkState.DELETED)
        for row in result:
            dest_glob_node = row['dest_node']
            node_id = dest_glob_node.id
            ret_glob = dest_glob_node
            found = True

        if found:  # Check if node has any incoming relationships
            if len(ret_glob.relationships.incoming) == 0:
                break
            else:
                found = False
                continue
        else:
            ret_glob = None
            break

    return ret_glob


def get_proc_meta(db_iface, proc_node, rel_type):
    '''Returns all meta objects of a given type and their
    relationship link to the process node proc_node'''
    meta_rel_list = []

    rows = db_iface.query("START proc_node=node({id}) "
                          "MATCH proc_node-[meta_rel:" + rel_type +
                          "]->meta_node "
                          "RETURN meta_node, meta_rel",
                          id=proc_node.id)
    for row in rows:
        meta_node = row['meta_node']
        meta_rel = row['meta_rel']
        meta_rel_list.append((meta_node, meta_rel))
    return meta_rel_list


@storage.CacheManager.dec(storage.CACHE_NAMES.LAST_EVENT,
                          lambda start_node, rel_type: start_node.id)
def get_last_event(db_iface, start_node, rel_type):
    '''Returns the event object and relationship link
    connected to the passed node'''
    last_event_node = None
    event_rel = None

    rows = db_iface.query("START start_node=node({id}) "
                          "MATCH start_node-[rel:" + rel_type +
                          "]->event_node "
                          "RETURN event_node, rel",
                          id=start_node.id)
    for row in rows:
        last_event_node = row['event_node']
        event_rel = row['rel']
    return last_event_node, event_rel


def get_rel(db_iface, src_node, rel_type):
    '''Returns a list of relationship links of rel_type
    from the source node src_node'''
    rel_list = []

    rows = db_iface.query("START src_node=node({id}) "
                          "MATCH src_node-[rel:" + rel_type + "]->dest_node "
                          "RETURN rel", id=src_node.id)
    for row in rows:
        rel = row['rel']
        rel_list.append(rel)
    return rel_list
