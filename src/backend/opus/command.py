# -*- coding: utf-8 -*-
'''
Systems to control the back end. Allowing for activating and deactivating
subsystems and for sending commands to those subsystems.
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


class CommandControl(object):
    '''Command and control core system.'''
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
        if msg.cmd_name == "getan":
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            rsp.rsp_data = self.daemon_manager.get_analyser()
            return rsp
        elif msg.cmd_name == "setan":
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            new_an = None
            for arg in msg.args:
                if arg.key == "new_an":
                    new_an = arg.value
            if new_an is None:
                rsp.rsp_data = "Invalid set of arguments for setan command."
            else:
                rsp.rsp_data = self.daemon_manager.set_analyser(new_an)
            return rsp
        elif msg.cmd_name == "shutdown":
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            if self.daemon_manager.stop_service():
                rsp.rsp_data = "Y"
            else:
                rsp.rsp_data = "N"
            return rsp
        else:
            self.prod_ctrl.write(msg)
            return self.prod_ctrl.read()

    def run(self):
        '''Engages the systems processing loop.'''
        self.cmd_if.run()


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
                raise CommandInterfaceStartupError("Failed to read whitelist.")

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


class CMDInterface(CommandInterface, cmd.Cmd):
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
        if re.match("\A\d*\Z", args) is None:
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
