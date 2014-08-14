# -*- coding: utf-8 -*-
'''
Systems to control the back end. Allowing for activating and deactivating
subsystems and for sending commands to those subsystems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import logging
import jpype

from opus import cc_msg_pb2


class CommandControl(object):
    '''Command and control core system.'''

    command_handlers = {}

    @classmethod
    def register_command_handler(cls, cmd):
        def wrap(func):
            cls.command_handlers[cmd] = func
            return func
        return wrap

    def __init__(self, daemon_manager, prod_ctrl):
        self.daemon_manager = daemon_manager
        self.prod_ctrl = prod_ctrl
        self.cmd_if = None

    def set_interface(self, inter):
        '''Set the control systems interface.'''
        self.cmd_if = inter

    def exec_cmd(self, msg):
        '''Executes a command message that it has recieved, producing a
        response message.'''
        if msg.cmd_name in self.command_handlers:
            return self.command_handlers[msg.cmd_name](self, msg)
        else:
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            rsp.rsp_data = "Invalid command name."
            return rsp

    def run(self):
        '''Engages the systems processing loop.'''
        self.cmd_if.run()


@CommandControl.register_command_handler("getan")
def handle_getan(cac, _):
    rsp = cc_msg_pb2.CmdCtlMessageRsp()
    rsp.rsp_data = cac.daemon_manager.get_analyser()
    return rsp


@CommandControl.register_command_handler("setan")
def handle_setan(cac, msg):
    rsp = cc_msg_pb2.CmdCtlMessageRsp()
    new_an = None
    for arg in msg.args:
        if arg.key == "new_an":
            new_an = arg.value
    if new_an is None:
        rsp.rsp_data = "Invalid set of arguments for setan command."
    else:
        rsp.rsp_data = cac.daemon_manager.set_analyser(new_an)
    return rsp


@CommandControl.register_command_handler("shutdown")
def handle_shutdown(cac, _):
    rsp = cc_msg_pb2.CmdCtlMessageRsp()
    if cac.daemon_manager.stop_service():
        rsp.rsp_data = "Y"
    else:
        rsp.rsp_data = "N"
    return rsp


@CommandControl.register_command_handler("db_qry")
def handle_db_qry(cac, msg):
    rsp = cc_msg_pb2.QueryMessageRsp()
    qry_str = ""

    for arg in msg.args:
        if arg.key == "qry_str":
            qry_str = arg.value

    try:
        qry_data = cac.daemon_manager.analyser.db_iface.locked_query(qry_str)
    except jpype.JavaException as exc:
        logging.error(exc)
        rsp.error = "Failed to execute query sucessfully."
        return rsp

    try:
        keys = qry_data.keys()
        for row in qry_data:
            cur = rsp.rows.add()
            for key in keys:
                cell = cur.cells.add()
                cell.key = key
                cell.value = row[key]
    except TypeError as exc:
        pass

    return rsp


@CommandControl.register_command_handler("ps")
@CommandControl.register_command_handler("kill")
def forward_to_producer(cac, msg):
    cac.prod_ctrl.write(msg)
    return cac.prod_ctrl.read()
