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

    filename = os.path.abspath(args.name)

    if(os.path.isdir(filename) or args.directory) and not args.file:
        pay = query_folder(helper, filename)
    else:
        pay = query_file(helper, filename)

    if pay.HasField("error"):
        print(pay.error)
    else:
        for row in pay.rows:
            for cell in row.cells:
                print(cell.value)


def query_file(helper, name):
    '''Performs a query returning the last command used on a file.'''
    print("Last command performed on %s:" % name)

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = "db_qry"

    arg = cmd.args.add()
    arg.key = "qry_str"
    arg.value = ("START g1=node:FILE_INDEX('name:" + name + "') "
                 "MATCH (g1)-[:GLOBAL_OBJ_PREV*0..]->(gn)-[r1:LOC_OBJ]->(l)"
                 "-[:PROC_OBJ]->(p)-[:OTHER_META]->(m) "
                 "WHERE m.name = 'cmd_args' AND r1.state in [3,4]"
                 "RETURN m.value ORDER BY p.timestamp LIMIT 1")

    return helper.make_request(cmd)


def query_folder(helper, name):
    '''Performs a query returning the last 5 commands used on a folder.'''
    print("Last 5 commands performed in %s:" % name)

    cmd = cc_msg.CmdCtlMessage()
    cmd.cmd_name = "db_qry"

    arg = cmd.args.add()
    arg.key = "qry_str"
    arg.value = ("START p=node(*) "
                 "MATCH (p)-[:OTHER_META]->()-[:META_PREV*0..]->(m),"
                 "      (p)-[:OTHER_META]->(m1) "
                 "WHERE m.name = 'cwd' AND m.value = '" + name + "' AND "
                 "m1.name = 'cmd_args' "
                 "RETURN m1.value ORDER BY p.timestamp LIMIT 5")

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
