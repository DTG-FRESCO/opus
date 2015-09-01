# -*- coding: utf-8 -*-
'''
Interfaces to the CommandControl system.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
import select
import socket

from . import cc_utils
from .exception import CommandInterfaceStartupError


class CommandInterface(object):
    '''Command and control interface base class.'''
    def __init__(self, command_control, *args, **kwargs):
        super(CommandInterface, self).__init__(*args, **kwargs)
        self.command_control = command_control

    def stop(self):
        '''Shuts down the main loop.'''
        raise NotImplementedError()

    def run(self):
        '''Causes the system to loop and process commands.'''
        raise NotImplementedError()


class TCPInterface(CommandInterface):
    '''TCP listening interface for command and control.'''
    def __init__(self, listen_addr, listen_port, whitelist_location=None,
                 *args, **kwargs):
        super(TCPInterface, self).__init__(*args, **kwargs)

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

    def stop(self):
        if self.running:
            self.running = False

    def run(self):
        self.running = True
        while self.running:
            if select.select([self.host_sock], [], [], 2) == ([], [], []):
                continue

            (new_conn, new_addr) = self.host_sock.accept()

            if self.whitelist and new_addr not in self.whitelist:
                new_conn.close()
                logging.info("Recieved connection from %s, dropped due"
                             " to not matching white list.", new_addr)
                continue

            pay = cc_utils.recv_cc_msg(new_conn)
            rsp = self.command_control.exec_cmd(pay)
            cc_utils.send_cc_msg(new_conn, rsp)
