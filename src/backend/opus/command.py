# -*- coding: utf-8 -*-
'''
Systems to control the back end. Allowing for activating and deactivating
subsystems and for sending commands to those subsystems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import errno
import logging
import random
import select
import socket
import threading
import traceback

from . import cc_utils, ipc
from .exception import CommandInterfaceStartupError


class CommandControl(object):
    '''Command and control core system.'''

    command_handlers = {}

    @classmethod
    def register_command_handler(cls, cmd):
        def wrap(func):
            cls.command_handlers[cmd] = func
            return func
        return wrap

    def __init__(self, daemon_manager, router,
                 listen_addr, listen_port,
                 whitelist_location=None):
        self.daemon_manager = daemon_manager
        self.node = ipc.Master(ident="CAC",
                               router=router)
        self.node.run_forever()
        self.running = False

        self.whitelist = []

        if whitelist_location is not None:
            try:
                with open(whitelist_location, "r") as white_file:
                    for line in white_file:
                        self.whitelist += [line]
            except IOError:
                logging.error("Failed to read specified whitelist file %s",
                              whitelist_location)
                raise CommandInterfaceStartupError(
                    "Failed to read whitelist.")

        self.host_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.host_sock.bind((listen_addr, listen_port))
        except IOError:
            logging.error("Failed to bind cmd socket on address %s port %d.",
                          listen_addr, listen_port)
            raise CommandInterfaceStartupError("Failed to bind socket.")
        self.host_sock.listen(10)

    def exec_cmd(self, msg):
        '''Executes a command message that it has recieved, producing a
        response message.'''

        try:
            if msg['cmd'] in self.command_handlers:
                return self.command_handlers[msg['cmd']](self, msg)
            else:
                return {"success": False, "msg": "Invalid command name."}
        except Exception as exe:  # pylint: disable=broad-except
            # Broad exception to catch all failures of CaC commands.
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

    def stop(self):
        if self.running:
            self.running = False

    def run(self):
        self.running = True
        while self.running:
            try:
                if select.select([self.host_sock], [], [], 2) == ([], [], []):
                    continue
            except IOError as exc:
                if exc.errno != errno.EINTR:
                    raise

            (new_conn, new_addr) = self.host_sock.accept()

            if self.whitelist and new_addr not in self.whitelist:
                new_conn.close()
                logging.info("Recieved connection from %s, dropped due"
                             " to not matching white list.", new_addr)
                continue

            pay = cc_utils.recv_cc_msg(new_conn)
            rsp = self.exec_cmd(pay)
            cc_utils.send_cc_msg(new_conn, rsp)


def _shutdown_inner(cac, drop):
    if cac.daemon_manager.stop_service(drop):
        cac.stop()
    else:
        handle_shutdown.shutdown_lock.release()


@CommandControl.register_command_handler("stop")
def handle_shutdown(cac, msg):
    if handle_shutdown.shutdown_lock.acquire(False):
        an_stat = cac.node.send("ANALYSER", {"cmd": "status"}).result()
        handle_shutdown.msg_count = an_stat['num_msgs']
        threading.Thread(target=_shutdown_inner,
                         kwargs={'cac': cac, 'drop': msg['drop_queue']}
                         ).start()
    return {"success": True, "msg_count": handle_shutdown.msg_count}
handle_shutdown.shutdown_lock = threading.Lock()


@CommandControl.register_command_handler("exec_qry_method")
def analyser(cac, msg):
    return cac.node.send("ANALYSER", msg).result()


@CommandControl.register_command_handler("status")
def handle_status(cac, _):
    rsp = {"success": True, 'analyser': {}, 'producer': {}, 'query': {}}

    # Analyser
    if cac.daemon_manager.analyser_ctl.is_alive():
        rsp['analyser']['status'] = "Alive"

        rq = cac.node.send("ANALYSER", {"cmd": "status"})

        rsp['analyser'].update(rq.result())
    else:
        rsp['analyser']['status'] = "Dead"

    # Producer
    if cac.daemon_manager.producer.is_alive():
        rsp['producer']['status'] = "Alive"
    else:
        rsp['producer']['status'] = "Dead"

    # Query Interface
    if hasattr(cac.daemon_manager, "query_interface"):
        if cac.daemon_manager.query_interface.is_alive():
            rsp['query']['status'] = "Alive"
        else:
            rsp['query']['status'] = "Dead"
    else:
        rsp['query']['status'] = "Not Present"

    return rsp


@CommandControl.register_command_handler("ps")
@CommandControl.register_command_handler("detach")
def producer(cac, msg):
    return cac.node.send("PRODUCER", msg).result()
