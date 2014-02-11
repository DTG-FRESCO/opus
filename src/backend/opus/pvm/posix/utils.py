# -*- coding: utf-8 -*-
'''
Various utility methods that support the actions and functions of the PVM posix
analyser implementation.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import functools
import logging


from opus import prov_db_pb2 as prov_db
from opus import pvm, storage, common_utils

class PVMException(common_utils.OPUSException):
    '''Base exception for PVM related failures.'''
    def __init__(self, msg):
        super(PVMException, self).__init__(msg)


class NoMatchingLocalError(PVMException):
    '''Failed to find a local object matching the supplied name.'''
    def __init__(self, proc_node, name):
        super(NoMatchingLocalError, self).__init__(
            "Error: Failed to find local %s in process %d" % (name, proc_node.id)
        )


def parse_kvpair_list(args):
    '''Converts a list of KVPair messages to a dictionary.'''
    return {arg.key: arg.value for arg in args}


def check_message_error_num(func):
    '''Check the error_num of the message passed and if it is a fail add an
    event to the process object then abort. Otherwise process as ususal.'''
    @functools.wraps(func)
    def wrapper(storage_iface, proc_node, msg, *args, **kwargs):
        '''Should never be seen.'''
        if msg.error_num > 0:
            return proc_node
        return func(storage_iface, proc_node, msg, *args, **kwargs)
    return wrapper


def add_meta_to_proc(storage_iface, proc_node, name, val, time_stamp, rel_type):
    '''Creates a meta node and links it to a process node'''
    meta_node = new_meta(storage_iface, name, val, time_stamp)
    storage_iface.create_relationship(proc_node, meta_node, rel_type)


def process_from_startup(storage_iface, (hdr, pay)):
    '''Given a hdr, pay pair for a startup message create a process node,
    meta nodes and link the process node to the meta nodes.'''

    proc_node = storage_iface.create_node(storage.NodeType.PROCESS)

    # Set properties on the process node
    time_stamp = hdr.timestamp
    proc_node['pid'] = hdr.pid

    proc_node['timestamp'] = time_stamp

    if pay.HasField('cwd'):
        add_meta_to_proc(storage_iface, proc_node, "cwd", pay.cwd, time_stamp,
                    storage.RelType.OTHER_META)

    if pay.HasField('cmd_line_args'):
        add_meta_to_proc(storage_iface, proc_node, "cmd_args",
                    pay.cmd_line_args, time_stamp,
                    storage.RelType.OTHER_META)

    if pay.HasField('user_name'):
        add_meta_to_proc(storage_iface, proc_node, "uid", pay.user_name,
                    time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('group_name'):
        add_meta_to_proc(storage_iface, proc_node, "gid", pay.group_name,
                    time_stamp, storage.RelType.OTHER_META)

    for pair in pay.environment:
        add_meta_to_proc(storage_iface, proc_node, pair.key, pair.value,
                    time_stamp, storage.RelType.ENV_META)

    for pair in pay.system_info:
        add_meta_to_proc(storage_iface, proc_node, pair.key, pair.value,
                    time_stamp, storage.RelType.OTHER_META)

    for pair in pay.resource_limit:
        add_meta_to_proc(storage_iface, proc_node, pair.key, pair.value,
                    time_stamp, storage.RelType.OTHER_META)

    return proc_node


def clone_file_des(storage_iface, old_proc_node, new_proc_node):
    '''Clones the file descriptors of old_proc_node to new_proc_node
    using the CoT mechanism.'''
    loc_node_link_list = storage_iface.get_locals_from_process(old_proc_node)
    for (loc_node, rel_link) in loc_node_link_list:
        if rel_link['state'] in [storage.LinkState.CLOSED,
                                storage.LinkState.CLOEXEC]:
            continue
        # Create a new link from the local node to the new process node
        new_rel_link = storage_iface.create_relationship(loc_node,
                                new_proc_node, storage.RelType.PROC_OBJ)
        new_rel_link['state'] = storage.LinkState.CoT


def new_meta(storage_iface, name, val, time_stamp):
    '''Create a new meta object node with the given name, value and timestamp.'''
    meta_node = storage_iface.create_node(storage.NodeType.META)
    meta_node['name'] = name
    if val is not None:
        meta_node['value'] = val
    meta_node['timestamp'] = time_stamp
    return meta_node


def event_from_msg(storage_iface, msg):
    '''Create an event object node from the given function info message.'''
    event_node = storage_iface.create_node(storage.NodeType.EVENT)
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



def proc_get_local(storage_iface, proc_node, loc_name):
    '''Retrieves the local object node that corresponds with
    a given name from a process node.'''

    loc_node, loc_proc_rel = storage_iface.get_valid_local(proc_node, loc_name)
    if loc_node is None:
        raise NoMatchingLocalError(proc_node, loc_name)

    if loc_proc_rel['state'] != storage.LinkState.CoT:
        return loc_node

    #### Handle Copy on Touch ####

    # Delete the CoT link to local
    storage_iface.delete_relationship(loc_proc_rel)

    # Create a new local object node
    new_loc_node = pvm.get_l(storage_iface, proc_node, loc_name)

    # Find the newest valid version of the global object
    glob_node = storage_iface.get_glob_latest_version(loc_node)
    if glob_node is None:
        return new_loc_node

    new_glob_node = pvm.version_global(storage_iface, glob_node)
    pvm.bind(storage_iface, new_loc_node, new_glob_node)
    return new_loc_node



def ins_local(storage_iface, event_node, loc_node):
    '''Inserts an event into local object.'''

    # Get the last IO event and the connecting link
    last_io_event_node, event_rel = storage_iface.get_last_event(loc_node,
                                                storage.RelType.IO_EVENTS)

    if last_io_event_node is not None:
        # Link the new event with the last IO event as previous
        storage_iface.create_relationship(event_node, last_io_event_node,
                                        storage.RelType.PREV_EVENT)

    # Create a new link between local object and new event object
    storage_iface.create_relationship(loc_node, event_node,
                                        storage.RelType.IO_EVENTS)

    if event_rel is not None:
        # Delete the old link between local object and old event object
        storage_iface.delete_relationship(event_rel)


def ins_proc(storage_iface, event_node, proc_node):
    '''Inserts an event into process object.'''

    # Get the last process event and the connecting link
    last_proc_event_node, event_rel = storage_iface.get_last_event(proc_node,
                                                storage.RelType.PROC_EVENTS)

    if last_proc_event_node is not None:
        # Link the new event with the last process event as previous
        storage_iface.create_relationship(event_node, last_proc_event_node,
                                        storage.RelType.PREV_EVENT)

    # Create a new link between process object and new event object
    storage_iface.create_relationship(proc_node, event_node,
                                        storage.RelType.PROC_EVENTS)

    if event_rel is not None:
        # Delete the old link between process object and old event object
        storage_iface.delete_relationship(event_rel)


def update_proc_meta(storage_iface, proc_node, meta_name, new_val, timestamp):
    '''Updates the meta object meta_name for the process with a new value
    and timestamp. Adds a new object if an existing one cannot be found.'''
    meta_node = new_meta(storage_iface, meta_name, new_val, timestamp)

    other_meta_list = storage_iface.get_proc_meta(proc_node,
                                        storage.RelType.OTHER_META)

    # Version the meta object if it exists
    for old_meta, meta_rel in other_meta_list:
        if old_meta['name'] == meta_name:
            storage_iface.create_relationship(meta_node, old_meta,
                                        storage.RelType.META_PREV)
            # Delete existing link from process to the meta object node
            storage_iface.delete_relationship(meta_rel)
            break

    # Add link from process node to newly added meta node
    storage_iface.create_relationship(proc_node, meta_node,
                                        storage.RelType.OTHER_META)


def add_event(storage_iface, node, msg):
    '''Adds an event to node, automatically deriving the object type.'''
    event_node = event_from_msg(storage_iface, msg)
    node_type = node['type']
    if node_type == storage.NodeType.LOCAL:
        ins_local(storage_iface, event_node, node)
    elif node_type == storage.NodeType.PROCESS:
        ins_proc(storage_iface, event_node, node)


def proc_dup_fd(storage_iface, proc_node, fd_i, fd_o):
    '''Helper for duplicating file descriptors. Handles closing the old
    descriptor if needed and binding it to the new identifier.'''
    if fd_i == fd_o:
        return

    i_loc_node = proc_get_local(storage_iface, proc_node, fd_i)
    try:
        o_loc_node = proc_get_local(storage_iface, proc_node, fd_o)
    except NoMatchingLocalError:
        pass
    else:
        glob_node_link_list = storage_iface.get_globals_from_local(o_loc_node)
        if len(glob_node_link_list) > 0:
            glob_node, glob_loc_rel = glob_node_link_list[0]
            new_glob_node, new_o_loc_node = pvm.drop_g(storage_iface,
                                            o_loc_node, glob_node)
            pvm.drop_l(storage_iface, new_o_loc_node)
        else:
            pvm.drop_l(storage_iface, o_loc_node)

    o_loc_node = pvm.get_l(storage_iface, proc_node, fd_o)
    i_glob_node_link_list = storage_iface.get_globals_from_local(i_loc_node)
    if len(i_glob_node_link_list) == 1:
        i_glob_node, i_glob_rel = i_glob_node_link_list[0]
        new_glob_node = pvm.version_global(storage_iface, i_glob_node)
        pvm.bind(storage_iface, o_loc_node, new_glob_node)


def process_put_env(storage_iface, proc_node, env, overwrite):
    '''Helper for edit processes environment, attempts to put name, val, ts
    into the processes environment. Clears keys if val is None, only overwrites
    existing keys if overwrite is set and inserts if the key is not found and
    val is not None.'''
    found = False
    (name, val, time_stamp) = env

    env_meta_list = storage_iface.get_proc_meta(proc_node,
                                storage.RelType.ENV_META)

    for meta_node, meta_rel in env_meta_list:
        if meta_node['name'] == name:
            found = True
            if not overwrite:
                break
            new_meta_node = new_meta(storage_iface, name, val, time_stamp)
            storage_iface.create_relationship(new_meta_node, meta_node,
                                        storage.RelType.META_PREV)
            storage_iface.create_relationship(proc_node, new_meta_node,
                                        storage.RelType.ENV_META)
            storage_iface.delete_relationship(meta_rel)

    if not found and val is not None:
        new_meta_node = new_meta(storage_iface, name, val, time_stamp)
        storage_iface.create_relationship(proc_node, new_meta_node,
                                        storage.RelType.ENV_META)


def set_rw_lnk(storage_iface, loc_node, state):
    '''Sets the link between local and the global it is connected to. The link
    is set to either state or the appropriate combination(if the link is
    already READ trying to set it to WRITE will result in RaW).'''
    glob_node_list = storage_iface.get_globals_from_local(loc_node)

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

        set_link(storage_iface, loc_node, new_state)



def set_link(storage_iface, loc_node, state):
    '''Sets the link between loc_node and the global it is connected to.'''
    glob_node_link_list = storage_iface.get_globals_from_local(loc_node)
    if len(glob_node_link_list) == 1:
        glob_node, rel_link = glob_node_link_list[0]
        rel_link['state'] = state
        if state == storage.LinkState.BIN:
            for name in glob_node['name']:
                storage_iface.update_index(storage.Neo4JInterface.PROC_INDEX,
                                            'name', name, glob_node)



def process_rw_pair(storage_iface, proc_node, msg):
    '''Helper function to implement PVM operations for a pair of file
    descriptors typically created by calls to pipe and socketpair'''
    args = parse_kvpair_list(msg.args)

    # Create local objects for read and write fds
    read_fd = args['read_fd']
    loc_node1 = pvm.get_l(storage_iface, proc_node, read_fd)
    write_fd = args['write_fd']
    loc_node2 = pvm.get_l(storage_iface, proc_node, write_fd)

    # Get a global object ID and bind both read and write fds
    new_glob_node = storage_iface.create_node(storage.NodeType.GLOBAL)

    pvm.bind(storage_iface, loc_node1, new_glob_node)
    add_event(storage_iface, loc_node1, msg)
    pvm.bind(storage_iface, loc_node2, new_glob_node)
    return loc_node2
