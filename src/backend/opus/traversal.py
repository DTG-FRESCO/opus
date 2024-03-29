# -*- coding: utf-8 -*-
'''
The traversal module contains procedures for traversing the graph.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
from . import storage

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

    for tmp_rel in loc_node.LOC_OBJ.incoming:
        glob_node_link_list.append((tmp_rel.start, tmp_rel))
    return glob_node_link_list


def get_locals_from_global(db_iface, glob_node):
    '''Gets all local object nodes and the relationship
    links connected to the given global'''
    loc_node_link_list = []

    for tmp_rel in glob_node.LOC_OBJ.outgoing:
        loc_node_link_list.append((tmp_rel.end, tmp_rel))
    return loc_node_link_list


def get_process_from_local(db_iface, loc_node):
    '''Gets the process node and relationship link
    from the local obj'''
    proc_node = None
    rel = None

    for tmp_rel in loc_node.PROC_OBJ.outgoing:
        rel = tmp_rel
        proc_node = tmp_rel.end
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

    for rel in loc_node.LOC_OBJ_PREV.incoming:
        next_loc_node = rel.start
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


def get_glob_latest_version(db_iface, glob_node):
    '''Returns the latest valid version of a global node'''

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

    lst = None
    if rel_type == storage.RelType.IO_EVENTS:
        lst = start_node.IO_EVENTS.outgoing
    elif rel_type == storage.RelType.PROC_EVENTS:
        lst = start_node.PROC_EVENTS.outgoing

    for rel in lst:
        last_event_node = rel.end
        event_rel = rel
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

def get_rel_to_dest(db_iface, rel_list, dest_node):
    '''Returns the correct relationship link to the
    destination node'''
    rel = None

    for tmp_rel in rel_list:
        if tmp_rel.end.id == dest_node.id:
            rel = tmp_rel
            break
    return rel
