# -*- coding: utf-8 -*-
'''
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import cmd
import re
import readline

from opus import cc_msg_pb2


class CommandControl(object):
    def __init__(self, daemon_manager, prod_ctrl):
        self.daemon_manager = daemon_manager
        self.prod_ctrl = prod_ctrl
        self.cmd_if = None

    def set_interface(self, inter):
        self.cmd_if = inter

    def exec_cmd(self, cmd):
        if cmd.cmd_name == "getan":
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            rsp.rsp_data = self.daemon_manager.get_analyser()
            return rsp
        elif cmd.cmd_name == "setan":
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            new_an = None
            for arg in cmd.args:
                if arg.key == "new_an":
                    new_an = arg.value
            if new_an is None:
                rsp.rsp_data = "Invalid set of arguments for setan command."
            else:
                rsp.rsp_data = self.daemon_manager.set_analyser(new_an)
            return rsp
        elif cmd.cmd_name == "shutdown":
            rsp = cc_msg_pb2.CmdCtlMessageRsp()
            if self.daemon_manager.stop_service():
                rsp.rsp_data = "Y"
            else:
                rsp.rsp_data = "N"
            return rsp
        else:
            self.prod_ctrl.write(cmd)
            return self.prod_ctrl.read()

    def run(self):
        self.cmd_if.run()


class CommandInterface(object):
    def __init__(self, command_control, *args, **kwargs):
        super(CommandInterface, self).__init__(*args, **kwargs)
        self.command_control = command_control

    def run(self):
        raise NotImplementedError()


class TCPInterface(CommandInterface):
    pass


class CMDInterface(CommandInterface, cmd.Cmd):
    def __init__(self, *args, **kwargs):
        super(CMDInterface, self).__init__(*args, **kwargs)
        cmd.Cmd.__init__(self)
        self.prompt = ">"

    def do_ps(self, args):
        """List all processes currently being interposed by the OPUS system.

        Arguments: None"""
        cmd = cc_msg_pb2.CmdCtlMessage()
        cmd.cmd_name = "ps"

        rsp = self.command_control.exec_cmd(cmd)
        print("Interposed Processes:\n\n"
              " Pid │ Thread Count\n"
              "═════╪══════════════")
        for psdat in rsp.ps_data:
            print("%5u│%14u" % (psdat.pid, psdat.thread_count))
        
    def do_kill(self, args):
        """Deactivate interposition for the specified process.

        Arguments: pid"""
        cmd = cc_msg_pb2.CmdCtlMessage()
        cmd.cmd_name = "kill"
        arg = cmd.args.add()
        arg.key = "pid"
        if re.match("\A\d*\Z", args) is None:
            print("Error: Kill takes a single number as an argument.")
            return False
        arg.value = args

        rsp = self.command_control.exec_cmd(cmd)

        print(rsp.rsp_data)

    def do_getan(self, args):
        """Return the current analyser.

        Arguments: None"""
        cmd = cc_msg_pb2.CmdCtlMessage()
        cmd.cmd_name = "getan"

        rsp = self.command_control.exec_cmd(cmd)

        print(rsp.rsp_data)

    def do_setan(self, args):
        """Switch the current analyser for the specified one.

        Arguments: new_analyser_type"""
        cmd = cc_msg_pb2.CmdCtlMessage()
        cmd.cmd_name = "setan"
        arg = cmd.args.add()
        arg.key = "new_an"
        arg.value = args

        rsp = self.command_control.exec_cmd(cmd)

        print(rsp.rsp_data)

    def do_shutdown(self, args):
        """Shutdown the system.

        Arguments: None"""
        cmd = cc_msg_pb2.CmdCtlMessage()
        cmd.cmd_name = "shutdown"
        print("Shutting down...")
        rsp = self.command_control.exec_cmd(cmd)

        if rsp.rsp_data == "Y":
            print("System successfully shutdown.")
            return True
        else:
            print("Error: failed to shutdown correctly.")
            return False

    def run(self):
        self.cmdloop()
