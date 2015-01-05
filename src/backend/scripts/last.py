#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
OPUS last tool.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import argparse
import os
import os.path

from opus import cc_utils
from opus import cc_msg_pb2 as cc_msg


def exec_query(args):
    '''Execute command specified by args.'''

    helper = cc_utils.CommandConnectionHelper(args.host, args.port)

    filename = args.name
    if os.path.isfile(filename):
        filename = os.path.abspath(args.name)
        filename = os.path.realpath(filename)

    if(os.path.isdir(filename) or args.directory) and not args.file:
        result = query_folder(helper, filename)
    else:
        result = query_file(helper, filename)

    if result.HasField("error"):
        print(result.error)
    else:
        print(result.rsp_data)


def query_file(helper, name):
    '''Performs a query returning the last command used on a file.'''
    print("Last command performed on %s:" % name)

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = "exec_qry_method"
    cmd.qry_method = "query_file"

    arg = cmd.args.add()
    arg.key = "name"
    arg.value = name
    return helper.make_request(cmd)


def query_folder(helper, name):
    '''Performs a query returning the last 5 commands used on a folder.'''
    print("Last 5 commands performed in %s:" % name)

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = "exec_qry_method"
    cmd.qry_method = "query_folder"

    arg = cmd.args.add()
    arg.key = "name"
    arg.value = name
    return helper.make_request(cmd)


def main():
    '''Parse command line arguments and execute resulting command.'''
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10101)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-D", "--directory", action="store_true",
                       help="Force the program to treat NAME as a directory.")
    group.add_argument("-F", "--file", action="store_true",
                       help="Force the program to treat NAME as a file.")

    parser.add_argument("name", type=str)

    args = parser.parse_args()
    exec_query(args)

if __name__ == "__main__":
    main()
