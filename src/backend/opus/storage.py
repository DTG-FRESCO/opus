# -*- coding: utf-8 -*-
'''
The storage module contains classes that interface between backend storage
systems and the opus analysers.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import functools
import hashlib
import leveldb
import struct
import logging
import time
import os

from opus import common_utils
from neo4j import GraphDatabase, INCOMING, OUTGOING
from opus import cc_utils

# Enum values for node types
NodeType = common_utils.enum(META=1,
                            GLOBAL=2,
                            PROCESS=3,
                            LOCAL=4,
                            EVENT=5,
                            ANNOT=6,
                            TERM=7)

# Enum values for relationship types
RelType = common_utils.enum(GLOB_OBJ_PREV="GLOB_OBJ_PREV",
                            LOC_OBJ="LOC_OBJ",
                            LOC_OBJ_PREV="LOC_OBJ_PREV",
                            PROC_OBJ="PROC_OBJ",
                            PROC_OBJ_PREV="PROC_OBJ_PREV",
                            PROC_PARENT="PROC_PARENT",
                            PROC_EVENTS="PROC_EVENTS",
                            IO_EVENTS="IO_EVENTS",
                            PREV_EVENT="PREV_EVENT",
                            FILE_META="FILE_META",
                            LIB_META="LIB_META",
                            ENV_META="ENV_META",
                            OTHER_META="OTHER_META",
                            META_PREV="META_PREV")

# Enum values for relationship link states
LinkState = common_utils.enum(NONE = 0,
                                CoT = 1,
                                READ = 2,
                                WRITE = 3,
                                RaW = 4,
                                CLOSED = 5,
                                DELETED = 6,
                                BIN = 7,
                                CoE = 8,
                                CLOEXEC = 9,
                                INACTIVE = 10)



class UniqueIDException(common_utils.OPUSException):
    '''Exception when unique ID cannot be generated'''
    def __init__(self):
        super(UniqueIDException, self).__init__(
            "Error: Unique ID generation error"
        )

class InvalidQueryException(common_utils.OPUSException):
    '''Exception when unique ID cannot be generated'''
    def __init__(self):
        super(InvalidQueryException, self).__init__(
            "Error: Invalid Query"
        )


def splitpath(path, maxdepth=50):
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
                submap[node_key] = { 'attr':{'hist':True}, 'subdirs':{} }
            else:
                submap[node_key]['attr']['hist'] = True
        else:
            node_key = path_list.pop()
            if node_key not in submap:
                submap[node_key] = { 'attr':{'hist':False}, 'subdirs':{} }
            self.treefy(path_list, submap[node_key]['subdirs'])


    def pretty_print(self, tmp_map, indent = 0):
        '''Recursively prints the tree'''
        for key, val in tmp_map.items():
            enable = ""
            if val['attr']['hist']:
                enable = "*"
            print("  " * indent + enable + key)
            self.pretty_print(tmp_map[key]['subdirs'], indent + 1)


    def print_tree(self):
        self.pretty_print(self.tree_map)



class StorageIFace(object):
    '''A storage interface base class to access a provenance graph database
    using a series of operations. It encapsulates the type of
    database and it's method of access.'''

    def close(self):
        '''Close the database connection.'''
        pass

    def start_transaction(self):
        '''Begin a transaction'''
        pass

    def create_node(self, node_type):
        '''Create a node'''
        pass

    def create_relationship(self, from_node, to_node, rel_type):
        '''Create a relationship between two nodes'''
        pass

    def set_property(self, node, name, value):
        '''Set a property on a node'''
        pass

    def get_property(self, node, name):
        '''Returns the value of a property for a node'''
        pass


class Neo4JInterface(StorageIFace):
    '''Neo4J implementation of storage interface'''

    FILE_INDEX = "FILE_INDEX"
    PROC_INDEX = "PROC_INDEX"
    UNIQ_ID_IDX = "UNIQ_ID_IDX"
    NODE_ID_IDX = "NODE_ID_IDX"
    TIME_INDEX = "TIME_INDEX"

    def __init__(self, filename):
        super(Neo4JInterface, self).__init__()
        try:
            self.db = GraphDatabase(filename)
            self.file_index = None
            self.proc_index = None
            self.node_id_idx = None
            self.id_node = None
            self.sys_time = int(time.time())

            with self.db.transaction:
                # Unique ID index
                if self.db.node.indexes.exists(Neo4JInterface.UNIQ_ID_IDX):
                    uniq_id_idx = self.db.node.indexes.get(Neo4JInterface.UNIQ_ID_IDX)
                    id_nodes = uniq_id_idx['node']['UNIQ_ID']
                    if len(id_nodes) == 1:
                        self.id_node = id_nodes[0]
                    else:
                        raise UniqueIDException()
                else:
                    uniq_id_idx = self.db.node.indexes.create(Neo4JInterface.UNIQ_ID_IDX)
                    self.id_node = self.db.node()
                    self.id_node['serial_id'] = 0
                    uniq_id_idx['node']['UNIQ_ID'] = self.id_node

                # File index
                if self.db.node.indexes.exists(Neo4JInterface.FILE_INDEX):
                    self.file_index = self.db.node.indexes.get(Neo4JInterface.FILE_INDEX)
                else:
                    self.file_index = self.db.node.indexes.create(Neo4JInterface.FILE_INDEX)

                # Process index
                if self.db.node.indexes.exists(Neo4JInterface.PROC_INDEX):
                    self.proc_index = self.db.node.indexes.get(Neo4JInterface.PROC_INDEX)
                else:
                    self.proc_index = self.db.node.indexes.create(Neo4JInterface.PROC_INDEX)

                # Node ID index
                if self.db.node.indexes.exists(Neo4JInterface.NODE_ID_IDX):
                    self.node_id_idx = self.db.node.indexes.get(Neo4JInterface.NODE_ID_IDX)
                else:
                    self.node_id_idx = self.db.node.indexes.create(Neo4JInterface.NODE_ID_IDX)

            # Fix for the class load error when using multiple threads
            rows = self.db.query("START n=node(1) RETURN n")
            for row in rows:
                n = row['n']

        except Exception as e:
            logging.error("Error: %s", str(e))
            raise e


    def close(self):
        '''Shutdown the database'''
        self.db.shutdown()


    def start_transaction(self):
        '''Returns a Neo4J transaction'''
        return self.db.transaction


    def set_sys_time_for_msg(self, sys_time):
        '''Stores the system time passed in the header
        for each message being processed'''
        self.sys_time = sys_time


    def create_node(self, node_type):
        '''Creates a node and sets the node ID, type and timestamp'''
        node = self.db.node()
        node_id = self.get_next_id()
        node['node_id'] = node_id
        node['type'] = node_type
        node['sys_time'] = self.sys_time

        self.update_index(Neo4JInterface.NODE_ID_IDX, 'node', node_id, node)
        return node


    def create_relationship(self, from_node, to_node, rel_type):
        '''Creates a relationship of given type'''
        rel = from_node.relationships.create(rel_type, to_node)
        rel['state'] = LinkState.NONE
        return rel


    def set_property(self, node, p_name, p_value):
        '''Given a property name and value, set it on the
        passed node object'''
        node[p_name] = p_value


    def get_property(self, node, p_name):
        '''Return the property value'''
        return node[p_name]


    def update_time_index(self, idx_type, sys_time_val, glob_node):
        '''Updates the file or process time index entry for the hourly
        bucket depending on the index type passed'''
        idx = None
        if idx_type == Neo4JInterface.FILE_INDEX:
            idx = self.file_index
        elif idx_type == Neo4JInterface.PROC_INDEX:
            idx = self.proc_index
        hourly_bucket =  sys_time_val - (sys_time_val % 3600)
        idx['time'][hourly_bucket] = glob_node


    def update_index(self, idx_type, idx_name, idx_key, idx_val):
        '''Adds value to a given index type with the name and key'''
        if idx_type == Neo4JInterface.FILE_INDEX:
            self.file_index[idx_name][idx_key] = idx_val
        elif idx_type == Neo4JInterface.PROC_INDEX:
            self.proc_index[idx_name][idx_key] = idx_val
        elif idx_type == Neo4JInterface.NODE_ID_IDX:
            self.node_id_idx[idx_name][idx_key] = idx_val


    def get_next_id(self):
        '''Returns a unique node ID'''
        node_id = None
        if self.id_node is not None:
            node_id = self.id_node['serial_id']
            self.id_node['serial_id'] = node_id + 1
            return node_id
        else:
            raise UniqueIDException()


    def find_and_del_rel(self, from_node, to_node, rel_type):
        '''Finds a relation of type rel_type between two nodes
        and deletes it'''
        qry = "START from_node=node(" + str(from_node.id) + ") "
        qry += "MATCH from_node-[rel:" + rel_type + "]->to_node "
        qry += "WHERE id(to_node) = " + str(to_node.id)
        qry += " RETURN rel"
        rows = self.db.query(qry)
        for row in rows:
            rel = row['rel']
            rel.delete()


    def delete_relationship(self, rel):
        '''Deletes relatioship given a relationship object'''
        rel.delete()


    def get_node_by_id(self, node_id):
        '''Returns a node object given the ID'''
        node_list = self.node_id_idx['node'][node_id]
        if len(node_list) == 1:
            return node_list[0]
        else:
            return None


    def get_latest_glob_version(self, name):
        '''Gets the latest global version for the given name'''
        node = None

        qry = "START n=node:FILE_INDEX('name:\"" + name + "\"') "
        qry += "RETURN n ORDER BY n.node_id DESC LIMIT 1"

        result = self.db.query(qry)
        for row in result:
            node = row['n']
        return node


    def is_glob_deleted(self, glob_node):
        '''Returns true if the global node has been deleted'''
        ret = False
        for rel in glob_node.relationships.outgoing:
            if rel['state'] == LinkState.DELETED:
                ret = True
        return ret


    def get_globals_from_local(self, loc_node):
        '''Gets the global object nodes and relationship list
        associated with the local object node'''
        glob_node_link_list = []


        rows = self.db.query("START loc_node=node({id}) \
                            MATCH loc_node<-[rel:LOC_OBJ]-glob_node \
                            RETURN glob_node, rel", id=loc_node.id)
        for row in rows:
            glob_node = row['glob_node']
            rel = row['rel']
            glob_node_link_list.append((glob_node, rel))
        return glob_node_link_list


    def get_locals_from_global(self, glob_node):
        '''Gets all local object nodes and the relationship
        links connected to the given global'''
        loc_node_link_list = []

        qry = "START glob_node=node(" + str(glob_node.id) + ") "
        qry += "MATCH glob_node-[rel:LOC_OBJ]->loc_node "
        qry += "RETURN loc_node, rel"

        rows = self.db.query(qry)
        for row in rows:
            loc_node = row['loc_node']
            rel = row['rel']
            loc_node_link_list.append((loc_node, rel))
        return loc_node_link_list


    def get_process_from_local(self, loc_node):
        '''Gets the process node and relationship link
        from the local obj'''
        proc_node = None
        rel = None

        qry = "START loc_node=node(" + str(loc_node.id) + ") "
        qry += "MATCH loc_node-[rel:PROC_OBJ]->proc_node "
        qry += "WHERE rel.state <> " + str(LinkState.CoT)
        qry += "RETURN proc_node, rel"

        rows = self.db.query(qry)
        for row in rows:
            proc_node = row['proc_node']
            rel = row['rel']
        return proc_node, rel


    def get_locals_from_process(self, proc_node):
        '''Returns all local object nodes and its links for the
        given process object node'''
        loc_node_link_list = []

        qry = "START proc_node=node(" + str(proc_node.id) + ") "
        qry += "MATCH proc_node<-[rel:PROC_OBJ]-loc_node "
        qry += "WHERE rel.state <> " + str(LinkState.INACTIVE)
        qry += "RETURN loc_node, rel"

        rows = self.db.query(qry)
        for row in rows:
            loc_node = row['loc_node']
            rel = row['rel']
            loc_node_link_list.append((loc_node, rel))
        return loc_node_link_list


    def get_next_local_version(self, loc_node):
        '''Gets the next local object version'''
        next_loc_node = None

        qry = "START loc_node=node(" + str(loc_node.id) + ") "
        qry += "MATCH loc_node<-[rel:LOC_OBJ_PREV]-next_loc_node "
        qry += "RETURN next_loc_node"

        rows = self.db.query(qry)
        for row in rows:
            next_loc_node = row['next_loc_node']
        return next_loc_node


    def get_valid_local(self, proc_node, loc_name):
        '''Returns a local, local->process link tuple
        filtered by local node name and link state'''
        loc_node = None
        loc_proc_rel = None

        rows = self.db.query("START proc_node=node({id}) \
                            MATCH proc_node<-[lp_rel:PROC_OBJ]-loc_node \
                            WHERE lp_rel.state <> {state1} \
                            AND lp_rel.state <> {state2} \
                            AND loc_node.name = {name} \
                            RETURN loc_node, lp_rel ",
                            id=proc_node.id, state1=LinkState.CLOSED,
                            state2=LinkState.INACTIVE, name=loc_name)
        for row in rows:
            loc_node = row['loc_node']
            loc_proc_rel = row['lp_rel']
        return loc_node, loc_proc_rel


    def get_glob_latest_version(self, loc_node):
        '''Returns the latest valid version of a global node'''
        ret_glob = None

        glob_node_list = self.get_globals_from_local(loc_node)
        glob_list_len = len(glob_node_list)

        if glob_list_len == 0:
            return ret_glob

        if glob_list_len > 1:
            logging.error("Tracing latest global of invalid local.")
            return ret_glob

        glob_node, glob_loc_rel = glob_node_list[0]

        # If there are no new versions of the global node the
        # local is pointing to, then return the current global
        if len(glob_node.relationships.incoming) == 0:
            return glob_node

        # The global has versioned, traverse the graph until you find
        # the last global node that is not in deleted status. Avoid 
        # taversing down deleted paths.
        found = False
        node_id = glob_node.id

        while 1:
            qry = "START src_node=node(" + str(node_id) + ") "
            qry += "MATCH src_node<-[rel:GLOB_OBJ_PREV]-dest_node "
            qry += "WHERE rel.state <> " + str(LinkState.DELETED)
            qry += "RETURN dest_node "
            qry += "ORDER BY dest_node.node_id"

            result = self.db.query(qry)
            for row in result:
                dest_glob_node = row['dest_node']
                node_id = dest_glob_node.id
                ret_glob = dest_glob_node
                found = True

            if found: # Check if node has any incoming relationships
                if len(ret_node.relationships.incoming) == 0:
                    break
                else:
                    found = False
                    continue
            else:
                ret_glob = None
                break

        return ret_glob



    def get_proc_meta(self, proc_node, rel_type):
        '''Returns all meta objects of a given type and their
        relationship link to the process node proc_node'''
        meta_rel_list = []

        qry = "START proc_node=node(" + str(proc_node.id) + ") "
        qry += "MATCH proc_node-[meta_rel:" + rel_type + "]->meta_node "
        qry += "RETURN meta_node, meta_rel"

        rows = self.db.query(qry)
        for row in rows:
            meta_node = row['meta_node']
            meta_rel = row['meta_rel']
            meta_rel_list.append((meta_node, meta_rel))
        return meta_rel_list


    def get_last_event(self, start_node, rel_type):
        '''Returns the event object and relationship link
        connected to the passed node'''
        last_event_node = None
        event_rel = None

        qry = "START start_node=node(" + str(start_node.id) + ") "
        qry += "MATCH start_node-[rel:" + rel_type + "]->event_node "
        qry += "RETURN event_node, rel"

        rows = self.db.query(qry)
        for row in rows:
            last_event_node = row['event_node']
            event_rel = row['rel']
        return last_event_node, event_rel


    def get_rel(self, src_node, rel_type):
        '''Returns a list of relationship links of rel_type
        from the source node src_node'''
        rel_list = []

        qry = "START src_node=node(" + str(src_node.id) + ") "
        qry += "MATCH src_node-[rel:" + rel_type + "]->dest_node "
        qry += "RETURN rel"

        rows = self.db.query(qry)
        for row in rows:
            rel = row['rel']
            rel_list.append(rel)
        return rel_list

    ######## The following functions are used for the GUI ########

    def __construct_name_idx_qry(self, idx_key):
        '''Returns sub query string to lookup name index'''
        idx_name_qry = "name:" + idx_key
        return idx_name_qry


    def __construct_time_idx_qry(self, start_date, end_date):
        '''Returns sub query string to lookup time index'''
        time_idx_qry = None
        if start_date and end_date:
            start_bucket = int(start_date) - (int(start_date) % 3600)
            end_bucket = int(end_date) - (int(end_date) % 3600)
            time_idx_qry = "time:[" + str(start_bucket)
            time_idx_qry += " TO " + str(end_bucket) + "]"
        return time_idx_qry


    def __construct_prog_qry(self, file_states, proc_states):
        '''Constructs and returns a query string to get programs
        from a given file'''
        tmp_qry = " MATCH glob_node-[rel1:LOC_OBJ]->loc_node, "
        tmp_qry += " loc_node-[:PROC_OBJ]->proc_node, "
        tmp_qry += " proc_node<-[:PROC_OBJ]-bin_loc_node, "
        tmp_qry += " bin_loc_node<-[rel2:LOC_OBJ]-bin_glob_node "
        tmp_qry += " WHERE rel1.state in [" + file_states + "]"
        tmp_qry += " AND rel2.state in [" + proc_states + "] "
        return tmp_qry


    def __construct_file_qry(self, file_states, proc_states):
        '''Constructs and returns a query string to get files
        from a given program'''
        tmp_qry = " MATCH glob_node-[rel1:LOC_OBJ]->loc_node, "
        tmp_qry += " loc_node-[:PROC_OBJ]->proc_node, "
        tmp_qry += " proc_node<-[:PROC_OBJ]-file_loc_node, "
        tmp_qry += " file_loc_node<-[rel2:LOC_OBJ]-file_glob_node "
        tmp_qry += " WHERE rel1.state in [" + proc_states + "]"
        tmp_qry += " AND rel2.state in [" + file_states + "] "
        return tmp_qry



    def __add_deleted_node(self, bin_glob_node, proc_node,
                                file_glob_node, result_list):
        '''Checks incoming relations with deleted state to a global node
        and adds the deleted global to the result list'''
        for link in file_glob_node.GLOB_OBJ_PREV.incoming:
            if link['state'] == LinkState.DELETED:
                start_node = link.start
                file_name = ""

                if start_node.has_key('name'):
                    file_name = start_node['name']

                result_list.append((bin_glob_node['name'], proc_node['pid'],
                                    file_name, LinkState.DELETED,
                                    start_node['sys_time'],
                                    start_node['node_id']))


    def __add_result(self, result_list, bin_glob_node, proc_node,
                        file_glob_node, glob_loc_rel):
        '''Common function that populates result list'''
        file_name = ""
        if file_glob_node.has_key('name'):
            file_name = file_glob_node['name']

        if len(file_glob_node.GLOB_OBJ_PREV.incoming) > 0:
            self.__add_deleted_node(bin_glob_node, proc_node,
                                file_glob_node, result_list)

        result_list.append((bin_glob_node['name'], proc_node['pid'],
                            file_name, glob_loc_rel['state'],
                            file_glob_node['sys_time'],
                            file_glob_node['node_id']))


    def __query_get_proc(self, qry, file_states, proc_states):
        '''Builds and executes a query to to get the
        processes and binares influencing a given file'''
        result_list = []

        tmp_qry = self.__construct_prog_qry(file_states, proc_states)
        tmp_qry += " RETURN bin_glob_node, proc_node, glob_node, rel1"
        tmp_qry += " ORDER by glob_node.node_id DESC"
        qry += tmp_qry

        result = self.db.query(qry)
        for row in result:
            bin_glob_node = row['bin_glob_node']
            proc_node = row['proc_node']
            file_glob_node = row['glob_node']
            glob_loc_rel = row['rel1']

            self.__add_result(result_list, bin_glob_node, proc_node,
                                file_glob_node, glob_loc_rel)
        return result_list


    def __query_get_files(self, qry, file_states, proc_states):
        '''Builds and executes a query to to get the
        files influenced by a given process'''
        result_list = []

        tmp_qry = self.__construct_file_qry(file_states, proc_states)
        tmp_qry += " RETURN glob_node, proc_node, file_glob_node, rel2"
        tmp_qry += " ORDER by file_glob_node.node_id DESC"
        qry += tmp_qry

        result = self.db.query(qry)
        for row in result:
            bin_glob_node = row['glob_node']
            proc_node = row['proc_node']
            file_glob_node = row['file_glob_node']
            glob_loc_rel = row['rel2']

            self.__add_result(result_list, bin_glob_node, proc_node,
                                file_glob_node, glob_loc_rel)
        return result_list


    def __get_file_proc_tree(self, search_str, start_date, end_date, idx_type):
        '''Retrieves file/process tree given time range and index type'''

        key_str = ""
        file_states = str(LinkState.READ)
        file_states += ", " + str(LinkState.WRITE)
        file_states += ", " + str(LinkState.RaW)
        file_states += ", " + str(LinkState.NONE)

        proc_states = str(LinkState.BIN)

        if search_str is None:
            search_str = "*"
        else:
            search_str = "\"" + search_str + "\""

        qry = "START glob_node=node:%s('%s %s')"

        time_idx_qry = self.__construct_time_idx_qry(start_date, end_date)
        if time_idx_qry is not None:
            time_idx_qry += " AND "
        else:
            time_idx_qry = ""

        name_idx_qry = self.__construct_name_idx_qry(search_str)
        qry = qry % (idx_type, time_idx_qry, name_idx_qry)

        if idx_type == Neo4JInterface.FILE_INDEX:
            prog_qry = self.__construct_prog_qry(file_states, proc_states)
            prog_qry += " AND HAS (glob_node.name) "
            prog_qry += " WITH DISTINCT bin_glob_node.name as bin_name "
            qry += prog_qry
            qry += " RETURN bin_name"
            key_str = "bin_name"
        elif idx_type == Neo4JInterface.PROC_INDEX:
            file_qry = self.__construct_file_qry(file_states, proc_states)
            file_qry += " AND HAS (file_glob_node.name) "
            file_qry += " WITH DISTINCT file_glob_node.name as file_name "
            qry += file_qry
            qry += " RETURN file_name"
            key_str = "file_name"

        tree_obj = FSTree()

        result = self.db.query(qry)
        for row in result:
            node_name = row[key_str]

            # Build a tree object
            for name in node_name:
                tree_obj.build(name)

        return tree_obj


    # Query for the main panel
    def get_programs(self, file_name, start_date, end_date, user_name):
        '''Returns program tree matching the file name string within the
        given start and end date range'''
        return self.__get_file_proc_tree(file_name, start_date, end_date,
                                        Neo4JInterface.FILE_INDEX)


    # Query for the main panel
    def get_files(self, prog_name, start_date, end_date, user_name):
        '''Returns file tree matching the program name string within the
        given start and end date range'''
        return self.__get_file_proc_tree(prog_name, start_date, end_date,
                                        Neo4JInterface.PROC_INDEX)


    # Query for the right panel
    def get_file_proc_history(self, file_name, proc_name, user_name,
                                start_date, end_date):
        '''Returns the history of a file/process after applying filters
        passed as input args. Returned data format is a list of tupes 
        of format (Binary name, PID, File name, Action, Time, node_id)'''

        result_list = []

        file_states = str(LinkState.READ)
        file_states += ", " + str(LinkState.WRITE)
        file_states += ", " + str(LinkState.RaW)
        file_states += ", " + str(LinkState.NONE)

        proc_states = str(LinkState.BIN)

        qry = "START glob_node=node:%s('%s %s')"

        # Build time index range query
        time_idx_qry = self.__construct_time_idx_qry(start_date, end_date)
        if time_idx_qry is not None:
            time_idx_qry += " AND "
        else:
            time_idx_qry = ""

        idx_type = None
        search_str = None
        qry_func = None

        if file_name is not None:
            idx_type = Neo4JInterface.FILE_INDEX
            search_str = file_name
            qry_func = self.__query_get_proc
        elif proc_name is not None:
            idx_type = Neo4JInterface.PROC_INDEX
            search_str = proc_name
            qry_func = self.__query_get_files
        else:
            raise InvalidQueryException()

        search_str = "\"" + search_str + "\""
        name_idx_qry = self.__construct_name_idx_qry(search_str)
        qry = qry % (idx_type, time_idx_qry, name_idx_qry)

        print(qry)

        return qry_func(qry, file_states, proc_states)
