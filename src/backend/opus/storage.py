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
NodeType = common_utils.enum(META = 1,
                            GLOBAL = 2,
                            PROCESS = 3,
                            LOCAL = 4,
                            EVENT = 5,
                            ANNOT = 6,
                            TERM = 7)

# Enum values for relationship types
RelType = common_utils.enum(GLOB_OBJ_PREV = "GLOB_OBJ_PREV",
                            LOC_OBJ = "LOC_OBJ",
                            LOC_OBJ_PREV = "LOC_OBJ_PREV",
                            PROC_OBJ = "PROC_OBJ",
                            PROC_OBJ_PREV = "PROC_OBJ_PREV",
                            PROC_PARENT = "PROC_PARENT",
                            PROC_EVENTS = "PROC_EVENTS",
                            IO_EVENTS = "IO_EVENTS",
                            PREV_EVENT = "PREV_EVENT",
                            FILE_META = "FILE_META",
                            LIB_META = "LIB_META",
                            ENV_META = "ENV_META",
                            OTHER_META = "OTHER_META",
                            META_PREV = "META_PREV")

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


class DBInterface(StorageIFace):
    '''Neo4J implementation of storage interface'''

    FILE_INDEX = "FILE_INDEX"
    PROC_INDEX = "PROC_INDEX"
    UNIQ_ID_IDX = "UNIQ_ID_IDX"
    NODE_ID_IDX = "NODE_ID_IDX"
    TIME_INDEX = "TIME_INDEX"

    def __init__(self, filename):
        super(DBInterface, self).__init__()
        try:
            self.db = GraphDatabase(filename)
            self.file_index = None
            self.proc_index = None
            self.node_id_idx = None
            self.id_node = None
            self.sys_time = int(time.time())

            with self.db.transaction:
                # Unique ID index
                if self.db.node.indexes.exists(DBInterface.UNIQ_ID_IDX):
                    uniq_id_idx = self.db.node.indexes.get(DBInterface.UNIQ_ID_IDX)
                    id_nodes = uniq_id_idx['node']['UNIQ_ID']
                    if len(id_nodes) == 1:
                        self.id_node = id_nodes[0]
                    else:
                        raise UniqueIDException()
                else:
                    uniq_id_idx = self.db.node.indexes.create(DBInterface.UNIQ_ID_IDX)
                    self.id_node = self.db.node()
                    self.id_node['serial_id'] = 0
                    uniq_id_idx['node']['UNIQ_ID'] = self.id_node

                # File index
                if self.db.node.indexes.exists(DBInterface.FILE_INDEX):
                    self.file_index = self.db.node.indexes.get(DBInterface.FILE_INDEX)
                else:
                    self.file_index = self.db.node.indexes.create(DBInterface.FILE_INDEX)

                # Process index
                if self.db.node.indexes.exists(DBInterface.PROC_INDEX):
                    self.proc_index = self.db.node.indexes.get(DBInterface.PROC_INDEX)
                else:
                    self.proc_index = self.db.node.indexes.create(DBInterface.PROC_INDEX)

                # Node ID index
                if self.db.node.indexes.exists(DBInterface.NODE_ID_IDX):
                    self.node_id_idx = self.db.node.indexes.get(DBInterface.NODE_ID_IDX)
                else:
                    self.node_id_idx = self.db.node.indexes.create(DBInterface.NODE_ID_IDX)

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
        node_id = self.__get_next_id()
        node['node_id'] = node_id
        node['type'] = node_type
        node['sys_time'] = self.sys_time

        self.update_index(DBInterface.NODE_ID_IDX, 'node', node_id, node)
        return node


    def create_relationship(self, from_node, to_node, rel_type):
        '''Creates a relationship of given type'''
        rel = from_node.relationships.create(rel_type, to_node)
        rel['state'] = LinkState.NONE
        return rel


    def update_time_index(self, idx_type, sys_time_val, glob_node):
        '''Updates the file or process time index entry for the hourly
        bucket depending on the index type passed'''
        idx = None
        if idx_type == DBInterface.FILE_INDEX:
            idx = self.file_index
        elif idx_type == DBInterface.PROC_INDEX:
            idx = self.proc_index
        hourly_bucket =  sys_time_val - (sys_time_val % 3600)
        idx['time'][hourly_bucket] = glob_node


    def update_index(self, idx_type, idx_name, idx_key, idx_val):
        '''Adds value to a given index type with the name and key'''
        if idx_type == DBInterface.FILE_INDEX:
            self.file_index[idx_name][idx_key] = idx_val
        elif idx_type == DBInterface.PROC_INDEX:
            self.proc_index[idx_name][idx_key] = idx_val
        elif idx_type == DBInterface.NODE_ID_IDX:
            self.node_id_idx[idx_name][idx_key] = idx_val


    def __get_next_id(self):
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

    def query(self, qry, **kwargs):
        '''Executes query and returns result'''
        return self.db.query(qry, **kwargs)
