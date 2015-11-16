#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
OPUS environment and dependencies diff tool
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import argparse
import datetime
import os
import sys
import textwrap

from opus import common_utils as cu

try:
    import prettytable
except ImportError as exe:
    print(exe.message)
    sys.exit(1)

try:
    from opus import cc_utils
except ImportError:
    print("Failed to locate OPUS libs, check your $PYTHONPATH"
          "and try again.")
    sys.exit(1)


def sync_send_message(args, msg):
    helper = cc_utils.CommandConnectionHelper(args.server)
    result = helper.make_request(msg)
    return result


def print_diff(diff):
    if diff['added']:
        print("Added:")
        added = prettytable.PrettyTable(["Key", "Value"])
        added.align["key"] = "l"
        added.padding_width = 1
        added.align["Value"] = "l"
        for elem in diff['added']:
            added.add_row([elem['name'], textwrap.fill(elem['value'], 50)])
        print(added)

    if diff['removed']:
        print("Removed:")
        removed = prettytable.PrettyTable(["Key", "Value"])
        removed.align["key"] = "l"
        removed.padding_width = 1
        removed.align["Value"] = "l"
        for elem in diff['removed']:
            removed.add_row([elem['name'], textwrap.fill(elem['value'], 50)])
        print(removed)

    if diff['changed']:
        print("Changed:")
        changed = prettytable.PrettyTable(["Key", "From", "To"])
        changed.align["key"] = "l"
        changed.padding_width = 1
        changed.align["From"] = "l"
        changed.align["To"] = "l"
        for elem in diff['changed']:
            changed.add_row([elem['name'],
                             textwrap.fill(elem['from'], 50),
                             textwrap.fill(elem['to'], 50)])
        print(changed)


def get_diff_input(cmd_args, result, prog_name):
    '''Get the diffs and display'''
    print("You can compare two executions based on ExecID")
    mapping_dict = result['mapping']

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

    result = sync_send_message(
        cmd_args,
        {'cmd': 'exec_qry_method',
         'qry_method': 'get_diffs',
         'qry_args': {'node_id1': mapping_dict[exec_id1],
                      'node_id2': mapping_dict[exec_id2],
                      'prog_name': prog_name}})
    if not result['success']:
        print(result['msg'])
    else:
        if len(result['bin_mods']):
            print("Modifications to binary \"%s\":" % (prog_name))
            mod_hist = prettytable.PrettyTable(["Modified By", "Modified At"])
            mod_hist.align["Modified By"] = "l"
            for res in result['bin_mods']:
                mod_hist.add_row([textwrap.fill(res['prog'], 40),
                                  res['date']])
            print(mod_hist)

        print("Differences in Resource limits, command line and user "
              "information:")
        print_diff(result['other_meta'])

        print("Differences in Environment variables:")
        print_diff(result['env_meta'])

        print("Differences in libraries linked by program:")
        print_diff(result['lib_meta'])


def valid_date(s):
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        msg = "Not a valid date: '{0}'.".format(s)
        raise argparse.ArgumentTypeError(msg)


def make_query(args):
    prog_name = cu.canonicalise_file_path(args.prog_name)
    print("Getting executions for binary %s" % (prog_name))

    if os.path.isfile(prog_name):
        prog_name = os.path.abspath(prog_name)
        prog_name = os.path.realpath(prog_name)

    cmd = {'cmd': 'exec_qry_method',
           'qry_method': 'get_execs',
           'qry_args': {'prog_name': prog_name}}

    if args.dates is not None:
        cmd['qry_args']['start_date'] = args.dates[0].strftime("%s")
        cmd['qry_args']['end_date'] = args.dates[1].strftime("%s")

    result = sync_send_message(args, cmd)
    if not result['success']:
        print(result['msg'])
    else:
        exec_hist = prettytable.PrettyTable(["ExecID",
                                             "Binary",
                                             "PID",
                                             "Date",
                                             "Command"])
        exec_hist.align["ExecID"] = "l"
        exec_hist.align["Binary"] = "l"
        exec_hist.align["Command"] = "l"
        for record in result['data']:
            exec_hist.add_row([record['exec_id'],
                               textwrap.fill(record['prog_name'], 40),
                               record['pid'],
                               record['date'],
                               textwrap.fill(record['cmd_line'], 40)])
        print(exec_hist)
        get_diff_input(args, result, prog_name)


def main():
    parser = argparse.ArgumentParser(description="This program shows the past"
                                     " executions of a binary and allows the"
                                     " user to find the difference between two"
                                     " executions")
    parser.add_argument("--server", default="tcp://localhost:10101")
    parser.add_argument('--dates', nargs=2, metavar=('start_date', 'end_date'),
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
