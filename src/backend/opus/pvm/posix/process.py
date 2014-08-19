# -*- coding: utf-8 -*-
'''
PVM posix core package.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging

from opus import common_utils, pvm, storage, traversal
from opus.pvm.posix import actions, utils


def create_proc(db_iface, pid, time_stamp):
    '''Create a process node with the given pid and timestamp.'''
    proc_node = db_iface.create_node(storage.NodeType.PROCESS)

    # Set properties on the process node
    proc_node['pid'] = pid
    proc_node['timestamp'] = time_stamp

    return proc_node


def expand_proc(db_iface, proc_node, pay):
    '''Expand a process node with a binary relation and with meta data
    from a given startup message payload 'pay'.'''
    time_stamp = proc_node['timestamp']

    loc_node = actions.touch_action(db_iface, proc_node, pay.exec_name)
    utils.set_link(db_iface, loc_node, storage.LinkState.BIN)

    if pay.HasField('cwd'):
        utils.add_meta_to_proc(db_iface, proc_node, "cwd", pay.cwd,
                               time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('cmd_line_args'):
        utils.add_meta_to_proc(db_iface, proc_node, "cmd_args",
                               pay.cmd_line_args, time_stamp,
                               storage.RelType.OTHER_META)

    if pay.HasField('user_name'):
        utils.add_meta_to_proc(db_iface, proc_node, "uid", pay.user_name,
                               time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('group_name'):
        utils.add_meta_to_proc(db_iface, proc_node, "gid", pay.group_name,
                               time_stamp, storage.RelType.OTHER_META)

    for pair in pay.environment:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.ENV_META)

    for pair in pay.system_info:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.OTHER_META)

    for pair in pay.resource_limit:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.OTHER_META)


def clone_file_des(db_iface, old_proc_node, new_proc_node):
    '''Clones the file descriptors of old_proc_node to new_proc_node
    using the CoT mechanism.'''
    loc_node_link_list = traversal.get_locals_from_process(db_iface,
                                                           old_proc_node)
    for (loc_node, rel_link) in loc_node_link_list:
        if rel_link['state'] in [storage.LinkState.CLOSED,
                                 storage.LinkState.CLOEXEC]:
            continue
        new_loc_node = pvm.get_l(db_iface, new_proc_node, loc_node['name'])

        # Find the newest valid version of the global object
        glob_node = traversal.get_glob_latest_version(db_iface, loc_node)
        if glob_node is not None:
            new_glob_node = pvm.version_global(db_iface, glob_node)
            pvm.bind(db_iface, new_loc_node, new_glob_node)


class ProcStateController(object):
    '''The ProcStateController handles process life cycles.'''
    proc_states = common_utils.enum(FORK=0,
                                    NORMAL=1,
                                    EXECED=2)

    proc_map = {}
    PIDMAP = {}

    @classmethod
    def proc_fork(cls, db_iface, p_node, pid, timestamp):
        '''Handle a process 'p_node' forking a child with pid 'pid' at time
        'timestamp'. Returns True if this is successful and False if this
        violates the state system.'''
        if pid not in cls.proc_map:
            cls.proc_map[pid] = cls.proc_states.FORK
            new_proc_node = create_proc(db_iface, pid, timestamp)
            db_iface.create_relationship(new_proc_node, p_node,
                                         storage.RelType.PROC_PARENT)
            clone_file_des(db_iface, p_node, new_proc_node)
            cls.PIDMAP[pid] = new_proc_node['node_id']
            return True
        else:
            logging.warning("Process %d received invalid request to fork while"
                            " already in the %s state.",
                            pid,
                            cls.proc_states.enum_str(cls.proc_map[pid]))
            return False

    @classmethod
    def proc_startup(cls, db_iface, hdr, pay):
        '''Handles a process startup message arriving.'''
        if hdr.pid not in cls.proc_map:
            cls.proc_map[hdr.pid] = cls.proc_states.NORMAL

            proc_node = create_proc(db_iface, hdr.pid, hdr.timestamp)
            expand_proc(db_iface, proc_node, pay)

            for i in range(3):
                pvm.get_l(db_iface, proc_node, str(i))
        else:
            if cls.proc_map[hdr.pid] == cls.proc_states.FORK:
                cls.proc_map[hdr.pid] = cls.proc_states.NORMAL
                proc_node = db_iface.get_node_by_id(cls.PIDMAP[hdr.pid])
                expand_proc(db_iface, proc_node, pay)

            else:
                proc_node = create_proc(db_iface, hdr.pid, hdr.timestamp)
                expand_proc(db_iface, proc_node, pay)

                old_proc_node_id = cls.PIDMAP[hdr.pid]
                old_proc_node = db_iface.get_node_by_id(old_proc_node_id)
                db_iface.create_relationship(proc_node, old_proc_node,
                                             storage.RelType.PROC_OBJ_PREV)
                clone_file_des(db_iface, old_proc_node, proc_node)
        cls.PIDMAP[hdr.pid] = proc_node['node_id']
        return True

    @classmethod
    def proc_exec(cls, pid):
        '''Handles a process with pid 'pid' executing an exec function.
        Returns True if this succeeds and returns False if this violates
        the state system.'''
        if pid in cls.proc_map:
            if cls.proc_map[pid] == cls.proc_states.NORMAL:
                cls.proc_map[pid] = cls.proc_states.EXECED
                return True
            else:
                logging.warning("Process %d received invalid request to "
                                "exec while already in the %s state.",
                                pid,
                                cls.proc_states.enum_str(cls.proc_map[pid]))
                return False
        else:
            logging.warning("Unknown process %d attempted to exec.",
                            pid)
            return False

    @classmethod
    def proc_discon(cls, pid):
        '''Handles a process with pid 'pid' disconnecting from the backend.
        Returns True unless the process is unknown to the system, in which
        case it returns False.'''
        if pid in cls.proc_map:
            if cls.proc_map[pid] == cls.proc_states.EXECED:
                cls.proc_map[pid] = cls.proc_states.NORMAL
                return True
            else:
                del cls.PIDMAP[pid]
                del cls.proc_map[pid]
        else:
            logging.warning("Unknown process %d disconnected.",
                            pid)
            return False

    @classmethod
    def resolve_process(cls, pid):
        '''Attempts to resolve an ID for a process with pid 'pid'. Logs an
        error and returns None in the event that the pid supplied is
        unknown.'''
        if pid in cls.PIDMAP:
            return cls.PIDMAP[pid]
        else:
            logging.error("Attempt to reffer to process %d which is not "
                          "present in the system.", pid)
            return None

    @classmethod
    def clear(cls):
        '''Clears up the classes data structures.'''
        cls.PIDMAP = {}
        cls.proc_map = {}
