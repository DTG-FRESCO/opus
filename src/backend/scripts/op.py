#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
OPUS command and control tool.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import argparse
import socket

from opus import cc_utils
from opus import cc_msg_pb2 as cc_msg


def exec_cmd(args):
    '''Execute command specified by args.'''
    host = args.host
    port = args.port

    conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    conn.connect((host, port))

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = args.cmd

    for k, val in vars(args).iteritems():
        if k not in ["host", "port", "cmd"]:
            arg = cmd.args.add()
            arg.key = k
            arg.value = str(val)

    cc_utils.send_cc_msg(conn, cmd)

    pay = cc_utils.recv_cc_msg(conn)

    if isinstance(pay, cc_msg.PSMessageRsp):
        print("Interposed Processes:\n\n"
              " Pid │ Thread Count\n"
              "═════╪══════════════")
        for psdat in pay.ps_data:
            print("%5u│%14u" % (psdat.pid, psdat.thread_count))
    else:
        print(pay.rsp_data)


def main():
    '''Parse command line arguments and execute resulting command.'''
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10101)

    sub_parsers = parser.add_subparsers(title="commands", dest="cmd")
    sub_parsers.add_parser("ps")

    kill_parser = sub_parsers.add_parser("kill")
    kill_parser.add_argument("pid", type=int)

    sub_parsers.add_parser("getan")

    setan_parser = sub_parsers.add_parser("setan")
    setan_parser.add_argument("new_an")

    sub_parsers.add_parser("shutdown")

    args = parser.parse_args()
    exec_cmd(args)

if __name__ == "__main__":
    main()
