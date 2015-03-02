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
    except utils.NoMatchingLocalError as e:
        # Add the event to the process
        utils.add_event(db_iface, proc_node, msg)
        logging.error(e)


def handle_bulk_functions(db_iface, pid, msg):
    '''Handle an aggregation message containing many messages.'''
    proc_node = db_iface.get_node_by_id(
        process.ProcStateController.resolve_process(pid))

    functions.process_aggregate_functions(db_iface,
                                          proc_node,
                                          msg.messages)


def handle_process(db_iface, hdr, pay, opus_lite):
    '''Handle a process startup message.'''
    db_iface.set_mono_time_for_msg(pay.start_time)
    process.ProcStateController.proc_startup(db_iface, hdr, pay, opus_lite)


def handle_disconnect(db_iface, pid):
    '''Handle the disconnection of a process.'''
    process.ProcStateController.proc_discon(db_iface, pid)


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


def handle_libinfo(db_iface, pid, pay):
    '''Handle for libinfo message'''
    proc_node = db_iface.get_node_by_id(
        process.ProcStateController.resolve_process(pid))

    time_stamp = proc_node['timestamp']
    for pair in pay.library:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                                time_stamp, storage.RelType.LIB_META)
