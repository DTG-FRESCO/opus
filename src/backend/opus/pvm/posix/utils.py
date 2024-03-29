# -*- coding: utf-8 -*-
'''
Various utility methods that support the actions and functions of the PVM posix
analyser implementation.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import functools
import logging

from ... import pvm, storage, traversal
from ...exception import NoMatchingLocalError, InvalidNodeTypeException


def parse_git_hash(msg):
    '''Returns git hash field if present'''
    git_hash = None
    if msg.HasField('git_hash'):
        git_hash = msg.git_hash
    return git_hash

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

    event_node['before_time'] = str(msg.begin_time)
    event_node['after_time'] = str(msg.end_time)
    return event_node


def proc_get_local(db_iface, proc_node, loc_name):
    '''Retrieves the local object node that corresponds with
    a given name from a process node.'''

    loc_node, _ = traversal.get_valid_local(db_iface, proc_node, loc_name)
    if loc_node is None:
        raise NoMatchingLocalError(proc_node, loc_name)

    return loc_node


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


def update_event_chain_cache(db_iface, loc_node, event_node):
    '''Finds the correct fd chain object and appends event node to the chain'''
    proc_node, _ = traversal.get_process_from_local(db_iface, loc_node)
    idx_list = db_iface.cache_man.get(storage.CACHE_NAMES.IO_EVENT_CHAIN,
                                      (proc_node.id, loc_node['name']))
    if idx_list is None:
        logging.error("Unable to get cached events for pid: %d and fd: %s",
                      proc_node['pid'], loc_node['name'])
    else:
        loc_index = idx_list.find(loc_node, key=lambda x: int(x['mono_time']))
        fd_chain = idx_list[loc_index - 1]
        fd_chain.chain.append(event_node)


def add_event(db_iface, node, msg):
    '''Adds an event to node, automatically deriving the object type.'''
    rel_type = None
    event_node = event_from_msg(db_iface, msg)
    node_type = node['type']

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
    new_event_rel = db_iface.create_relationship(node, event_node, rel_type)

    if event_rel is not None:
        # Delete the old link between node object and old event object
        db_iface.delete_relationship(event_rel)

    # Update the new event and relation in the event cache
    db_iface.cache_man.update(storage.CACHE_NAMES.LAST_EVENT, node.id,
                              (event_node, new_event_rel))

    # Update IO_EVENT_CHAIN cache
    if node_type == storage.NodeType.LOCAL:
        update_event_chain_cache(db_iface, node, event_node)


def _bind_global_to_new_local(db_iface, proc_node, o_loc_node, i_loc_node):
    '''Helper function that binds the new local node to the global nodes
    associated with the old local node'''
    i_glob_node_link_list = traversal.get_globals_from_local(db_iface,
                                                             i_loc_node)
    if len(i_glob_node_link_list) == 1:
        i_glob_node, i_glob_loc_rel = i_glob_node_link_list[0]

        # Copy over state from input fd link
        old_state = None
        if proc_node.has_key('opus_lite') and proc_node['opus_lite']:
            old_state = i_glob_loc_rel['state']

        new_glob_node = pvm.version_global(db_iface, i_glob_node)
        pvm.bind(db_iface, o_loc_node, new_glob_node, old_state)


def proc_dup_fd(db_iface, proc_node, fd_i, fd_o, lp_link_state=None):
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
            glob_node, _ = glob_node_link_list[0]
            _, new_o_loc_node = pvm.drop_g(db_iface, o_loc_node, glob_node)
            pvm.drop_l(db_iface, new_o_loc_node)
        else:
            pvm.drop_l(db_iface, o_loc_node)

    o_loc_node = pvm.get_l(db_iface, proc_node, fd_o)
    if lp_link_state is not None:
        db_iface.set_link_state(o_loc_node.PROC_OBJ.outgoing, lp_link_state)

    _bind_global_to_new_local(db_iface, proc_node, o_loc_node, i_loc_node)


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
            version_meta(db_iface, proc_node, meta_node, meta_rel, env)

    if not found and val is not None:
        new_meta_node = new_meta(db_iface, name, val, time_stamp)
        db_iface.create_relationship(proc_node, new_meta_node,
                                     storage.RelType.ENV_META)


def version_meta(db_iface, proc_node, meta_node, meta_rel, env):
    '''Adds a new node to the meta chain of 'proc_node' replacing
    'meta_node'.'''
    name, val, time_stamp = env
    new_meta_node = new_meta(db_iface, name, val, time_stamp)

    db_iface.create_relationship(new_meta_node, meta_node,
                                 storage.RelType.META_PREV)
    db_iface.create_relationship(proc_node, new_meta_node,
                                 storage.RelType.ENV_META)
    db_iface.delete_relationship(meta_rel)


def set_rw_lnk(db_iface, loc_node, state):
    '''Sets the link between local and the global it is connected to. The link
    is set to either state or the appropriate combination(if the link is
    already READ trying to set it to WRITE will result in RaW).'''
    glob_node_list = traversal.get_globals_from_local(db_iface, loc_node)

    if len(glob_node_list) == 1:
        _, glob_loc_rel = glob_node_list[0]
        if((state == storage.LinkState.READ and
            glob_loc_rel['state'] == storage.LinkState.WRITE) or
           (state == storage.LinkState.WRITE and
            glob_loc_rel['state'] == storage.LinkState.READ) or
           glob_loc_rel['state'] == storage.LinkState.RaW):
            new_state = storage.LinkState.RaW
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
                                      "name", name, glob_node)
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

    # In OPUS lite mode, tag read and write on the link
    read_state = None
    write_state = None
    if proc_node.has_key('opus_lite') and proc_node['opus_lite']:
        read_state = storage.LinkState.READ
        write_state = storage.LinkState.WRITE

    pvm.bind(db_iface, loc_node1, new_glob_node, read_state)
    add_event(db_iface, loc_node1, msg)
    pvm.bind(db_iface, loc_node2, new_glob_node, write_state)
    return loc_node2
