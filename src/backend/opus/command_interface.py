# -*- coding: utf-8 -*-
'''
Interfaces to the CommandControl system.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import cmd
import logging
import re
import readline  # pylint: disable=W0611
import select
import socket

from opus import cc_msg_pb2, cc_utils, common_utils


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

            rsp = self.command_control.exec_cmd(pay)

            cc_utils.send_cc_msg(new_conn, rsp)

            if pay.cmd_name == "shutdown" and rsp.rsp_data == "Y":
                break


class CMDInterface(CommandInterface, cmd.Cmd):  # pylint: disable=R0904
    '''Command line interface for command and control module.'''
    def __init__(self, *args, **kwargs):
        super(CMDInterface, self).__init__(*args, **kwargs)
        cmd.Cmd.__init__(self)
        self.prompt = ">"

    def do_ps(self, args):
        """List all processes currently being interposed by the OPUS system.

        Arguments: None"""
        msg = cc_msg_pb2.CmdCtlMessage()
        msg.cmd_name = "ps"

        rsp = self.command_control.exec_cmd(msg)
        print("Interposed Processes:\n\n"
              " Pid │ Thread Count\n"
              "═════╪══════════════")
        for psdat in rsp.ps_data:
            print("%5u│%14u" % (psdat.pid, psdat.thread_count))

    def do_kill(self, args):
        """Deactivate interposition for the specified process.

        Arguments: pid"""
        msg = cc_msg_pb2.CmdCtlMessage()
        msg.cmd_name = "kill"
        arg = msg.args.add()
        arg.key = "pid"
        if re.match(r"\A\d*\Z", args) is None:
            print("Error: Kill takes a single number as an argument.")
            return False
        arg.value = args

        rsp = self.command_control.exec_cmd(msg)

        print(rsp.rsp_data)

    def do_getan(self, args):
        """Return the current analyser.

        Arguments: None"""
        msg = cc_msg_pb2.CmdCtlMessage()
        msg.cmd_name = "getan"

        rsp = self.command_control.exec_cmd(msg)

        print(rsp.rsp_data)

    def do_setan(self, args):
        """Switch the current analyser for the specified one.

        Arguments: new_analyser_type"""
        msg = cc_msg_pb2.CmdCtlMessage()
        msg.cmd_name = "setan"
        arg = msg.args.add()
        arg.key = "new_an"
        arg.value = args

        rsp = self.command_control.exec_cmd(msg)

        print(rsp.rsp_data)

    def do_shutdown(self, args):
        """Shutdown the system.

        Arguments: None"""
        msg = cc_msg_pb2.CmdCtlMessage()
        msg.cmd_name = "shutdown"
        print("Shutting down...")
        rsp = self.command_control.exec_cmd(msg)

        if rsp.rsp_data == "Y":
            print("System successfully shutdown.")
            return True
        else:
            print("Error: failed to shutdown correctly.")
            return False

    def run(self):
        self.cmdloop()
