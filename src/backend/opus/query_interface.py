# -*- coding: utf-8 -*-
'''
The query interface module contains functions for querying from
the database.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
from . import storage
from .exception import InvalidQueryException


def splitpath(path, maxdepth=50):
    '''Splits a unix file path into a list of elements'''
    (head, tail) = os.path.split(path)
    return [tail] + splitpath(head, maxdepth - 1) \
        if maxdepth and head and head != path \
        else [head or tail]


class FSTree(object):
    '''Constructs a tree given a list of paths'''
    def __init__(self):
        super(FSTree, self).__init__()
        self.tree_map = {}

    def get_tree_map(self):
        '''Returns the tree map'''
        return self.tree_map

    def build(self, line):
        '''Starts building the tree'''
        if line == "":
            return

        path_list = splitpath(line)
        if path_list[-1].count('/') > 1:
            path_list[-1] = '/'

        self.treefy(path_list, self.tree_map)

    def treefy(self, path_list, submap):
        '''Recursively builds a tree with the given path'''

        if len(path_list) == 1:
            node_key = path_list.pop()
            if node_key not in submap:
                submap[node_key] = {'attr': {'hist': True}, 'subdirs': {}}
            else:
                submap[node_key]['attr']['hist'] = True
        else:
            node_key = path_list.pop()
            if node_key not in submap:
                submap[node_key] = {'attr': {'hist': False}, 'subdirs': {}}
            self.treefy(path_list, submap[node_key]['subdirs'])

    def pretty_print(self, tmp_map, indent=0):
        '''Recursively prints the tree'''
        for key, val in tmp_map.items():
            enable = ""
            if val['attr']['hist']:
                enable = "*"
            print("  " * indent + enable + key)
            self.pretty_print(tmp_map[key]['subdirs'], indent + 1)

    def print_tree(self):
        '''Prints the tree map'''
        self.pretty_print(self.tree_map)

# ####### The following functions are used for the GUI ####### #


def __construct_name_idx_qry(idx_key):
    '''Returns sub query string to lookup name index'''
    idx_name_qry = "name:" + idx_key
    return idx_name_qry


def __construct_time_idx_qry(start_date, end_date):
    '''Returns sub query string to lookup time index'''
    time_idx_qry = None
    if start_date and end_date:
        start_bucket = int(start_date) - (int(start_date) % 3600)
        end_bucket = int(end_date) - (int(end_date) % 3600)
        time_idx_qry = "time:[" + str(start_bucket)
        time_idx_qry += " TO " + str(end_bucket) + "]"
    return time_idx_qry


def __construct_prog_qry(file_states, proc_states):
    '''Constructs and returns a query string to get programs
    from a given file'''
    tmp_qry = " MATCH glob_node-[rel1:LOC_OBJ]->loc_node, "
    tmp_qry += " loc_node-[:PROC_OBJ]->proc_node, "
    tmp_qry += " proc_node<-[:PROC_OBJ]-bin_loc_node, "
    tmp_qry += " bin_loc_node<-[rel2:LOC_OBJ]-bin_glob_node "
    tmp_qry += " WHERE rel1.state in [" + file_states + "]"
    tmp_qry += " AND rel2.state in [" + proc_states + "] "
    return tmp_qry


def __construct_file_qry(file_states, proc_states):
    '''Constructs and returns a query string to get files
    from a given program'''
    tmp_qry = " MATCH glob_node-[rel1:LOC_OBJ]->loc_node, "
    tmp_qry += " loc_node-[:PROC_OBJ]->proc_node, "
    tmp_qry += " proc_node<-[:PROC_OBJ]-file_loc_node, "
    tmp_qry += " file_loc_node<-[rel2:LOC_OBJ]-file_glob_node "
    tmp_qry += " WHERE rel1.state in [" + proc_states + "]"
    tmp_qry += " AND rel2.state in [" + file_states + "] "
    return tmp_qry


def __add_deleted_node(bin_glob_node, proc_node,
                       file_glob_node, result_list):
    '''Checks incoming relations with deleted state to a global node
    and adds the deleted global to the result list'''
    for link in file_glob_node.GLOB_OBJ_PREV.incoming:
        if link['state'] == storage.LinkState.DELETED:
            start_node = link.start
            file_name = ""

            if start_node.has_key('name'):
                file_name = start_node['name']

            result_list.append((bin_glob_node['name'], proc_node['pid'],
                                file_name, storage.LinkState.DELETED,
                                start_node['sys_time'],
                                start_node['node_id']))


def __add_result(result_list, bin_glob_node, proc_node,
                 file_glob_node, glob_loc_rel):
    '''Common function that populates result list'''
    file_name = ""
    if file_glob_node.has_key('name'):
        file_name = file_glob_node['name']

    if len(file_glob_node.GLOB_OBJ_PREV.incoming) > 0:
        __add_deleted_node(bin_glob_node, proc_node,
                           file_glob_node, result_list)

    result_list.append((bin_glob_node['name'], proc_node['pid'],
                        file_name, glob_loc_rel['state'],
                        file_glob_node['sys_time'],
                        file_glob_node['node_id']))


def __get_history(db_iface, qry, file_states, proc_states):
    '''Builds and executes a query to to get the process/file
    history after applying filters'''
    result_list = []

    tmp_qry = " MATCH bin_glob_node-[rel1:LOC_OBJ]->loc_node, "
    tmp_qry += "loc_node-[:PROC_OBJ]->proc_node, "
    tmp_qry += "proc_node<-[:PROC_OBJ]-file_loc_node, "
    tmp_qry += "file_loc_node<-[rel2:LOC_OBJ]-file_glob_node "
    tmp_qry += "WHERE rel1.state in [" + proc_states + "] "
    tmp_qry += "AND rel2.state in [" + file_states + "] "
    tmp_qry += "RETURN bin_glob_node, proc_node, file_glob_node, rel2 "
    tmp_qry += "ORDER by file_glob_node.node_id DESC"
    qry += tmp_qry

    result = db_iface.query(qry)
    for row in result:
        bin_glob_node = row['bin_glob_node']
        proc_node = row['proc_node']
        file_glob_node = row['file_glob_node']
        glob_loc_rel = row['rel2']

        __add_result(result_list, bin_glob_node, proc_node,
                     file_glob_node, glob_loc_rel)
    return result_list


def __get_file_proc_tree(db_iface, search_str, start_date, end_date, idx_type):
    '''Retrieves file/process tree given time range and index type'''

    key_str = ""
    file_states = str(storage.LinkState.READ)
    file_states += ", " + str(storage.LinkState.WRITE)
    file_states += ", " + str(storage.LinkState.RaW)
    file_states += ", " + str(storage.LinkState.NONE)

    proc_states = str(storage.LinkState.BIN)

    if search_str is None:
        search_str = "*"
    else:
        search_str = "\"" + search_str + "\""

    qry = "START glob_node=node:%s('%s %s')"

    time_idx_qry = __construct_time_idx_qry(start_date, end_date)
    if time_idx_qry is not None:
        time_idx_qry += " AND "
    else:
        time_idx_qry = ""

    qry = qry % (idx_type, time_idx_qry, __construct_name_idx_qry(search_str))

    if idx_type == storage.DBInterface.FILE_INDEX:
        qry += __construct_prog_qry(file_states, proc_states)
        qry += " AND HAS (glob_node.name) "
        qry += " WITH DISTINCT bin_glob_node.name as bin_name "
        qry += " RETURN bin_name"
        key_str = "bin_name"
    elif idx_type == storage.DBInterface.PROC_INDEX:
        qry += __construct_file_qry(file_states, proc_states)
        qry += " AND HAS (file_glob_node.name) "
        qry += " WITH DISTINCT file_glob_node.name as file_name "
        qry += " RETURN file_name"
        key_str = "file_name"

    tree_obj = FSTree()

    result = db_iface.query(qry)
    for row in result:
        node_name = row[key_str]

        # Build a tree object
        for name in node_name:
            tree_obj.build(name)

    return tree_obj


# Query for the main panel
def get_programs(db_iface, file_name, start_date, end_date, user_name):
    '''Returns program tree matching the file name string within the
    given start and end date range'''
    return __get_file_proc_tree(db_iface, file_name, start_date, end_date,
                                storage.DBInterface.FILE_INDEX)


# Query for the main panel
def get_files(db_iface, prog_name, start_date, end_date, user_name):
    '''Returns file tree matching the program name string within the
    given start and end date range'''
    return __get_file_proc_tree(db_iface, prog_name, start_date, end_date,
                                storage.DBInterface.PROC_INDEX)


def __build_idx_qry(node_name, search_str, idx_type, time_idx_qry):
    '''Builds a query string  using file/process name and time indexes'''
    tmp_qry = "%s=node:%s('%s %s')"
    search_str = "\"" + search_str + "\""
    name_idx_qry = __construct_name_idx_qry(search_str)
    tmp_qry = tmp_qry % (node_name, idx_type, time_idx_qry, name_idx_qry)
    return tmp_qry


# Query for the right panel
def get_file_proc_history(db_iface, file_name, proc_name, user_name,
                          start_date, end_date):
    '''Returns the history of a file/process after applying filters
    passed as input args. Returned data format is a list of tupes
    of format (Binary name, PID, File name, Action, Time, node_id)'''

    if (file_name is None) and (proc_name is None):
        raise InvalidQueryException()

    file_states = str(storage.LinkState.READ)
    file_states += ", " + str(storage.LinkState.WRITE)
    file_states += ", " + str(storage.LinkState.RaW)
    file_states += ", " + str(storage.LinkState.NONE)

    proc_states = str(storage.LinkState.BIN)

    qry = "START %s %s %s"

    file_idx_qry = ""
    proc_idx_qry = ""
    comma_char = ""

    # Build time index range query
    time_idx_qry = __construct_time_idx_qry(start_date, end_date)
    if time_idx_qry is not None:
        time_idx_qry += " AND "
    else:
        time_idx_qry = ""

    if file_name is not None:
        file_idx_qry = __build_idx_qry("file_glob_node", file_name,
                                       storage.DBInterface.FILE_INDEX,
                                       time_idx_qry)

    if proc_name is not None:
        proc_idx_qry = __build_idx_qry("bin_glob_node", proc_name,
                                       storage.DBInterface.PROC_INDEX,
                                       time_idx_qry)

    if file_name and proc_name:
        comma_char = ", "

    qry = qry % (file_idx_qry, comma_char, proc_idx_qry)

    return __get_history(db_iface, qry, file_states, proc_states)
