# -*- coding: utf-8 -*-
'''
Implementations of many standard actions that posix functions can perform that
are shown in terms of their PVM semantics.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


from ... import pvm, storage, traversal
from . import utils


class ActionMap(object):
    '''Mapping of action names to action functions.'''
    action_map = {}

    @classmethod
    def call(cls, name, err, *args, **kwargs):
        '''Return the function associated with key.'''
        if cls.action_map[name]['proc_err']:
            if err > 0:
                return args[1]  # p_id

            return cls.action_map[name]['func'](*args, **kwargs)
        return cls.action_map[name]['func'](err, *args, **kwargs)

    @classmethod
    def add(cls, name, proc_err):
        '''Adds name => fun to the map.'''
        def wrapper(fun):
            '''Decorator internal.'''
            cls.action_map[name] = {}
            cls.action_map[name]['func'] = fun
            cls.action_map[name]['proc_err'] = proc_err
            return fun
        return wrapper


@ActionMap.add('event', True)
def event_action(_, proc_node):
    '''Action representing a function that only generates a process event.'''
    return proc_node


@ActionMap.add('read', False)
def read_action(err, db_iface, proc_node, filedes):
    '''Action that reads from a names file descriptor.'''
    node = null_action(err, db_iface, proc_node, filedes)
    if node['type'] == storage.NodeType.LOCAL:
        utils.set_rw_lnk(db_iface, node, storage.LinkState.READ)
    return node


@ActionMap.add('write', False)
def write_action(err, db_iface, proc_node, filedes):
    '''Action that writes to a named file descriptor.'''
    node = null_action(err, db_iface, proc_node, filedes)
    if node['type'] == storage.NodeType.LOCAL:
        utils.set_rw_lnk(db_iface, node, storage.LinkState.WRITE)
    return node


@ActionMap.add('null', False)
def null_action(err, db_iface, proc_node, filedes):
    '''Action that interacts with a file descriptor but is neither a read or a
    write. Also the common basis between both the read and write actions.'''
    try:
        loc_node = utils.proc_get_local(db_iface, proc_node, filedes)
    except utils.NoMatchingLocalError:
        if err > 0:
            return proc_node
        else:
            raise utils.NoMatchingLocalError(proc_node, filedes)
    return loc_node


@ActionMap.add('open', True)
def open_action(db_iface, proc_node, filename, filedes):
    '''Action that opens a named file.'''
    loc_node = pvm.get_l(db_iface, proc_node, filedes)
    pvm.get_g(db_iface, loc_node, filename)
    return loc_node


@ActionMap.add('close', False)
def close_action(err, db_iface, proc_node, filedes):
    '''Action that closes a named file descriptor.'''
    try:
        loc_node = utils.proc_get_local(db_iface, proc_node, filedes)
    except utils.NoMatchingLocalError:
        if err > 0:
            return proc_node
        else:
            raise utils.NoMatchingLocalError(proc_node, filedes)

    if err > 0:
        return loc_node

    return close_action_helper(db_iface, loc_node)


def close_action_helper(db_iface, loc_node):
    glob_node_list = traversal.get_globals_from_local(db_iface, loc_node)
    if len(glob_node_list) > 0:
        glob_node, _ = glob_node_list[0]
        _, new_loc_node = pvm.drop_g(db_iface, loc_node, glob_node)
        pvm.drop_l(db_iface, new_loc_node)
    else:
        pvm.drop_l(db_iface, loc_node)

    return loc_node


def delete_single_name(db_iface, omega_id, glob_node):
    '''Deletes a file with a single name.'''
    new_glob_node, _ = pvm.drop_g(db_iface, omega_id, glob_node)
    prev_ver_rel_list = traversal.get_rel(db_iface, new_glob_node,
                                          storage.RelType.GLOB_OBJ_PREV)
    if len(prev_ver_rel_list) > 0:
        prev_ver_rel_list[0]['state'] = storage.LinkState.DELETED

    loc_node_rel_list = traversal.get_locals_from_global(db_iface,
                                                         new_glob_node)
    for loc_node, _ in loc_node_rel_list:
        pvm.unbind(db_iface, loc_node, new_glob_node)


def delete_multiple_names(db_iface, omega_id, glob_node, glob_name):
    '''Deletes a file with multiple names.'''
    main_glob_node, _ = pvm.drop_g(db_iface, omega_id, glob_node)

    glob_name_list = main_glob_node['name']
    for i in range(len(glob_name_list)):
        if glob_name_list[i] == glob_name:
            del glob_name_list[i]
            main_glob_node['name'] = glob_name_list
            break

    loc_node_rel_list = traversal.get_locals_from_global(db_iface,
                                                         main_glob_node)
    for loc_node, _ in loc_node_rel_list:
        loc_node['ref_count'] = loc_node['ref_count'] - 1

    side_glob_node = db_iface.create_node(storage.NodeType.GLOBAL)
    side_glob_node['name'] = [glob_name]
    db_iface.update_index(storage.DBInterface.FILE_INDEX, 'name',
                          glob_name, side_glob_node)

    glob_prev_rel = db_iface.create_relationship(side_glob_node, glob_node,
                                                 storage.RelType.GLOB_OBJ_PREV)
    glob_prev_rel['state'] = storage.LinkState.DELETED


@ActionMap.add('delete', True)
def delete_action(db_iface, proc_node, filename):
    '''Action that deletes a named file.'''
    loc_node = pvm.get_l(db_iface, proc_node, "omega")
    glob_node = pvm.get_g(db_iface, loc_node, filename)
    name_list = glob_node['name']
    if len(name_list) == 1:
        delete_single_name(db_iface, loc_node, glob_node)
    else:
        delete_multiple_names(db_iface, loc_node, glob_node, filename)

    new_loc_node = traversal.get_next_local_version(db_iface, loc_node)
    pvm.drop_l(db_iface, new_loc_node)
    utils.set_rw_lnk(db_iface, loc_node, storage.LinkState.WRITE)

    return loc_node


@ActionMap.add('link', True)
def link_action(db_iface, proc_node, orig_name, new_name):
    '''Action that links a new name to an existing file.'''
    loc_node = pvm.get_l(db_iface, proc_node, "omega")

    orig_glob_node = pvm.get_g(db_iface, loc_node, orig_name)

    new_glob_node = pvm.get_g(db_iface, loc_node, new_name)

    new_o_glob_node, new_o_loc_node = pvm.drop_g(db_iface,
                                                 loc_node, orig_glob_node)

    loc_node_rel_list = traversal.get_locals_from_global(db_iface,
                                                         new_glob_node)
    for l_node, g_l_rel in loc_node_rel_list:
        if l_node['node_id'] != loc_node['node_id']:
            pvm.version_local(db_iface, l_node, new_o_glob_node, g_l_rel)

    tmp_name_list = new_glob_node['name']
    orig_name_list = new_o_glob_node['name']
    for name in tmp_name_list:
        orig_name_list.append(name)
        db_iface.update_index(storage.DBInterface.FILE_INDEX,
                              'name', name, new_o_glob_node)
    new_o_glob_node['name'] = orig_name_list

    db_iface.create_relationship(new_o_glob_node, new_glob_node,
                                 storage.RelType.GLOB_OBJ_PREV)

    pvm.drop_l(db_iface, new_o_loc_node)
    return loc_node


@ActionMap.add('touch', True)
def touch_action(db_iface, proc_node, filename):
    '''Action that touches a named file.'''
    loc_node = pvm.get_l(db_iface, proc_node, "omega")

    glob_node = pvm.get_g(db_iface, loc_node, filename)

    _, new_loc_node = pvm.drop_g(db_iface, loc_node, glob_node)

    pvm.drop_l(db_iface, new_loc_node)
    return loc_node
