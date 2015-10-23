#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Helper module for workflow scripts
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import cc_utils, common_utils as cu

import cPickle as pickle
import time
import datetime


def get_cur_time():
    return datetime.datetime.fromtimestamp(time.time()).strftime(
        '%d%m%Y-%H:%M:%S')


def parse_command_line(parser):
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=10101)
    parser.add_argument("file_name",
                        help="Full path of the file to be queried", type=str)
    parser.add_argument('--regen', action='store_true', default=False)
    parser.add_argument('--dest',
                        help="Destination directory for files produced by the "
                        "program",
                        type=str, default=".")

    args = parser.parse_args()
    return args


def sync_send_message(args, msg):
    helper = cc_utils.CommandConnectionHelper(args.host, args.port)
    result = helper.make_request(msg)
    return result


def make_workflow_qry(args):
    file_name = cu.canonicalise_file_path(args.file_name)
    proc_tree_map = None

    regen = False
    if args.regen:
        regen = args.regen

    cmd = {'cmd': 'exec_qry_method',
           'qry_method': 'gen_workflow',
           'qry_args': {'file_name': file_name,
                        'regen': regen}}

    result = sync_send_message(args, cmd)
    if not result['success']:
        print(result['msg'])
    else:
        if 'proc_tree_map' in result:
            proc_tree_map = pickle.loads(str(result['proc_tree_map']))

    return proc_tree_map, file_name
