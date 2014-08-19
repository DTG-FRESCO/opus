# -*- coding: utf-8 -*-
'''
PVM posix core package.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import logging

from opus.pvm.posix import functions, process, utils
from opus import storage


def handle_function(db_iface, pid, msg):
    '''Handle a function call message from the given pid.'''
    db_iface.set_mono_time_for_msg(msg.begin_time)
    try:
        proc_node = db_iface.get_node_by_id(
            process.ProcStateController.resolve_process(pid))
        affected_node = functions.FuncController.call(msg.func_name,
                                                      db_iface,
                                                      proc_node,
                                                      msg)
        utils.add_event(db_iface, affected_node, msg)
    except functions.MissingMappingError as ex:
        logging.debug(ex)


def handle_bulk_functions(db_iface, pid, msg):
    '''Handle an aggregation message containing many messages.'''
    proc_node = db_iface.get_node_by_id(
        process.ProcStateController.resolve_process(pid))

    functions.process_aggregate_functions(db_iface,
                                          proc_node,
                                          msg.messages)


def handle_process(db_iface, hdr, pay):
    '''Handle a process startup message.'''
    db_iface.set_mono_time_for_msg(pay.start_time)
    process.ProcStateController.proc_startup(db_iface, hdr, pay)


def handle_disconnect(pid):
    '''Handle the disconnection of a process.'''
    process.ProcStateController.proc_discon(pid)


def handle_prefunc(pid, msg):
    '''Handle a pre-function call message.'''
    if "exec" in msg.msg_desc:
        process.ProcStateController.proc_exec(pid)


def handle_startup(db_iface, pay):
    '''Handle system startup.'''
    term_node = db_iface.create_node(storage.NodeType.TERM)
    term_node['reason'] = pay.reason
    term_node['downtime_start'] = pay.downtime_start
    term_node['downtime_end'] = pay.downtime_end


def handle_cleanup():
    '''Cleanup all PVM state'''
    process.ProcStateController.clear()
