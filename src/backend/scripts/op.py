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

def print_status_rsp(pay):
    '''Prints status response to stdout'''
    stat_str_table = {cc_msg.LIVE: "Alive",
                        cc_msg.DEAD: "Not running",
                        cc_msg.NOT_PRESENT: "Not present"}

    print("{0:<20} {1:<12}".format("Producer",
                            stat_str_table[pay.producer_status]))

    if pay.analyser_status.HasField("num_msgs"):
        num_msgs = pay.analyser_status.num_msgs
        print("{0:<20} {1:<12} {2:<20}".format("Analyser",
                            stat_str_table[pay.analyser_status.status],
                            "(" + str(num_msgs) + " msgs in queue)"))
    else:
        print("{0:<20} {1:<12}".format("Analyser",
                            stat_str_table[pay.analyser_status.status]))


    print("{0:<20} {1:<12}".format("Query Interface",
                            stat_str_table[pay.query_status]))


def exec_cmd(args):
    '''Execute command specified by args.'''

    helper = cc_utils.CommandConnectionHelper(args.host, args.port)

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = args.cmd

    for k, val in vars(args).iteritems():
        if k not in ["host", "port", "cmd"]:
            arg = cmd.args.add()
            arg.key = k
            arg.value = str(val)

    pay = helper.make_request(cmd)

    if isinstance(pay, cc_msg.PSMessageRsp):
        print("Interposed Processes:\n\n"
              " Pid │ Thread Count\n"
              "═════╪══════════════")
        for psdat in pay.ps_data:
            print("%5u│%14u" % (psdat.pid, psdat.thread_count))
    elif isinstance(pay, cc_msg.StatusMessageRsp):
        print_status_rsp(pay)
    else:
        print(pay.rsp_data)


def main():
    '''Parse command line arguments and execute resulting command.'''
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10101)

    sub_parsers = parser.add_subparsers(title="commands", dest="cmd")
    sub_parsers.add_parser("ps")

    sub_parsers.add_parser("status")

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
