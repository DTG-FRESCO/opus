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


def query_file(helper, filename, limit):
    filename = os.path.abspath(filename)

    if os.path.isfile(filename):
        filename = os.path.realpath(filename)

    if limit is None:
        limit = "1"

    return query(helper, filename, limit, False)


def query_folder(helper, filename, limit):
    if filename[-1] == "/":
        # Trailing slash causes backend query to return no results.
        filename = filename[:-1]

    if limit is None:
        limit = "5"

    return query(helper, filename, limit, True)


def exec_query(args):
    '''Execute command specified by args.'''

    helper = cc_utils.CommandConnectionHelper(args.host, args.port)

    filename = args.name

    if args.directory or (os.path.isdir(filename) and not args.file):
        result = query_folder(helper, filename, args.limit)
    elif args.file or (os.path.isfile(filename) and not args.directory):
        result = query_file(helper, filename, args.limit)
    else:
        print("Path does not exist in the filesystem. Please pass either"
              "-F or -D as appropriate.")
        return

    print_query_result(result, args.trunc)


def print_query_result(result, trunc):
    if not result['success']:
        print(result['msg'])
    else:
        for record in result['data']:
            if trunc:
                cmd = record['cmd'][:75] + (record['cmd'][75:] and '..')
            else:
                cmd = record['cmd']
            print("{ts} - {cmd}".format(ts=record['ts'], cmd=cmd))


def query(helper, name, limit, folder=False):
    if folder:
        connective = "in"
    else:
        connective = "on"

    if limit == "1":
        print("Last command performed {} {}:".format(connective, name))
    else:
        print("Last {} commands performed {} {}:".format(limit,
                                                         connective,
                                                         name))

    return helper.make_request({'cmd': "exec_qry_method",
                                'qry_method': "query_folder"
                                              if folder else
                                              "query_file",
                                "qry_args": {'name': name,
                                             'limit': limit}})


def main():
    '''Parse command line arguments and execute resulting command.'''
    parser = argparse.ArgumentParser(
        description="Shows the last command(s) that were run on a file or in "
                    "a directory.")

    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10101)

    group = parser.add_mutually_exclusive_group()
    group.add_argument("-D", "--directory", action="store_true",
                       help="Force the program to treat NAME as a directory.")
    group.add_argument("-F", "--file", action="store_true",
                       help="Force the program to treat NAME as a file.")

    parser.add_argument("-L", "--limit",
                        help="Number of results to return, defaults to 1 for "
                        "file queries and 5 for directory queries.")

    parser.add_argument("--no-trunc", action="store_false", dest="trunc",
                        help="Disable truncation of long commands.")

    parser.add_argument("name", type=str,
                        help="The file or directory you wish to query the "
                        "history for.")

    args = parser.parse_args()
    exec_query(args)

if __name__ == "__main__":
    main()
