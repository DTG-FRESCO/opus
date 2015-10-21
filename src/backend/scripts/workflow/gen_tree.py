#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Produces a Tree View of the workflow
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import argparse
import os
import subprocess
import sys

try:
    import opus.scripts.workflow_helper as wfh
except ImportError:
    print("Failed to locate OPUS libs, check your $PYTHONPATH"
          "and try again.")
    sys.exit(1)


printed_list = []
visited_list = []
bash_children = []

start_filters = ['/tmp/']
end_filters = ['.cls', '.aux', '.cache']
word_filters = ['matplotlib']


def check_filter(file_name):
    for f in start_filters:
        if file_name.startswith(f):
            return False
    for f in end_filters:
        if file_name.endswith(f):
            return False
    for w in word_filters:
        if w in file_name:
            return False
    return True


def check_f(f, dot_fh):
    if f in printed_list:
        return
    printed_list.append(f)
    dot_fh.write("    \"%s\" [label=\"%s\", color=palegreen];\n" %
                 (f, os.path.basename(f)))


def collapse_children(level, node_id, p_map, new_p_map, tkey=None):
    if node_id in visited_list:
        return
    visited_list.append(node_id)

    if len(p_map[node_id]['cmd_args']) > 0:
        if level == 1:  # User initiated command
            tkey = node_id
            if tkey not in bash_children:
                bash_children.append(tkey)

        if tkey is None:
            print("ERROR!! Top level key not present")
            return

        if tkey not in new_p_map:
            new_p_map[tkey] = {}
            new = new_p_map[tkey]
            old = p_map[node_id]
            new['pid'] = old['pid']
            new['cmd_args'] = old['cmd_args']
            new['read_files'] = old['read_files']
            new['write_files'] = old['write_files']
            new['read_write_files'] = old['read_write_files']
            new['executed_files'] = old['executed_files']
        else:
            new = new_p_map[tkey]
            old = p_map[node_id]
            new['read_files'].extend(old['read_files'])
            new['write_files'].extend(old['write_files'])
            new['read_write_files'].extend(old['read_write_files'])
            new['executed_files'].extend(old['executed_files'])

    # Recursively get data for children or execed processes
    if ('execed' in p_map[node_id] and
       (len(p_map[node_id]['execed']) > 0)):
        el = p_map[node_id]['execed']
        el.sort()
        for ni in el:
            collapse_children(level, ni, p_map, new_p_map, tkey)
    if ('forked' in p_map[node_id] and
       (len(p_map[node_id]['forked']) > 0)):
        fl = p_map[node_id]['forked']
        fl.sort()
        for ni in fl:
            collapse_children(level + 1, ni, p_map, new_p_map, tkey)


def collapse(p_map):
    level = 0
    new_p_map = {}
    for key in sorted(p_map):
        if key in visited_list:
            continue

        new_p_map[key] = p_map[key]
        if 'forked' in p_map[key]:
            fl = p_map[key]['forked']
            fl.sort()
            visited_list.append(key)
            for node_id in fl:
                collapse_children(level + 1, node_id, p_map, new_p_map)
            global bash_children
            if ("bash" in p_map[key]['cmd_args'] or
                "zsh" in p_map[key]['cmd_args']):
                new_p_map[key]['forked'] = bash_children
            bash_children = []
    return new_p_map


def print_node(node, dot_fh):
    proc_pid = node['pid']
    proc_cmd = node['cmd_args']
    dot_fh.write("    %d [label=\"%s\"];\n" % (proc_pid,
                                               proc_cmd[:80] +
                                               (proc_cmd[80:] and "...")))
    if len(node['read_files']) > 0:
        read_files = sorted(set(
            node['read_files']))
        for f in read_files:
            if check_filter(f) is False:
                continue
            check_f(f, dot_fh)
            dot_fh.write("    \"%s\" -> %d;\n" % (f, proc_pid))
    if len(node['write_files']) > 0:
        write_files = sorted(set(
            node['write_files']))
        for f in write_files:
            if check_filter(f) is False:
                continue
            check_f(f, dot_fh)
            dot_fh.write("    %d -> \"%s\";\n" % (proc_pid, f))
    if len(node['read_write_files']) > 0:
        read_write_files = sorted(set(
            node['read_write_files']))
        for f in read_write_files:
            if check_filter(f) is False:
                continue
            check_f(f, dot_fh)
            dot_fh.write("    \"%s\" -> %d;\n" % (f, proc_pid))
            dot_fh.write("    %d -> \"%s\";\n" % (proc_pid, f))
    if len(node['executed_files']) > 0:
        executed_files = sorted(set(
            node['executed_files']))
        for f in executed_files:
            if check_filter(f) is False:
                continue
            check_f(f, dot_fh)
            dot_fh.write("    \"%s\" -> %d;\n" % (f, proc_pid))


def print_recursive(node_id, proc_tree_map, dot_fh):
    proc_pid = proc_tree_map[node_id]['pid']
    if node_id in printed_list:
        return proc_pid
    printed_list.append(node_id)

    if len(proc_tree_map[node_id]['cmd_args']) > 0:
        print_node(proc_tree_map[node_id], dot_fh)

    if ('execed' in proc_tree_map[node_id] and
       (len(proc_tree_map[node_id]['execed']) > 0)):
        el = proc_tree_map[node_id]['execed']
        el.sort()
        for ni in el:
            pid = print_recursive(ni, proc_tree_map, dot_fh)
    if ('forked' in proc_tree_map[node_id] and
       (len(proc_tree_map[node_id]['forked']) > 0)):
        fl = proc_tree_map[node_id]['forked']
        fl.sort()
        for ni in fl:
            pid = print_recursive(ni, proc_tree_map, dot_fh)
            dot_fh.write("    %d -> %d;\n" % (proc_pid, pid))
    return proc_pid


def print_tree(p_map, dot_fh):

    dot_fh.write("digraph prov{"
                 "    graph [];"
                 "    node [style=filled,shape=box,color=grey];"
                 "    edge [arrowhead=vee];\n")

    for key in sorted(p_map):
        if key in printed_list:
            continue

        if 'forked' in p_map[key]:
            fl = p_map[key]['forked']
            if ('bash' not in p_map[key]['cmd_args'] and
                'zsh' not in p_map[key]['cmd_args']):
                dot_fh.write("    %d [label=\"%s\"];\n" %
                             (p_map[key]['pid'],
                              p_map[key]['cmd_args'][:80] +
                              (p_map[key]['cmd_args'][80:] and "...")))
            printed_list.append(key)
            for node_id in fl:
                pid = print_recursive(node_id, p_map, dot_fh)
                if ('bash' not in p_map[key]['cmd_args'] and
                    'zsh' not in p_map[key]['cmd_args']):
                    dot_fh.write("    %d -> %d;\n" % (p_map[key]['pid'], pid))
    dot_fh.write("}\n")


def main():
    parser = argparse.ArgumentParser(description="This program retrieves the "
                                     "workflow used to produce the queried "
                                     "file and generates a tree view of the "
                                     "workflow")

    args = wfh.parse_command_line(parser)
    proc_tree_map, _ = wfh.make_workflow_qry(args)

    if proc_tree_map is None:
        print("Could not retrieve process tree map")
        return

    new_proc_tree_map = collapse(proc_tree_map)

    xdot = subprocess.Popen(["xdot", "-"], stdin=subprocess.PIPE)

    print_tree(new_proc_tree_map, xdot.stdin)

    xdot.stdin.close()

    xdot.wait()

if __name__ == "__main__":
    main()
