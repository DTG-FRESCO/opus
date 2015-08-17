#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Generates EPSRC report
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import argparse
import datetime
import os
import sys

try:
    from termcolor import colored
except ImportError as exe:
    print(exe.message)
    sys.exit(1)

try:
    import opus.scripts.workflow_helper as wfh
except ImportError:
    print("Failed to locate OPUS libs, check your $PYTHONPATH"
          "and try again.")
    sys.exit(1)


visited_list = []


def get_date_time_str(sys_time):
    return datetime.datetime.fromtimestamp(sys_time).strftime(
        '%Y-%m-%d %H:%M:%S')


def get_first_level(level, node_id, proc_tree_map,
                    script_file, current_dir):
    if node_id in visited_list:
        return
    visited_list.append(node_id)

    if len(proc_tree_map[node_id]['cmd_args']) > 0:
        # NOTE: Indicates commands run by used from command prompt.
        if level == 1:
            cwd = proc_tree_map[node_id]['cwd']
            if current_dir != cwd:
                current_dir = cwd
                script_file.write("cd " + current_dir + "\n")
            script_file.write(proc_tree_map[node_id]['cmd_args'])
            script_file.write("\n")

    if 'execed' in proc_tree_map[node_id]:
        el = proc_tree_map[node_id]['execed']
        el.sort()
        for ni in el:
            get_first_level(level, ni, proc_tree_map,
                            script_file, current_dir)
    elif 'forked' in proc_tree_map[node_id]:
        fl = proc_tree_map[node_id]['forked']
        fl.sort()
        for ni in fl:
            get_first_level(level + 1, ni, proc_tree_map,
                            script_file, current_dir)


def scriptise(proc_tree_map, script_file):
    level = 0
    current_dir = None
    for key in sorted(proc_tree_map):
        if key in visited_list:
            continue

        if 'forked' in proc_tree_map[key]:
            fl = proc_tree_map[key]['forked']
            fl.sort()
            date_time_str = get_date_time_str(
                proc_tree_map[key]['sys_time'])
            script_file.write("\n")
            script_file.write("# Commands from session at " +
                              date_time_str + "\n")

            cwd = proc_tree_map[key]['cwd']
            if current_dir != cwd:
                current_dir = cwd
                script_file.write("cd " + current_dir + "\n")

            visited_list.append(key)
            for node_id in fl:
                get_first_level(level + 1, node_id, proc_tree_map,
                                script_file, current_dir)


def main():
    parser = argparse.ArgumentParser(description="This program retrieves the "
                                     "workflow used to produce the queried "
                                     "file and generates a script to "
                                     "reproduce the file")

    args = wfh.parse_command_line(parser)
    proc_tree_map, _ = wfh.make_workflow_qry(args)

    if proc_tree_map is None:
        print("Could not retrieve process tree map")
        return

    cur_time = wfh.get_cur_time()
    script_name = os.path.join(args.dest, "workflow." + cur_time + ".sh")
    script_file = open(script_name, 'w')
    script_file.write("#!/bin/bash\n")

    desc = ("# This is an auto generated script.\n"
            "# The script produces the file:\n"
            "#    " + args.file_name + "\n")
    script_file.write(desc + "\n")

    script_file.write("set -e\n")
    script_file.write("set -x\n")
    scriptise(proc_tree_map, script_file)
    script_file.close()

    print("\nSuccessfully generated " +
          colored(script_name, 'green') +
          " from workflow")

if __name__ == "__main__":
    main()
