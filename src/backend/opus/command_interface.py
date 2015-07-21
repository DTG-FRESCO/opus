# -*- coding: utf-8 -*-
'''
Interfaces to the CommandControl system.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
import md5
import random
import select
import socket

from . import cc_utils, common_utils


class CommandInterfaceStartupError(common_utils.OPUSException):
    '''Exception indicating that the command interface has failed to
    initialise.'''
    def __init__(self, *args, **kwargs):
        super(CommandInterfaceStartupError, self).__init__(*args, **kwargs)


class CommandInterface(object):
    '''Command and control interface base class.'''
    def __init__(self, command_control, *args, **kwargs):
        super(CommandInterface, self).__init__(*args, **kwargs)
        self.command_control = command_control

    def run(self):
        '''Causes the system to loop and process commands.'''
        raise NotImplementedError()


class TCPInterface(CommandInterface):
    '''TCP listening interface for command and control.'''
    def __init__(self, listen_addr, listen_port, whitelist_location=None,
                 *args, **kwargs):
        super(TCPInterface, self).__init__(*args, **kwargs)

        self.whitelist = []

        if whitelist_location is not None:
            try:
                with open(whitelist_location, "r") as white_file:
                    for line in white_file:
                        self.whitelist += [line]
            except IOError:
                logging.error("Failed to read specified whitelist file %s",
                              whitelist_location)
                raise CommandIntercfaceStartupError(
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

    def run(self):
        while True:
            select.select([self.host_sock], [], [])

            (new_conn, new_addr) = self.host_sock.accept()

            if self.whitelist and new_addr not in self.whitelist:
                new_conn.close()
                logging.info("Recieved connection from %s, dropped due"
                             " to not matching white list.", new_addr)
                continue

            pay = cc_utils.recv_cc_msg(new_conn)

            try:
                rsp = self.command_control.exec_cmd(pay)
            except Exception as exe:
                errorid = md5.new(str(random.getrandbits(128))).hexdigest()
                logging.error("Exception occurred processing command.\n"
                              "Errorid:{}\n"
                              "Command:\n{}\n"
                              "Exception:\n{}".format(errorid, pay, exe))
                rsp = {"success": False,
                       "msg": "Command failed due to an unhandled exception. "
                              "Errorid:{}".format(errorid)}

            cc_utils.send_cc_msg(new_conn, rsp)

            if pay['cmd'] == "stop" and rsp['success']:
                break
