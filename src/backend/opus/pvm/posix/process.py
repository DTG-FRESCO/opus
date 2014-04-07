# -*- coding: utf-8 -*-
'''
PVM posix core package.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging

from opus import common_utils, pvm, storage
from opus.pvm.posix import actions, utils


def create_proc(storage_iface, pid, time_stamp):
    proc_node = storage_iface.create_node(storage.NodeType.PROCESS)

    # Set properties on the process node
    proc_node['pid'] = pid
    proc_node['timestamp'] = time_stamp

    return proc_node


def expand_proc(storage_iface, proc_node, pay):
    time_stamp = proc_node['timestamp']

    loc_node = actions.touch_action(storage_iface, proc_node, pay.exec_name)
    utils.set_link(storage_iface, loc_node, storage.LinkState.BIN)

    if pay.HasField('cwd'):
        utils.add_meta_to_proc(storage_iface, proc_node, "cwd", pay.cwd,
                               time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('cmd_line_args'):
        utils.add_meta_to_proc(storage_iface, proc_node, "cmd_args",
                               pay.cmd_line_args, time_stamp,
                               storage.RelType.OTHER_META)

    if pay.HasField('user_name'):
        utils.add_meta_to_proc(storage_iface, proc_node, "uid", pay.user_name,
                               time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('group_name'):
        utils.add_meta_to_proc(storage_iface, proc_node, "gid", pay.group_name,
                               time_stamp, storage.RelType.OTHER_META)

    for pair in pay.environment:
        utils.add_meta_to_proc(storage_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.ENV_META)

    for pair in pay.system_info:
        utils.add_meta_to_proc(storage_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.OTHER_META)

    for pair in pay.resource_limit:
        utils.add_meta_to_proc(storage_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.OTHER_META)


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


class ProcStateController(object):
    '''The ProcStateController handles process life cycles.'''
    proc_states = common_utils.enum(FORK=0,
                                    NORMAL=1,
                                    EXECED=2)

    proc_map = {}
    PIDMAP = {}

    @classmethod
    def proc_fork(cls, storage_iface, p_node, pid, timestamp):
        if pid not in cls.proc_map:
            cls.proc_map[pid] = cls.proc_states.FORK
            new_proc_node = create_proc(storage_iface, pid, timestamp)
            storage_iface.create_relationship(new_proc_node, p_node,
                                              storage.RelType.PROC_PARENT)
            clone_file_des(storage_iface, p_node, new_proc_node)
            cls.PIDMAP[pid] = new_proc_node['node_id']
            return True
        else:
            logging.warning("Process %d received invalid request to fork while"
                            " already in the %s state.",
                            pid,
                            cls.proc_states.enum_str(cls.proc_map[pid]))
            return False

    @classmethod
    def proc_startup(cls, storage_iface, hdr, pay):
        if hdr.pid not in cls.proc_map:
            cls.proc_map[hdr.pid] = cls.proc_states.NORMAL

            proc_node = create_proc(storage_iface, hdr.pid, hdr.timestamp)
            expand_proc(storage_iface, proc_node, pay)

            for i in range(3):
                pvm.get_l(storage_iface, proc_node, str(i))
        else:
            if cls.proc_map[hdr.pid] == cls.proc_states.FORK:
                cls.proc_map[hdr.pid] = cls.proc_states.NORMAL
                proc_node = storage_iface.get_node_by_id(cls.PIDMAP[hdr.pid])
                expand_proc(storage_iface, proc_node, pay)

            else:
                proc_node = create_proc(storage_iface, hdr.pid, hdr.timestamp)
                expand_proc(storage_iface, proc_node, pay)

                old_proc_node_id = cls.PIDMAP[hdr.pid]
                old_proc_node = storage_iface.get_node_by_id(old_proc_node_id)
                storage_iface.create_relationship(proc_node, old_proc_node,
                                                  storage.RelType.PROC_OBJ_PREV)
                clone_file_des(storage_iface, old_proc_node, proc_node)
        cls.PIDMAP[hdr.pid] = proc_node['node_id']
        return True

    @classmethod
    def proc_exec(cls, pid):
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
        if pid in cls.proc_map:
            if cls.proc_map[pid] == cls.proc_states.EXECED:
                cls.proc_map[pid] == cls.proc_states.NORMAL
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
        if pid in cls.PIDMAP:
            return cls.PIDMAP[pid]
        else:
            logging.error("Attempt to reffer to process %d which is not "
                          "present in the system.", pid)
            return None

    @classmethod
    def clear(cls):
        cls.PIDMAP = {}
        cls.proc_map = {}
