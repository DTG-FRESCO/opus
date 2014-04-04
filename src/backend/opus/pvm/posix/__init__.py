# -*- coding: utf-8 -*-
'''
PVM posix implementation package.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import logging

from opus import pvm
from opus.pvm.posix import actions, functions, utils
from opus import storage


# Mapping of pid to most recent DB id.
PIDMAP = {}


class DisconController(object):
    '''The DisconController handles process disconnection.'''
    dis_map = {}

    @classmethod
    def proc_create(cls, pid):
        '''Process created - If it is not in the disconnection map, add it.'''
        if pid not in cls.dis_map:
            cls.dis_map[pid] = False

    @classmethod
    def proc_exec(cls, pid):
        '''Process exec - Flag the process as being able to disconnect without
        removal from the PIDMAP.'''
        cls.dis_map[pid] = True

    @classmethod
    def proc_discon(cls, pid):
        '''Process disconnection - If the process is flagged, clear the flag.
        Otherwise remove it from the PIDMAP and the disconnection map.'''
        if cls.dis_map[pid]:
            cls.dis_map[pid] = False
        else:
            del PIDMAP[pid]
            del cls.dis_map[pid]

    @classmethod
    def clear(cls):
        '''Clear the contents of the disconnection map.'''
        cls.dis_map = {}


def handle_function(storage_iface, pid, msg):
    '''Handle a function call message from the given pid.'''
    try:
        proc_node = storage_iface.get_node_by_id(PIDMAP[pid])
        affected_node = functions.FuncController.call(msg.func_name,
                                                    storage_iface,
                                                    proc_node,
                                                    msg)
        utils.add_event(storage_iface, affected_node, msg)
    except functions.MissingMappingError as ex:
        logging.debug(ex)


def handle_process(storage_iface, hdr, pay):
    '''Handle a process startup message.'''
    proc_node = utils.process_from_startup(storage_iface, (hdr, pay))

    loc_node = actions.touch_action(storage_iface, proc_node, pay.exec_name)
    utils.set_link(storage_iface, loc_node, storage.LinkState.BIN)

    pid = proc_node['pid']
    if pid in PIDMAP: # Exec operation
        old_proc_node_id = PIDMAP[pid]
        old_proc_node = storage_iface.get_node_by_id(old_proc_node_id)
        storage_iface.create_relationship(proc_node, old_proc_node,
                                    storage.RelType.PROC_OBJ_PREV)
        utils.clone_file_des(storage_iface, old_proc_node, proc_node)
    else: # Fork and vfork
        if pay.ppid in PIDMAP:
            parent_proc_node_id = PIDMAP[pay.ppid]
            parent_proc_node = storage_iface.get_node_by_id(parent_proc_node_id)
            storage_iface.create_relationship(proc_node, parent_proc_node,
                                        storage.RelType.PROC_PARENT)
            utils.clone_file_des(storage_iface, parent_proc_node, proc_node)
        else:
            for i in range(3):
                pvm.get_l(storage_iface, proc_node, str(i))
    PIDMAP[hdr.pid] = proc_node['node_id']
    DisconController.proc_create(pid)


def handle_disconnect(pid):
    '''Handle the disconnection of a process.'''
    DisconController.proc_discon(pid)


def handle_prefunc(pid, msg):
    '''Handle a pre-function call message.'''
    if "exec" in msg.msg_desc:
        DisconController.proc_exec(pid)


def handle_startup(storage_iface, pay):
    '''Handle system startup.'''
    term_node = storage_iface.create_node(storage.NodeType.TERM)
    term_node['reason'] = pay.reason
    term_node['downtime_start'] = pay.downtime_start
    term_node['downtime_end'] = pay.downtime_end
