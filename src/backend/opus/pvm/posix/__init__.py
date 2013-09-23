# -*- coding: utf-8 -*-
'''
PVM posix implementation package.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import logging


from opus import prov_db_pb2 as prov_db
from opus import pvm
from opus.pvm.posix import actions, functions, utils


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


def handle_function(tran, pid, msg):
    '''Handle a function call message from the given pid.'''
    try:
        affected_id = functions.FuncController.call(msg.func_name,
                                                    tran,
                                                    PIDMAP[pid],
                                                    msg)
        utils.add_event(tran, affected_id, msg)
    except functions.MissingMappingError as ex:
        logging.debug(ex)


def handle_process(tran, hdr, pay):
    '''Handle a process startup message.'''
    p_id = utils.process_from_startup(tran, (hdr, pay))

    l_id = actions.touch_action(tran, p_id, pay.exec_name)
    utils.set_rw_lnk(tran, l_id, prov_db.READ)

    p_obj = tran.get(p_id)
    if p_obj.pid in PIDMAP:
        old_p_id = PIDMAP[p_obj.pid]
        old_p_obj = tran.get(old_p_id)
        old_p_obj.next_version.id = p_id
        p_obj.prev_version.id = old_p_id
        utils.clone_file_des(tran, old_p_id, p_id)
    else:
        if pay.ppid in PIDMAP:
            par_id = PIDMAP[pay.ppid]
            par_obj = tran.get(par_id)
            p_obj.parent.id = par_id
            par_obj.child.add().id = p_id
            utils.clone_file_des(tran, par_id, p_id)
        else:
            for i in range(3):
                pvm.get_l(tran, p_id, str(i))
    PIDMAP[hdr.pid] = p_id
    DisconController.proc_create(p_obj.pid)


def handle_disconnect(pid):
    '''Handle the disconnection of a process.'''
    DisconController.proc_discon(pid)


def handle_prefunc(pid, msg):
    '''Handle a pre-function call message.'''
    if "exec" in msg.msg_desc:
        DisconController.proc_exec(pid)

def handle_startup(tran, pay):
    '''Handle system startup.'''
    t_id, t_obj = tran.create(prov_db.TERM)
    t_obj.reason = pay.reason
    t_obj.downtime_start = pay.downtime_start
    t_obj.downtime_end = pay.downtime_end

    cur_id_state = tran.id_state()

    for k in cur_id_state:
        kv_pair = t_obj.id_state.add()
        kv_pair.key = k
        kv_pair.value = cur_id_state[k]