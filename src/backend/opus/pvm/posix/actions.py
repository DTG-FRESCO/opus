# -*- coding: utf-8 -*-
'''
Implementations of many standard actions that posix functions can perform that
are shown in terms of their PVM semantics.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import logging

from opus import pvm
from opus.pvm.posix import utils
from opus import prov_db_pb2 as prov_db


class ActionMap(object):
    '''Mapping of action names to action functions.'''
    action_map = {}

    @classmethod
    def get(cls, key):
        '''Return the function associated with key.'''
        return cls.action_map[key]

    @classmethod
    def add(cls, name):
        '''Adds name => fun to the map.'''
        def wrapper(fun):
            '''Decorator internal.'''
            cls.action_map[name] = fun
            return fun
        return wrapper


@ActionMap.add('event')
def event_action(*args):
    '''Action representing a function that only generates a process event.'''
    return args[1] #p_id


@ActionMap.add('read')
def read_action(tran, p_id, msg, fd_arg):
    '''Action that reads from a names file descriptor.'''
    l_id = null_action(tran, p_id, msg, fd_arg)
    utils.set_rw_lnk(tran, l_id, prov_db.READ)
    return l_id


@ActionMap.add('write')
def write_action(tran, p_id, msg, fd_arg):
    '''Action that writes to a named file descriptor.'''
    l_id = null_action(tran, p_id, msg, fd_arg)
    utils.set_rw_lnk(tran, l_id, prov_db.WRITE)
    return l_id


@ActionMap.add('null')
def null_action(tran, p_id, msg, fd_arg):
    '''Action that interacts with a file descriptor but is neither a read or a
    write. Also the common basis between both the read and write actions.'''
    if isinstance(fd_arg, unicode) or isinstance(fd_arg, str):
        args = utils.parse_kvpair_list(msg.args)
        file_des = args[fd_arg]
    else:
        file_des = fd_arg
    l_id = utils.proc_get_local(tran, p_id, file_des)
    return l_id


@ActionMap.add('open')
@utils.check_message_error_num
def open_action(tran, p_id, msg, file_arg):
    '''Action that opens a named file.'''
    args = utils.parse_kvpair_list(msg.args)
    l_id = pvm.get_l(tran, p_id, str(msg.ret_val))
    pvm.get_g(tran, l_id, args[file_arg])
    return l_id


@ActionMap.add('close')
def close_action(tran, p_id, msg, fd_arg):
    '''Action that closes a named file descriptor.'''
    args = utils.parse_kvpair_list(msg.args)
    try:
        l_id = utils.proc_get_local(tran, p_id, args[fd_arg])
    except utils.NoMatchingLocalError:
        return p_id

    if msg.error_num > 0:
        return l_id
    l_obj = tran.get(l_id)
    if len(l_obj.file_object) > 0:
        if len(l_obj.file_object) > 1:
            logging.error("Closing invalid local object.")
        g_id = l_obj.file_object[0].id
        pvm.drop_g(tran, l_id, g_id)
        l_obj = tran.get(l_id)
        new_l_id = l_obj.next_version.id
        pvm.drop_l(tran, new_l_id)
    else:
        pvm.drop_l(tran, l_id)

    return l_id


def delete_single_name(tran, omega_id, g_id):
    '''Deletes a file with a single name.'''
    g_obj = tran.get(g_id)
    new_g_id = pvm.drop_g(tran, omega_id, g_id)
    new_g_obj = tran.get(new_g_id)
    new_g_obj.prev_version[0].state = prov_db.DELETED
    g_obj.next_version[0].state = prov_db.DELETED
    for lnk in new_g_obj.process_object:
        pvm.unbind(tran, lnk.id, new_g_id)


def delete_multiple_names(tran, omega_id, g_id, g_name):
    '''Deletes a file with multiple names.'''
    g_obj = tran.get(g_id)
    main_g_id = pvm.drop_g(tran, omega_id, g_id)
    main_g_obj = tran.get(main_g_id)
    for i in range(len(main_g_obj.name)):
        if main_g_obj.name[i] == g_name:
            del main_g_obj.name[i]
            break
    for lnk in main_g_obj.process_object:
        loc = tran.get(lnk.id)
        loc.ref_count = loc.ref_count - 1
    (side_g_id, side_g_obj) = tran.create(prov_db.GLOBAL)
    side_g_obj.name.append(g_name)
    tran.name_put(g_name, side_g_id)
    fwd = g_obj.next_version.add()
    fwd.id = side_g_id
    fwd.state = prov_db.DELETED
    bck = side_g_obj.prev_version.add()
    bck.id = g_id
    bck.state = prov_db.DELETED


@ActionMap.add('delete')
@utils.check_message_error_num
def delete_action(tran, p_id, msg, file_arg):
    '''Action that deletes a named file.'''
    args = utils.parse_kvpair_list(msg.args)
    l_id = pvm.get_l(tran, p_id, "omega")
    g_name = args[file_arg]
    g_id = pvm.get_g(tran, l_id, g_name)
    g_obj = tran.get(g_id)
    if len(g_obj.name) == 1:
        delete_single_name(tran, l_id, g_id)
    else:
        delete_multiple_names(tran, l_id, g_id, g_name)
    new_l_id = tran.get(l_id).next_version.id
    pvm.drop_l(tran, new_l_id)
    utils.set_rw_lnk(tran, l_id, prov_db.WRITE)
    return l_id


@ActionMap.add('link')
@utils.check_message_error_num
def link_action(tran, p_id, msg, orig_arg, new_arg):
    '''Action that links a new name to an existing file.'''
    args = utils.parse_kvpair_list(msg.args)
    l_id = pvm.get_l(tran, p_id, "omega")
    orig_id = pvm.get_g(tran, l_id, args[orig_arg])
    new_id = pvm.get_g(tran, l_id, args[new_arg])
    orig_id = pvm.drop_g(tran, l_id, orig_id)
    new_obj = tran.get(new_id)
    for lnk in new_obj.process_object:
        if lnk.id != l_id:
            pvm.version_local(tran, lnk.id, orig_id)
    orig_obj = tran.get(orig_id)
    for name in new_obj.name:
        orig_obj.name.append(name)
    new_obj.next_version.add().id = orig_id
    orig_obj.prev_version.add().id = new_id
    new_l_id = tran.get(l_id).next_version.id
    pvm.drop_l(tran, new_l_id)
    return l_id

@ActionMap.add('touch')
@utils.check_message_error_num
def touch_action(tran, p_id, msg, file_arg):
    '''Action that touches a named file.'''
    args = utils.parse_kvpair_list(msg.args)
    l_id = pvm.get_l(tran, p_id, "omega")
    g_id = pvm.get_g(tran, l_id, args[file_arg])
    pvm.drop_g(tran, l_id, g_id)
    l_obj = tran.get(l_id)
    new_l_id = l_obj.next_version.id
    pvm.drop_l(tran, new_l_id)
    return l_id