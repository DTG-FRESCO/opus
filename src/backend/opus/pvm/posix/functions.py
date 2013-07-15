# -*- coding: utf-8 -*-
'''
Contains all of the function mappings of the posix implementation. Controls the
association between posix functions and python code that implements their PVM
semantics.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import logging
import sys


try:
    import yaml
except ImportError:
    print("YAML module is not present!")
    print("Please install the PyYAML module.")
    sys.exit(1)


from opus import pvm
from opus.pvm.posix import actions, utils 


class MissingMappingError(utils.PVMException):
    '''Failed to find a mapping for a given function.'''
    def __init__(self):
        super(MissingMappingError, self).__init__(
                                    "Error: Failed to find a function mapping.")


def wrap_action(action, arg_map):
    '''Converts an item from the ActionMap into a lambda taking tran, p_id and
    a msg.'''
    def fun(tran, p_id, msg):
        '''Wrapper internal. '''
        args = utils.parse_kvpair_list(msg.args)
        arg_set = {}
        for k,v in arg_map.items():
            if v[0] == "msg_arg":
                arg_set[k] = args[v[1]]
            elif v[0] == "ret_val":
                arg_set[k] = str(msg.ret_val)
            elif v[0] == "const":
                arg_set[k] = str(v[1])
        return actions.ActionMap.call(action, msg.error_num,
                                      tran, p_id, **arg_set)
    return fun


class FuncController(object):
    '''Mapping for function names to definitions.'''
    funcs = {}

    @classmethod
    def load(cls, func_file):
        '''Loads a YAML action specification from func_file.'''
        try:
            with open(func_file, "rt") as conf:
                data = yaml.safe_load(conf)
                for key in data:
                    cls.register(key, wrap_action(**data[key]))
        except IOError:
            logging.error("Failed to read in config file.")
            raise

    @classmethod
    def register(cls, name, func):
        '''Register func with key name.'''
        cls.funcs[name] = func

    @classmethod
    def call(cls, name, *args):
        '''Calls the method associated with name with any subsequent
        arguments.'''
        if name in cls.funcs:
            return cls.funcs[name](*args)
        else:
            logging.error("Failed to find mapping for function %s.", name)
            raise MissingMappingError()

    @classmethod
    def dec(cls, name):
        '''Declares the wrapped function as representing the given name.'''
        def wrapper(fun):
            '''Decorator internals.'''
            FuncController.register(name, fun)
            return fun
        return wrapper


FuncController.load("opus/pvm/posix/pvm.yaml")


@FuncController.dec('fcloseall')
@utils.check_message_error_num
def posix_fcloseall(tran, p_id, _):
    '''Implementation of fcloseall in PVM semantics.'''
    p_obj = tran.get(p_id)
    for l_lnk in p_obj.local_object:
        l_id = l_lnk.id
        l_obj = tran.get(l_id)
        for lnk in l_obj.file_object:
            pvm.drop_g(tran, l_id, lnk.id)
        pvm.drop_l(tran, l_id)

    return p_id


@FuncController.dec('freopen')
def posix_freopen(tran, p_id, msg):
    '''Implementation of freopen in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    try:
        utils.proc_get_local(tran, p_id, args['stream'])
    except utils.NoMatchingLocalError:
        actions.close_action(tran, p_id, args['stream'])
    new_l_id = actions.open_action(tran, p_id,
                                   args['filename'], str(msg.ret_val))
    return new_l_id

@FuncController.dec('freopen64')
def posix_freopen64(tran, p_id, msg):
    '''Implementation of freopen64 in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    try:
        utils.proc_get_local(tran, p_id, args['stream'])
    except utils.NoMatchingLocalError:
        actions.close_action(tran, p_id, args['stream'])
    new_l_id = actions.open_action(tran, p_id,
                                   args['filename'], str(msg.ret_val))
    return new_l_id


@FuncController.dec('fchmodat')
def posix_fchmodat():
    '''Implementation of fchmodat in PVM semantics.'''
    pass


@FuncController.dec('fchownat')
def posix_fchownat():
    '''Implementation of fchownat in PVM semantics.'''
    pass


@FuncController.dec('dup')
@utils.check_message_error_num
def posix_dup(tran, p_id, msg):
    '''Implementation of dup in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    old_fd = args['oldfd']
    new_fd = msg.ret_val
    i_id = utils.proc_get_local(tran, p_id, old_fd)
    utils.proc_dup_fd(tran, p_id, old_fd, new_fd)
    return i_id


@FuncController.dec('dup2')
@utils.check_message_error_num
def posix_dup2(tran, p_id, msg):
    '''Implementation of dup2 in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    old_fd = args['oldfd']
    new_fd = args['newfd']
    i_id = utils.proc_get_local(tran, p_id, old_fd)
    utils.proc_dup_fd(tran, p_id, old_fd, new_fd)
    return i_id


@FuncController.dec('dup3')
@utils.check_message_error_num
def posix_dup3(tran, p_id, msg):
    '''Implementation of dup3 in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    old_fd = args['oldfd']
    new_fd = args['newfd']
    i_id = utils.proc_get_local(tran, p_id, old_fd)
    utils.proc_dup_fd(tran, p_id, old_fd, new_fd)
    return i_id


@FuncController.dec('link')
def posix_link(tran, p_id, msg):
    '''Implementation of link in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    return actions.link_action(tran, p_id, msg, args['path1'], args['path2'])


@FuncController.dec('rename')
def posix_rename(tran, p_id, msg):
    '''Implementation of rename in PVM semantics.'''
    #TODO: Fix to only use a single omega.
    args = utils.parse_kvpair_list(msg.args)
    if tran.name_get(args['newpath']) is not None:
        actions.delete_action(tran, p_id, args['newpath'])
    l_id = actions.link_action(tran, p_id, args['oldpath'], args['newpath'])
    actions.delete_action(tran, p_id, args['oldpath'])
    return l_id


@FuncController.dec('umask')
def posix_umask(tran, p_id, msg):
    '''Implementation of umask in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "file_mode_creation_mask",
                           args["mask"], msg.end_time)
    return p_id


@FuncController.dec('popen')
@utils.check_message_error_num
def posix_popen(tran, p_id, msg):
    '''Implementation of popen in PVM semantics.'''
    l_id = pvm.get_l(tran, p_id, str(msg.ret_val))
    return l_id #TODO properly implement pipes


@FuncController.dec('tmpfile')
@utils.check_message_error_num
def posix_tmpfile(tran, p_id, msg):
    '''Implementation of tmpfile in PVM semantics.'''
    l_id = pvm.get_l(tran, p_id, str(msg.ret_val))
    return l_id


@FuncController.dec('tmpfile64')
@utils.check_message_error_num
def posix_tmpfile64(tran, p_id, msg):
    '''Implementation of tmpfile64 in PVM semantics.'''
    l_id = pvm.get_l(tran, p_id, str(msg.ret_val))
    return l_id


@FuncController.dec('chdir')
@utils.check_message_error_num
def posix_chdir(tran, p_id, msg):
    '''Implementation of chdir in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "cwd", args["path"], msg.end_time)
    return p_id


@FuncController.dec('fchdir')
def posix_fchdir(tran, p_id, msg):
    '''Implementation of fchdir in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    try:
        l_id = utils.proc_get_local(tran, p_id, args['fd'])
    except utils.NoMatchingLocalError:
        return p_id

    if msg.error_num > 0:
        return l_id

    l_obj = tran.get(l_id)
    if len(l_obj.file_object) < 1 or len(l_obj.file_object) > 1:
        return l_id

    g_obj = tran.get(l_obj.file_object[0].id)
    dir_name = g_obj.name[0]

    utils.update_proc_meta(tran, p_id, "cwd", dir_name, msg.end_time)
    return l_id


@FuncController.dec('seteuid')
@utils.check_message_error_num
def posix_seteuid(tran, p_id, msg):
    '''Implementation of seteuid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "euid", args["euid"], msg.end_time)
    return p_id


@FuncController.dec('setegid')
@utils.check_message_error_num
def posix_setegid(tran, p_id, msg):
    '''Implementation of setegid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "egid", args["egid"], msg.end_time)
    return p_id


@FuncController.dec('setgid')
@utils.check_message_error_num
def posix_setgid(tran, p_id, msg):
    '''Implementation of setgid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "gid", args["gid"], msg.end_time)
    return p_id


@FuncController.dec('setreuid')
@utils.check_message_error_num
def posix_setreuid(tran, p_id, msg):
    '''Implementation of setreuid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "ruid", args["ruid"], msg.end_time)
    utils.update_proc_meta(tran, p_id, "euid", args["euid"], msg.end_time)
    return p_id


@FuncController.dec('setregid')
@utils.check_message_error_num
def posix_setregid(tran, p_id, msg):
    '''Implementation of setregid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "rgid", args["rgid"], msg.end_time)
    utils.update_proc_meta(tran, p_id, "egid", args["egid"], msg.end_time)
    return p_id


@FuncController.dec('setuid')
@utils.check_message_error_num
def posix_setuid(tran, p_id, msg):
    '''Implementation of setuid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(tran, p_id, "uid", args["uid"], msg.end_time)
    return p_id


@FuncController.dec('clearenv')
@utils.check_message_error_num
def posix_clearenv(tran, p_id, msg):
    '''Implementation of clearenv in PVM semantics.'''
    p_obj = tran.get(p_id)
    for meta in p_obj.env:
        old_m_id = meta.id
        old_m_obj = tran.get(old_m_id)
        m_id = utils.new_meta(tran, old_m_obj.name, None, msg.end_time)
        m_obj = tran.get(m_id)
        m_obj.prev_version.id = old_m_id
        meta.id = m_id
    return p_id


@FuncController.dec('putenv')
@utils.check_message_error_num
def posix_putenv(tran, p_id, msg):
    '''Implementation of putenv in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)

    parts = args['string'].split("=")
    if len(parts) == 2:
        env = (parts[0], parts[1], msg.end_time)
    else:
        env = (parts[0], None, msg.end_time)
    utils.process_put_env(tran, p_id, env, True)
    return p_id


@FuncController.dec('setenv')
@utils.check_message_error_num
def posix_setenv(tran, p_id, msg):
    '''Implementation of setenv in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    env = (args['name'], args['value'], msg.end_time)
    utils.process_put_env(tran, p_id, env, args['overwrite'] > 0)
    return p_id


@FuncController.dec('unsetenv')
@utils.check_message_error_num
def posix_unsetenv(tran, p_id, msg):
    '''Implementation of unsetenv in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    env = (args['name'], None, msg.end_time)
    utils.process_put_env(tran, p_id, env, True)
    return p_id
