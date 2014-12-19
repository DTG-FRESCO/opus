#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
OPUS environment and dependencies diff tool
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import cc_utils
from opus import cc_msg_pb2 as cc_msg

import os
import datetime
import argparse


def sync_send_message(args, msg):
    helper = cc_utils.CommandConnectionHelper(args.host, args.port)
    result = helper.make_request(msg)
    return result


def get_diff_input(cmd_args, result, prog_name):
    '''Get the diffs and display'''
    mapping_dict = {}
    for arg in result.state_mapping:
        mapping_dict[arg.key] = arg.value

    if not mapping_dict:
        return

    print("You can compare two executions based on ExecID")

    while True:
        exec_id1 = raw_input('Enter the first ExecID: ')
        if exec_id1 in mapping_dict:
            break
        print("%s is an invalid execution ID" % (exec_id1))

    while True:
        exec_id2 = raw_input('Enter the second ExecID: ')
        if exec_id2 == exec_id1:
            print("Cannot enter the same execution ID")
            continue
        if exec_id2 in mapping_dict:
            break
        print("%s is an invalid execution ID" % (exec_id2))


    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = "exec_qry_method"
    cmd.qry_method = "get_diffs"

    arg_list = [("node_id1", mapping_dict[exec_id1])]
    arg_list.append(("node_id2", mapping_dict[exec_id2]))
    arg_list.append(("prog_name", prog_name))

    for key, val in arg_list:
        arg = cmd.args.add()
        arg.key = key
        arg.value = val

    result = sync_send_message(cmd_args, cmd)
    if result.HasField("error"):
        print(result.error)
    else:
        print(result.rsp_data)


def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def make_query(args):
    prog_name = args.prog_name
    print("Getting executions for binary %s" % (prog_name))

    if os.path.isfile(prog_name):
        prog_name = os.path.abspath(prog_name)
        prog_name = os.path.realpath(prog_name)

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = "exec_qry_method"
    cmd.qry_method = "get_execs"
    arg = cmd.args.add()
    arg.key = "prog_name"
    arg.value = prog_name

    if args.dates is not None:
        arg1 = cmd.args.add()
        arg1.key = "start_date"
        arg1.value = args.dates[0].strftime("%s")

        arg2 = cmd.args.add()
        arg2.key = "end_date"
        arg2.value = args.dates[1].strftime("%s")

    result = sync_send_message(args, cmd)
    if result.HasField("error"):
        print(result.error)
        if result.HasField("rsp_data"):
            print(result.rsp_data)
    else:
        print(result.rsp_data)
        get_diff_input(args, result, prog_name)


def main():
    parser = argparse.ArgumentParser(description="This program shows the past" \
            " executions of a binary and allows the user"
            " to find the difference between two executions")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10101)
    parser.add_argument('--dates', nargs=2, metavar=('start_date','end_date'),
                            help='start_date and end_date in YYYY-MM-DD',
                            default=None,
                            type=valid_date)
    parser.add_argument("prog_name",
                help="Full path of the binary to be queried", type=str)

    args = parser.parse_args()
    make_query(args)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise
