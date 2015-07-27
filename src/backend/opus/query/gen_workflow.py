#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Retrieves workflow
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from . import client_query
from .. import storage

import os
import datetime
import cPickle as pickle
import hashlib
import logging


action_dict = {0: 'None', 1: 'Copy On Touch', 2: 'Read', 3: 'Write',
               4: 'ReadWrite', 5: 'Close', 6: 'Delete', 7: 'Exec',
               8: 'CoE', 9: 'Close on Exec', 10: 'Inactive'}

start_filters = ['/etc/', '/lib/', '/var/', '/dev/', '/usr/', '.sh_history',
                 '.bashrc', '/run', '/bin', '/sbin', '/proc', '/opt']
end_filters = ['.sh_history', '.bashrc', 'logilab_common-0.61.0-nspkg.pth',
               '.cache', '.config']
dir_filters = ['.matplotlib']


class GlobData:
    proc_list = []
    file_hist_list = []
    visited_list = []
    printed_list = []  # NOTE: not needed
    queried_file = ""
    queried_file_last_modified_time = 0

    @staticmethod
    def clear_data():
        del GlobData.proc_list[:]
        del GlobData.file_hist_list[:]
        del GlobData.visited_list[:]
        del GlobData.printed_list[:]
        GlobData.queried_file = ""
        GlobData.queried_file_last_modified_time = 0

# Algorithm:
# 1. Get the process that wrote to the file.
# 2. Get files read, written or executed by that process
# 3. Get parent/prev process. Do step 2 for that process.
#    If no more parents/prevs go to step 4.
# 4. For each file (rwx) repeat from step 1.


def get_date_time_str(sys_time):
    return datetime.datetime.fromtimestamp(sys_time).strftime(
        '%Y-%m-%d %H:%M:%S')


def update_last_modified_time(sys_time):
    if sys_time > GlobData.queried_file_last_modified_time:
        GlobData.queried_file_last_modified_time = sys_time


def check_filter(glob_node):
    if not glob_node.has_key('name'):
        return False
    name = glob_node['name'][0]
    for f in start_filters:
        if name.startswith(f):
            return False
    for f in end_filters:
        if name.endswith(f):
            return False
    for f in dir_filters:
        if f in name:
            return False
    return True


def get_command_args(proc_node):
    for tmp_rel in proc_node.OTHER_META.outgoing:
        if tmp_rel.end['name'] != "cmd_args":
            continue
        cmd_args_node = tmp_rel.end
        return cmd_args_node['value']


def get_cwd(proc_node):
    for tmp_rel in proc_node.OTHER_META.outgoing:
        if tmp_rel.end['name'] != "cwd":
            continue
        cwd = tmp_rel.end
        return cwd['value']


def get_meta(link_type):
    name_value_map = {}
    for tmp_rel in link_type.outgoing:
        name_value_map[tmp_rel.end['name']] = tmp_rel.end['value']
    return name_value_map


def descend_down_proc_tree(db_iface, proc_node, proc_tree_map):
    '''Recursively descends down the process hierarchy and finds
    files written, read or executed'''
    if proc_node.PROC_PARENT.incoming:
        for tmp_rel in proc_node.PROC_PARENT.incoming:
            child_proc_node = tmp_rel.start
            descend_down_proc_tree(db_iface, child_proc_node, proc_tree_map)
    if proc_node.PROC_OBJ_PREV.incoming:
        for tmp_rel in proc_node.PROC_OBJ_PREV.incoming:
            child_proc_node = tmp_rel.start
            descend_down_proc_tree(db_iface, child_proc_node, proc_tree_map)

    find_files_read_and_written_by_process(db_iface, proc_node, proc_tree_map)


def add_file(glob_node, lineage_list, file_list):
    lineage_list.append(glob_node)
    if glob_node.has_key('name'):
        if glob_node['name'][0] not in file_list:
            file_list.append(glob_node['name'][0])


def find_files_read_and_written_by_process(db_iface, proc_node, proc_tree_map):
    if (proc_node.id in GlobData.proc_list or
       proc_node['sys_time'] > GlobData.queried_file_last_modified_time):
        return

    GlobData.proc_list.append(proc_node.id)

    lineage_list = []
    read_files = []
    write_files = []
    executed_files = []
    read_write_files = []
    cmd_args = get_command_args(proc_node)
    cwd = get_cwd(proc_node)
    sys_meta = get_meta(proc_node.OTHER_META)
    env_meta = get_meta(proc_node.ENV_META)
    lib_meta = get_meta(proc_node.LIB_META)

    rows = db_iface.locked_query(
        "START proc_node=node(" + str(proc_node.id) + ") "
        "MATCH proc_node<-[:PROC_OBJ]-loc_node, "
        "loc_node<-[rel:LOC_OBJ]-glob_node "
        "WHERE rel.state in [{r},{w},{rw},{b}] "
        "RETURN glob_node, rel "
        "ORDER BY glob_node.node_id desc",
        r=storage.LinkState.READ,
        w=storage.LinkState.WRITE,
        rw=storage.LinkState.RaW,
        b=storage.LinkState.BIN)
    for row in rows:
        glob_node = row['glob_node']
        rel = row['rel']

        if check_filter(glob_node) is False:
            continue

        if rel['state'] == storage.LinkState.READ:
            add_file(glob_node, lineage_list, read_files)
        elif rel['state'] == storage.LinkState.WRITE:
            add_file(glob_node, lineage_list, write_files)
        elif rel['state'] == storage.LinkState.RaW:
            add_file(glob_node, lineage_list, read_write_files)
        elif rel['state'] == storage.LinkState.BIN:
            add_file(glob_node, lineage_list, executed_files)

    # TODO: Change this to add new record and update existing record
    # store_proc_tree_map(proc_node.id, ....)

    if proc_node.id not in proc_tree_map:
        proc_tree_map[proc_node.id] = {'forked': [], 'execed': []}
    proc_tree_map[proc_node.id].update({'pid': proc_node['pid'],
                                        'sys_time': proc_node['sys_time'],
                                        'cwd': cwd,
                                        'cmd_args': cmd_args,
                                        'sys_meta': sys_meta,
                                        'env_meta': env_meta,
                                        'lib_meta': lib_meta,
                                        'write_files': write_files,
                                        'read_files': read_files,
                                        'read_write_files': read_write_files,
                                        'executed_files': executed_files})

    # TODO: Change this to traverse up
    if proc_node.PROC_PARENT.outgoing:
        for r1 in proc_node.PROC_PARENT.outgoing:
            if r1.end.id not in proc_tree_map:
                proc_tree_map[r1.end.id] = {'pid': proc_node['pid'],
                                            'forked': [proc_node.id]}
            else:
                proc_tree_map[r1.end.id]['forked'].append(proc_node.id)

            find_files_read_and_written_by_process(db_iface, r1.end,
                                                   proc_tree_map)
    if proc_node.PROC_OBJ_PREV.outgoing:
        for r1 in proc_node.PROC_OBJ_PREV.outgoing:
            if r1.end.id not in proc_tree_map:
                proc_tree_map[r1.end.id] = {'pid': proc_node['pid'],
                                            'execed': [proc_node.id]}
            else:
                proc_tree_map[r1.end.id]['execed'].append(proc_node.id)

            find_files_read_and_written_by_process(db_iface, r1.end,
                                                   proc_tree_map)

    if len(lineage_list) == 0:
        return

    # Get write history for the files we are interested in
    for gnode in lineage_list:
        file_name = gnode['name'][0]
        if file_name not in GlobData.file_hist_list:
            get_write_history(db_iface, gnode['name'][0], proc_tree_map)


def get_write_history(db_iface, file_name, proc_tree_map):

    if file_name in GlobData.file_hist_list:
        return

    GlobData.file_hist_list.append(file_name)
    logging.debug("Getting write histories for: %s", file_name)

    rows = db_iface.locked_query(
        "START file_glob_node=node:FILE_INDEX('name:\"" + file_name + "\"') "
        "MATCH file_glob_node-[rel1:LOC_OBJ]->file_loc_node,  "
        "file_loc_node-[:PROC_OBJ]->proc_node "
        "WHERE rel1.state in [{w},{rw}] "
        "RETURN distinct proc_node "
        "ORDER by proc_node.node_id DESC",
        w=storage.LinkState.WRITE,
        rw=storage.LinkState.RaW)

    for row in rows:
        proc_node = row['proc_node']

        if file_name == GlobData.queried_file:
            update_last_modified_time(proc_node['sys_time'])

        find_files_read_and_written_by_process(db_iface, proc_node,
                                               proc_tree_map)


def get_fork_exec(node_id, proc_tree_map, proc_nodes):
    if node_id in GlobData.visited_list:
        return

    GlobData.visited_list.append(node_id)
    proc_nodes.append(node_id)
    if "forked" in proc_tree_map[node_id]:
        fl = proc_tree_map[node_id]['forked']
        for n_id in fl:
            get_fork_exec(n_id, proc_tree_map, proc_nodes)
    if "execed" in proc_tree_map[node_id]:
        el = proc_tree_map[node_id]['execed']
        for n_id in el:
            get_fork_exec(n_id, proc_tree_map, proc_nodes)


def get_all_processes(db_iface, proc_tree_map):
    if len(GlobData.proc_list) == 0:
        logging.debug("No write history available")
        return

    proc_nodes = []
    for key in sorted(proc_tree_map):
        if key in GlobData.visited_list:
            continue
        GlobData.visited_list.append(key)
        if 'forked' in proc_tree_map[key]:
            fl = proc_tree_map[key]['forked']
            fl.sort()
            for node_id in fl:
                get_fork_exec(node_id, proc_tree_map, proc_nodes)

    # TODO: This should be the list of processes for which we need to
    # descend down and build the tree.
    proc_nodes = sorted(set(proc_nodes))
    for node_id in proc_nodes:
        proc_node = db_iface.db.node[node_id]
        descend_down_proc_tree(db_iface, proc_node, proc_tree_map)


def print_recursive(indent, node_id, proc_tree_map, current_dir):
    if node_id in GlobData.printed_list:
        return
    GlobData.printed_list.append(node_id)

    if len(proc_tree_map[node_id]['cmd_args']) > 0:
        date_time_str = get_date_time_str(
            proc_tree_map[node_id]['sys_time'])
        cwd = proc_tree_map[node_id]['cwd']
        if current_dir != cwd:
            current_dir = cwd
            print("\t"*indent + "(Current directory: %s)" % (current_dir))

        print("\t"*indent + "[%s]: %s, (PID: %d)" %
              (date_time_str,
               proc_tree_map[node_id]['cmd_args'],
               proc_tree_map[node_id]['pid']))
        if len(proc_tree_map[node_id]['read_files']) > 0:
            read_files = sorted(set(proc_tree_map[node_id]['read_files']))
            print("\t"*(indent+3) + "READ: %s" % (','.join(read_files)))
        if len(proc_tree_map[node_id]['write_files']) > 0:
            write_files = sorted(set(
                proc_tree_map[node_id]['write_files']))
            print("\t"*(indent+3) + "WROTE: %s" % (','.join(write_files)))
        if len(proc_tree_map[node_id]['read_write_files']) > 0:
            read_write_files = sorted(set(
                proc_tree_map[node_id]['read_write_files']))
            print("\t"*(indent+3) + "READ/WROTE: %s" %
                  (','.join(read_write_files)))
        if len(proc_tree_map[node_id]['executed_files']) > 0:
            executed_files = sorted(set(
                proc_tree_map[node_id]['executed_files']))
            print("\t"*(indent+3) + "EXECUTED: %s" %
                  (','.join(executed_files)))

    if 'execed' in proc_tree_map[node_id]:
        el = proc_tree_map[node_id]['execed']
        el.sort()
        for ni in el:
            print_recursive(indent, ni, proc_tree_map, current_dir)
    elif 'forked' in proc_tree_map[node_id]:
        fl = proc_tree_map[node_id]['forked']
        fl.sort()
        for ni in fl:
            print_recursive(indent + 1, ni, proc_tree_map, current_dir)


def print_tree(proc_tree_map):
    indent = 0
    current_dir = None
    for key in sorted(proc_tree_map):
        if key in GlobData.printed_list:
            continue

        if 'forked' in proc_tree_map[key]:
            fl = proc_tree_map[key]['forked']
            fl.sort()
            date_time_str = get_date_time_str(
                proc_tree_map[key]['sys_time'])

            cwd = proc_tree_map[key]['cwd']
            if current_dir != cwd:
                current_dir = cwd
                print("\t"*indent + "(Current directory: %s)" % (current_dir))

            print("\t"*indent + "[%s]: %s, (PID: %d)" %
                  (date_time_str,
                   proc_tree_map[key]['cmd_args'],
                   proc_tree_map[key]['pid']))
            GlobData.printed_list.append(key)
            for node_id in fl:
                print_recursive(indent + 1, node_id,
                                proc_tree_map, current_dir)


def save_proc_tree_map(proc_tree_map, file_name):
    pickle.dump(proc_tree_map, open(file_name, "wb"))


def load_proc_tree_map(file_name):
    return pickle.load(open(file_name, "rb"))


def get_hash(name):
    hasher = hashlib.sha1()
    hasher.update(name)
    return hasher.hexdigest()


@client_query.ClientQueryControl.register_query_method("gen_workflow")
def gen_workflow(db_iface, args):
    if 'file_name' not in args:
        return {"success": False,
                "msg": "No file name provided."}

    file_name = args['file_name']

    regen = True
    if 'regen' in args:
        regen = args['regen']

    file_hash = get_hash(file_name) + ".procmap"
    if not regen and os.path.isfile(file_hash):
        return {"success": True,
                "proc_tree_map": pickle.dumps(load_proc_tree_map(file_hash))}

    GlobData.clear_data()
    proc_tree_map = {}

    GlobData.queried_file = file_name
    get_write_history(db_iface, file_name, proc_tree_map)
    get_all_processes(db_iface, proc_tree_map)

    # print_tree(proc_tree_map) # Use only for debugging

    save_proc_tree_map(proc_tree_map, file_hash)
    logging.debug("Successfully generated workflow...saved data on disk\n")

    return {"success": True,
            "proc_tree_map": pickle.dumps(proc_tree_map)}
