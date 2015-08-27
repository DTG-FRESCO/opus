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
import sys

try:
    from opus import cc_utils
except ImportError:
    print("Failed to locate OPUS libs, check your $PYTHONPATH"
          "and try again.")
    sys.exit(1)


def exec_query(args):
    '''Execute command specified by args.'''

    helper = cc_utils.CommandConnectionHelper(args.host, args.port)

    filename = args.name

    if args.directory or (os.path.isdir(filename) and not args.file):
        if filename[-1] == "/":
            # Trailing slash causes backend query to return no results.
            filename = filename[:-1]

        result = query_folder(helper, filename, args.limit)
    elif args.file or (os.path.isfile(filename) and not args.directory):
        filename = os.path.abspath(filename)

        if os.path.isfile(filename):
            filename = os.path.realpath(filename)

        result = query_file(helper, filename)
    else:
        print("Path does not exist in the filesystem. Please pass either"
              "-F or -D as appropriate.")
        return

    if not result['success']:
        print(result['msg'])
    else:
        for record in result['data']:
            if args.trunc:
                cmd = record['cmd'][:75] + (record['cmd'][75:] and '..')
            else:
                cmd = record['cmd']
            print("{ts} - {cmd}".format(ts=record['ts'], cmd=cmd))


def query_file(helper, name):
    '''Performs a query returning the last command used on a file.'''
    print("Last command performed on %s:" % name)

    return helper.make_request({'cmd': "exec_qry_method",
                                'qry_method': "query_file",
                                "qry_args": {'name': name}})


def query_folder(helper, name, limit):
    '''Performs a query returning the last 5 commands used on a folder.'''
    print("Last {} commands performed in {}:".format(limit, name))

    return helper.make_request({'cmd': "exec_qry_method",
                                'qry_method': "query_folder",
                                "qry_args": {'name': name,
                                             'limit': limit}})


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

    parser.add_argument("-L", "--limit", type=int, default=5,
                        help="Number of results to return for directory "
                        "queries.")

    parser.add_argument("--no-trunc", action="store_false", dest="trunc",
                        help="Disable truncation of long commands.")

    parser.add_argument("name", type=str)

    args = parser.parse_args()
    exec_query(args)

if __name__ == "__main__":
    main()
