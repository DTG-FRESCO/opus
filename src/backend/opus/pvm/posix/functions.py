# -*- coding: utf-8 -*-
'''
Contains all of the function mappings of the posix implementation. Controls the
association between posix functions and python code that implements their PVM
semantics.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import fcntl
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
from opus import storage


class MissingMappingError(utils.PVMException):
    '''Failed to find a mapping for a given function.'''
    def __init__(self):
        super(MissingMappingError, self).__init__(
            "Error: Failed to find a function mapping."
        )


def wrap_action(action, arg_map):
    '''Converts an item from the ActionMap into a lambda taking
    storage interface, process node and a msg.'''
    def fun(storage_iface, proc_node, msg):
        '''Wrapper internal. '''
        args = utils.parse_kvpair_list(msg.args)
        arg_set = {}
        for k, val in arg_map.items():
            if val[0] == "msg_arg":
                arg_set[k] = args[val[1]]
            elif val[0] == "ret_val":
                arg_set[k] = str(msg.ret_val)
            elif val[0] == "const":
                arg_set[k] = str(val[1])
        return actions.ActionMap.call(action, msg.error_num,
                                      storage_iface, proc_node, **arg_set)
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
def posix_fcloseall(storage_iface, proc_node, _):
    '''Implementation of fcloseall in PVM semantics.'''
    local_node_link_list = get_locals_from_process(proc_node)

    for (loc_node, rel_link) in local_node_link_list:
        glob_node_link_list = storage_iface.get_globals_from_local(loc_node)

        for (glob_node, rel_link) in glob_node_link_list:
            pvm.drop_g(storage_iface, loc_node, glob_node)
        pvm.drop_l(storage_iface, loc_node)

    return proc_node


@FuncController.dec('freopen')
def posix_freopen(storage_iface, proc_node, msg):
    '''Implementation of freopen in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)

    try:
        utils.proc_get_local(storage_iface, proc_node, args['stream'])
    except utils.NoMatchingLocalError:
        actions.close_action(msg.error_num, storage_iface,
                                proc_node, args['stream'])

    new_loc_node = actions.open_action(storage_iface, proc_node,
                                   args['filename'], str(msg.ret_val))
    return new_loc_node


@FuncController.dec('freopen64')
def posix_freopen64(storage_iface, proc_node, msg):
    '''Implementation of freopen64 in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    try:
        utils.proc_get_local(storage_iface, proc_node, args['stream'])
    except utils.NoMatchingLocalError:
        actions.close_action(msg.error_num, storage_iface, proc_node,
                                    args['stream'])
    new_loc_node = actions.open_action(storage_iface, proc_node,
                                    args['filename'], str(msg.ret_val))
    return new_loc_node


@FuncController.dec('fchmodat')
def posix_fchmodat():
    '''Implementation of fchmodat in PVM semantics.'''
    pass


@FuncController.dec('fchownat')
def posix_fchownat():
    '''Implementation of fchownat in PVM semantics.'''
    pass


@FuncController.dec('socket')
@utils.check_message_error_num
def posix_socket(storage_iface, proc_node, msg):
    '''Implementation of socket in PVM semantics.'''
    loc_node = pvm.get_l(storage_iface, proc_node, str(msg.ret_val))
    return loc_node


@FuncController.dec('accept')
@utils.check_message_error_num
def posix_accept(storage_iface, proc_node, msg):
    '''Implementation of accept in PVM semantics.'''
    loc_node = pvm.get_l(storage_iface, proc_node, str(msg.ret_val))
    return loc_node


@FuncController.dec('pipe')
@utils.check_message_error_num
def posix_pipe(storage_iface, proc_node, msg):
    '''Implementation of pipe in PVM semantics.'''
    return utils.process_rw_pair(storage_iface, proc_node, msg)


@FuncController.dec('pipe2')
@utils.check_message_error_num
def posix_pipe2(storage_iface, proc_node, msg):
    '''Implementation of pipe2 in PVM semantics.'''
    return utils.process_rw_pair(storage_iface, proc_node, msg)


@FuncController.dec('socketpair')
@utils.check_message_error_num
def posix_socketpair(storage_iface, proc_node, msg):
    '''Implementation of socketpair in PVM semantics.'''
    return utils.process_rw_pair(storage_iface, proc_node, msg)


@FuncController.dec('dup')
@utils.check_message_error_num
def posix_dup(socket_iface, proc_node, msg):
    '''Implementation of dup in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    old_fd = args['oldfd']
    new_fd = str(msg.ret_val)
    loc_node = utils.proc_get_local(storage_iface, proc_node, old_fd)
    utils.proc_dup_fd(storage_iface, proc_node, old_fd, new_fd)
    return loc_node


@FuncController.dec('dup2')
@utils.check_message_error_num
def posix_dup2(storage_iface, proc_node, msg):
    '''Implementation of dup2 in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    old_fd = args['oldfd']
    new_fd = args['newfd']
    loc_node = utils.proc_get_local(storage_iface, proc_node, old_fd)
    utils.proc_dup_fd(storage_iface, proc_node, old_fd, new_fd)
    return loc_node


@FuncController.dec('dup3')
@utils.check_message_error_num
def posix_dup3(storage_iface, proc_node, msg):
    '''Implementation of dup3 in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    old_fd = args['oldfd']
    new_fd = args['newfd']
    loc_node = utils.proc_get_local(storage_iface, proc_node, old_fd)
    utils.proc_dup_fd(storage_iface, proc_node, old_fd, new_fd)
    return loc_node


@FuncController.dec('link')
def posix_link(storage_iface, proc_node, msg):
    '''Implementation of link in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    return actions.link_action(storage_iface, proc_node,
                            args['path1'], args['path2'])


@FuncController.dec('rename')
def posix_rename(storage_iface, proc_node, msg):
    '''Implementation of rename in PVM semantics.'''
    # TODO(tb403): Fix to only use a single omega.
    args = utils.parse_kvpair_list(msg.args)
    dest_glob_node = storage_iface.get_latest_glob_version(args['newpath'])

    if dest_glob_node is not None:
        if storage_iface.is_glob_deleted(dest_glob_node) is False:
            actions.delete_action(storage_iface, proc_node, args['newpath'])
    loc_node = actions.link_action(storage_iface, proc_node,
                            args['oldpath'], args['newpath'])
    actions.delete_action(storage_iface, proc_node, args['oldpath'])
    return loc_node


@FuncController.dec('umask')
def posix_umask(storage_iface, proc_node, msg):
    '''Implementation of umask in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "file_mode_creation_mask",
                           args["mask"], msg.end_time)
    return proc_node


@FuncController.dec('popen')
@utils.check_message_error_num
def posix_popen(storage_iface, proc_node, msg):
    '''Implementation of popen in PVM semantics.'''
    loc_node = pvm.get_l(storage_iface, proc_node, str(msg.ret_val))
    return loc_node # TODO(tb403) properly implement pipes


@FuncController.dec('tmpfile')
@utils.check_message_error_num
def posix_tmpfile(storage_iface, proc_node, msg):
    '''Implementation of tmpfile in PVM semantics.'''
    loc_node = pvm.get_l(storage_iface, proc_node, str(msg.ret_val))
    return loc_node


@FuncController.dec('tmpfile64')
@utils.check_message_error_num
def posix_tmpfile64(storage_iface, proc_node, msg):
    '''Implementation of tmpfile64 in PVM semantics.'''
    loc_node = pvm.get_l(storage_iface, proc_node, str(msg.ret_val))
    return loc_node


@FuncController.dec('chdir')
@utils.check_message_error_num
def posix_chdir(storage_iface, proc_node, msg):
    '''Implementation of chdir in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "cwd",
                                args["path"], msg.end_time)
    return proc_node


@FuncController.dec('fchdir')
def posix_fchdir(storage_iface, proc_node, msg):
    '''Implementation of fchdir in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    try:
        loc_node = utils.proc_get_local(storage_iface, proc_node, args['fd'])
    except utils.NoMatchingLocalError:
        return proc_node

    if msg.error_num > 0:
        return loc_node

    glob_node_rel_list = storage_iface.get_globals_from_local(loc_node)
    if len(glob_node_link_list) == 0 or len(glob_node_link_list) > 1:
        return loc_node

    glob_node = glob_node_rel_list[0]
    name_list = storage_iface.get_property(glob_node, 'name')
    dir_name = name_list[0]

    utils.update_proc_meta(storage_iface, proc_node, "cwd",
                            dir_name, msg.end_time)
    return loc_node


@FuncController.dec('seteuid')
@utils.check_message_error_num
def posix_seteuid(storage_iface, proc_node, msg):
    '''Implementation of seteuid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "euid",
                            args["euid"], msg.end_time)
    return proc_node


@FuncController.dec('setegid')
@utils.check_message_error_num
def posix_setegid(storage_iface, proc_node, msg):
    '''Implementation of setegid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "egid",
                            args["egid"], msg.end_time)
    return proc_node


@FuncController.dec('setgid')
@utils.check_message_error_num
def posix_setgid(storage_iface, proc_node, msg):
    '''Implementation of setgid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "gid",
                            args["gid"], msg.end_time)
    return proc_node


@FuncController.dec('setreuid')
@utils.check_message_error_num
def posix_setreuid(storage_iface, proc_node, msg):
    '''Implementation of setreuid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "ruid",
                                args["ruid"], msg.end_time)
    utils.update_proc_meta(storage_iface, proc_node, "euid",
                                args["euid"], msg.end_time)
    return proc_node


@FuncController.dec('setregid')
@utils.check_message_error_num
def posix_setregid(storage_iface, proc_node, msg):
    '''Implementation of setregid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "rgid",
                                args["rgid"], msg.end_time)
    utils.update_proc_meta(storage_iface, proc_node, "egid",
                                args["egid"], msg.end_time)
    return proc_node


@FuncController.dec('setuid')
@utils.check_message_error_num
def posix_setuid(storage_iface, proc_node, msg):
    '''Implementation of setuid in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    utils.update_proc_meta(storage_iface, proc_node, "uid",
                                args["uid"], msg.end_time)
    return proc_node


@FuncController.dec('clearenv')
@utils.check_message_error_num
def posix_clearenv(storage_iface, proc_node, msg):
    '''Implementation of clearenv in PVM semantics.'''
    env_meta_list = storage_iface.get_proc_meta(proc_node,
                                storage.RelType.ENV_META)

    for meta_node, meta_rel in env_meta_list:
        new_meta_node = utils.new_meta(storage_iface, meta_node['name'],
                                        None, msg.end_time)
        storage_iface.create_relationship(new_meta_node, meta_node,
                                        storage.RelType.META_PREV)
        storage_iface.create_relationship(proc_node, new_meta_node,
                                        storage.RelType.ENV_META)
        storage_iface.delete_relationship(meta_rel)
    return proc_node


@FuncController.dec('putenv')
@utils.check_message_error_num
def posix_putenv(storage_iface, proc_node, msg):
    '''Implementation of putenv in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)

    parts = args['string'].split("=")
    if len(parts) == 2:
        env = (parts[0], parts[1], msg.end_time)
    else:
        env = (parts[0], None, msg.end_time)
    utils.process_put_env(storage_iface, proc_node, env, True)
    return proc_node


@FuncController.dec('setenv')
@utils.check_message_error_num
def posix_setenv(storage_iface, proc_node, msg):
    '''Implementation of setenv in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    env = (args['name'], args['value'], msg.end_time)
    utils.process_put_env(storage_iface, proc_node, env, args['overwrite'] > 0)
    return proc_node


@FuncController.dec('unsetenv')
@utils.check_message_error_num
def posix_unsetenv(storage_iface, proc_node, msg):
    '''Implementation of unsetenv in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    env = (args['name'], None, msg.end_time)
    utils.process_put_env(storage_iface, proc_node, env, True)
    return proc_node


@FuncController.dec('fcntl')
@utils.check_message_error_num
def posix_fcntl(storage_iface, proc_node, msg):
    '''Implementation of fnctl in PVM semantics.'''
    args = utils.parse_kvpair_list(msg.args)
    loc_node = utils.proc_get_local(storage_iface, proc_node, args['filedes'])

    if int(args['cmd']) == fcntl.F_DUPFD:
        utils.proc_dup_fd(storage_iface, proc_node, args['filedes'],
                            str(msg.ret_val))
    if int(args['cmd']) == fcntl.F_SETFD:
        if int(args['arg']) == fcntl.FD_CLOEXEC:
            utils.set_link(storage_iface, loc_node, storage.LinkState.CLOEXEC)
        else:
            utils.set_link(storage_iface, loc_node, storage.LinkState.NONE)

    return loc_node
