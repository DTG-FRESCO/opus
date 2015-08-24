# -*- coding: utf-8 -*-
'''
Systems to control the back end. Allowing for activating and deactivating
subsystems and for sending commands to those subsystems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
import random
import traceback

from . import query


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

        try:
            if msg['cmd'] in self.command_handlers:
                return self.command_handlers[msg['cmd']](self, msg)
            else:
                return {"success": False, "msg": "Invalid command name."}
        except Exception as exe:
            errorid = hex(random.getrandbits(128))[2:-1]
            stack_trace = traceback.format_exc()
            logging.error("Exception occurred processing command.\n"
                          "Errorid: %s\n"
                          "Command:\n%s\n"
                          "Exception:\n%s\n"
                          "Stack Trace:\n%s\n", errorid, msg, exe, stack_trace)
            rsp = {"success": False,
                   "msg": "Errorid: {}".format(errorid)}
            return rsp

    def run(self):
        '''Engages the systems processing loop.'''
        self.cmd_if.run()


@CommandControl.register_command_handler("getan")
def handle_getan(cac, _):
    return {"success": True,
            "msg": cac.daemon_manager.get_analyser()}


@CommandControl.register_command_handler("setan")
def handle_setan(cac, msg):
    if "new_an" not in msg:
        return {"success": False,
                "msg": "Invalid set of arguments for setan command."}
    else:
        return {"success": True,
                "msg": cac.daemon_manager.set_analyser(msg['new_an'])}


@CommandControl.register_command_handler("stop")
def handle_shutdown(cac, _):
    return {"success": cac.daemon_manager.stop_service()}


@CommandControl.register_command_handler("exec_qry_method")
def handle_exec_qry_method(cac, msg):
    db_iface = cac.daemon_manager.analyser.db_iface
    return query.ClientQueryControl.exec_method(db_iface, msg)


@CommandControl.register_command_handler("status")
def handle_status(cac, _):
    rsp = {"success": True, 'analyser': {}, 'producer': {}, 'query': {}}

    # Analyser
    if cac.daemon_manager.analyser.isAlive():
        rsp['analyser']['status'] = "Alive"

        try:
            analyser = cac.daemon_manager.analyser
            num_msgs = analyser.event_orderer.get_queue_size()
            rsp['analyser']['num_msgs'] = num_msgs
        except AttributeError:
            pass  # Analyser not an ordering analyser
    else:
        rsp['analyser']['status'] = "Dead"

    # Producer
    if cac.daemon_manager.producer.isAlive():
        rsp['producer']['status'] = "Alive"
    else:
        rsp['producer']['status'] = "Dead"

    # Query Interface
    if hasattr(cac.daemon_manager, "query_interface"):
        if cac.daemon_manager.query_interface.isAlive():
            rsp['query']['status'] = "Alive"
        else:
            rsp['query']['status'] = "Dead"
    else:
        rsp['query']['status'] = "Not Present"

    return rsp


@CommandControl.register_command_handler("ps")
@CommandControl.register_command_handler("detach")
def forward_to_producer(cac, msg):
    cac.prod_ctrl.write(msg)
    return cac.prod_ctrl.read()
