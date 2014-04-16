# -*- coding: utf-8 -*-
'''
Various utility methods that support the actions and functions of the PVM posix
analyser implementation.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import functools
import logging

from opus import pvm, storage, common_utils, traversal


class InvalidNodeTypeException(common_utils.OPUSException):
    '''exception for Invalid node types.'''
    def __init__(self, node_type):
        super(InvalidNodeTypeException, self).__init__(
            "Error: Tried to assign an event to a node of type %d, "
            "expected Local or Process." % node_type)


class NoMatchingLocalError(common_utils.OPUSException):
    '''Failed to find a local object matching the supplied name.'''
    def __init__(self, proc_node, name):
        super(NoMatchingLocalError, self).__init__(
            "Error: Failed to find local %s in process %d" % (name,
                                                              proc_node.id)
        )


def parse_kvpair_list(args):
    '''Converts a list of KVPair messages to a dictionary.'''
    return {arg.key: arg.value for arg in args}


def check_message_error_num(func):
    '''Check the error_num of the message passed and if it is a fail add an
    event to the process object then abort. Otherwise process as ususal.'''
    @functools.wraps(func)
    def wrapper(db_iface, proc_node, msg, *args, **kwargs):
        '''Should never be seen.'''
        if msg.error_num > 0:
            return proc_node
        return func(db_iface, proc_node, msg, *args, **kwargs)
    return wrapper


def add_meta_to_proc(db_iface, proc_node, name, val, time_stamp, rel_type):
    '''Creates a meta node and links it to a process node'''
    meta_node = new_meta(db_iface, name, val, time_stamp)
    db_iface.create_relationship(proc_node, meta_node, rel_type)


def new_meta(db_iface, name, val, time_stamp):
    '''Create a new meta object node with the given name,
    value and timestamp.'''
    meta_node = db_iface.create_node(storage.NodeType.META)
    meta_node['name'] = name
    if val is not None:
        meta_node['value'] = val
    meta_node['timestamp'] = time_stamp
    return meta_node


def event_from_msg(db_iface, msg):
    '''Create an event object node from the given function info message.'''
    event_node = db_iface.create_node(storage.NodeType.EVENT)
    event_node['fn'] = msg.func_name
    event_node['ret'] = msg.ret_val

    arg_keys = []
    arg_values = []
    for obj in msg.args:
        arg_keys.append(obj.key)
        arg_values.append(obj.value)

    if len(arg_keys) > 0:
        event_node['arg_keys'] = arg_keys

    if len(arg_values) > 0:
        event_node['arg_values'] = arg_values

    event_node['before_time'] = msg.begin_time
    event_node['after_time'] = msg.end_time
    return event_node



def proc_get_local(db_iface, proc_node, loc_name):
    '''Retrieves the local object node that corresponds with
    a given name from a process node.'''

    loc_node, loc_proc_rel = traversal.get_valid_local(db_iface, proc_node,
                                                       loc_name)
    if loc_node is None:
        raise NoMatchingLocalError(proc_node, loc_name)

    if loc_proc_rel['state'] != storage.LinkState.CoT:
        return loc_node

    #### Handle Copy on Touch ####

    # Delete the CoT link to local
    db_iface.delete_relationship(loc_proc_rel)

    # Create a new local object node
    new_loc_node = pvm.get_l(db_iface, proc_node, loc_name)

    # Find the newest valid version of the global object
    glob_node = traversal.get_glob_latest_version(db_iface, loc_node)
    if glob_node is None:
        return new_loc_node

    new_glob_node = pvm.version_global(db_iface, glob_node)
    pvm.bind(db_iface, new_loc_node, new_glob_node)
    return new_loc_node


def update_proc_meta(db_iface, proc_node, meta_name, new_val, timestamp):
    '''Updates the meta object meta_name for the process with a new value
    and timestamp. Adds a new object if an existing one cannot be found.'''
    meta_node = new_meta(db_iface, meta_name, new_val, timestamp)

    other_meta_list = traversal.get_proc_meta(db_iface, proc_node,
                                              storage.RelType.OTHER_META)

    # Version the meta object if it exists
    for old_meta, meta_rel in other_meta_list:
        if old_meta['name'] == meta_name:
            db_iface.create_relationship(meta_node, old_meta,
                                         storage.RelType.META_PREV)
            # Delete existing link from process to the meta object node
            db_iface.delete_relationship(meta_rel)
            break

    # Add link from process node to newly added meta node
    db_iface.create_relationship(proc_node, meta_node,
                                 storage.RelType.OTHER_META)


def add_event(db_iface, node, msg):
    '''Adds an event to node, automatically deriving the object type.'''
    rel_type = None
    event_node = event_from_msg(db_iface, msg)
    node_type = node['type']

    db_iface.cache_man.invalidate(storage.CACHE_NAMES.LAST_EVENT,
                                  node.id)

    if node_type == storage.NodeType.LOCAL:
        rel_type = storage.RelType.IO_EVENTS
    elif node_type == storage.NodeType.PROCESS:
        rel_type = storage.RelType.PROC_EVENTS

    if rel_type is None:
        raise InvalidNodeTypeException(node_type)

    # Get the last event and the connecting link
    last_event_node, event_rel = traversal.get_last_event(db_iface, node,
                                                          rel_type)

    if last_event_node is not None:
        # Link the new event with the last event as previous
        db_iface.create_relationship(event_node, last_event_node,
                                     storage.RelType.PREV_EVENT)

    # Create a new link between node object and new event object
    db_iface.create_relationship(node, event_node, rel_type)

    if event_rel is not None:
        # Delete the old link between node object and old event object
        db_iface.delete_relationship(event_rel)


def proc_dup_fd(db_iface, proc_node, fd_i, fd_o):
    '''Helper for duplicating file descriptors. Handles closing the old
    descriptor if needed and binding it to the new identifier.'''
    if fd_i == fd_o:
        return

    i_loc_node = proc_get_local(db_iface, proc_node, fd_i)
    try:
        o_loc_node = proc_get_local(db_iface, proc_node, fd_o)
    except NoMatchingLocalError:
        pass
    else:
        glob_node_link_list = traversal.get_globals_from_local(db_iface,
                                                               o_loc_node)
        if len(glob_node_link_list) > 0:
            glob_node, glob_loc_rel = glob_node_link_list[0]
            new_glob_node, new_o_loc_node = pvm.drop_g(db_iface,
                                                       o_loc_node, glob_node)
            pvm.drop_l(db_iface, new_o_loc_node)
        else:
            pvm.drop_l(db_iface, o_loc_node)

    o_loc_node = pvm.get_l(db_iface, proc_node, fd_o)
    i_glob_node_link_list = traversal.get_globals_from_local(db_iface,
                                                             i_loc_node)
    if len(i_glob_node_link_list) == 1:
        i_glob_node, i_glob_rel = i_glob_node_link_list[0]
        new_glob_node = pvm.version_global(db_iface, i_glob_node)
        pvm.bind(db_iface, o_loc_node, new_glob_node)


def process_put_env(db_iface, proc_node, env, overwrite):
    '''Helper for edit processes environment, attempts to put name, val, ts
    into the processes environment. Clears keys if val is None, only overwrites
    existing keys if overwrite is set and inserts if the key is not found and
    val is not None.'''
    found = False
    (name, val, time_stamp) = env

    env_meta_list = traversal.get_proc_meta(db_iface, proc_node,
                                            storage.RelType.ENV_META)

    for meta_node, meta_rel in env_meta_list:
        if meta_node['name'] == name:
            found = True
            if not overwrite:
                break
            new_meta_node = new_meta(db_iface, name, val, time_stamp)
            db_iface.create_relationship(new_meta_node, meta_node,
                                         storage.RelType.META_PREV)
            db_iface.create_relationship(proc_node, new_meta_node,
                                         storage.RelType.ENV_META)
            db_iface.delete_relationship(meta_rel)

    if not found and val is not None:
        new_meta_node = new_meta(db_iface, name, val, time_stamp)
        db_iface.create_relationship(proc_node, new_meta_node,
                                     storage.RelType.ENV_META)


def set_rw_lnk(db_iface, loc_node, state):
    '''Sets the link between local and the global it is connected to. The link
    is set to either state or the appropriate combination(if the link is
    already READ trying to set it to WRITE will result in RaW).'''
    glob_node_list = traversal.get_globals_from_local(db_iface, loc_node)

    if len(glob_node_list) == 1:
        glob_node, glob_loc_rel = glob_node_list[0]
        if ((state == storage.LinkState.READ and
            glob_loc_rel['state'] == storage.LinkState.WRITE) or
            (state == storage.LinkState.WRITE and
            glob_loc_rel['state'] == storage.LinkState.READ) or
            glob_loc_rel['state'] == storage.LinkState.RaW):
            new_state = storage.LinkState.Raw
        else:
            new_state = state

        set_link(db_iface, loc_node, new_state, glob_node_list)



def set_link(db_iface, loc_node, state, glob_node_list=None):
    '''Sets the link between loc_node and the global it is connected to.'''
    if glob_node_list is None:
        glob_node_list = traversal.get_globals_from_local(db_iface, loc_node)
    if len(glob_node_list) == 1:
        glob_node, rel_link = glob_node_list[0]
        rel_link['state'] = state
        if state == storage.LinkState.BIN:
            for name in glob_node['name']:
                db_iface.update_index(storage.DBInterface.PROC_INDEX,
                                      'name', name, glob_node)
            db_iface.update_time_index(storage.DBInterface.PROC_INDEX,
                                       glob_node['sys_time'], glob_node)



def process_rw_pair(db_iface, proc_node, msg):
    '''Helper function to implement PVM operations for a pair of file
    descriptors typically created by calls to pipe and socketpair'''
    args = parse_kvpair_list(msg.args)

    # Create local objects for read and write fds
    read_fd = args['read_fd']
    loc_node1 = pvm.get_l(db_iface, proc_node, read_fd)
    write_fd = args['write_fd']
    loc_node2 = pvm.get_l(db_iface, proc_node, write_fd)

    # Get a global object ID and bind both read and write fds
    new_glob_node = db_iface.create_node(storage.NodeType.GLOBAL)

    pvm.bind(db_iface, loc_node1, new_glob_node)
    add_event(db_iface, loc_node1, msg)
    pvm.bind(db_iface, loc_node2, new_glob_node)
    return loc_node2
