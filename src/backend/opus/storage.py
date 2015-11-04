# -*- coding: utf-8 -*-
'''
The storage module contains classes that interface between backend storage
systems and the opus analysers.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import functools
import logging
import threading
import time
import os
import psutil

from . import common_utils
from .exception import InvalidCacheException, UniqueIDException


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
LinkState = common_utils.enum(NONE=0,
                              CoT=1,
                              READ=2,
                              WRITE=3,
                              RaW=4,
                              CLOSED=5,
                              DELETED=6,
                              BIN=7,
                              CoE=8,
                              CLOEXEC=9,
                              INACTIVE=10)

# Enum values for cache naming
CACHE_NAMES = common_utils.enum(VALID_LOCAL=0,
                                LOCAL_GLOBAL=1,
                                LAST_EVENT=2,
                                NODE_BY_ID=3,
                                IO_EVENT_CHAIN=4)

# Enum values for process status
PROCESS_STATE = common_utils.enum(ALIVE=0, DEAD=1)


class FdChain(object):
    '''An object representing a filedescriptor chain.'''
    def __init__(self):
        super(FdChain, self).__init__()
        self.local = None
        self.chain = common_utils.IndexList(lambda x: int(x['before_time']))

    def __repr__(self):
        return str(str(self.local), str(self.chain))


class CacheManager(object):
    '''Manages a series of caches and allows for them to be
    updated and invalidated.'''
    def __init__(self, cache_list):
        self.caches = {key: dict() for key in cache_list}

    def dump_cache(self, file_name):
        '''Dumps contents of cache to file'''
        pass

    def load_cache(self, file_name):
        '''Loads cache content from file'''
        pass

    def invalidate(self, cache, key):
        '''Invalidates the entry 'key' in 'cache', a InvalidCacheExcetion
        will be raised if 'cache' is not present, a warning will be produced
        if a key that does not exist is invalidated.'''
        if cache not in self.caches:
            raise InvalidCacheException(CACHE_NAMES.enum_str(cache))

        if key not in self.caches[cache]:
            if __debug__:
                logging.warn("Warning: Attempted to invalidate key {0} "
                             "in cache {1} but {0} was not present in "
                             "the cache.".format(
                                 key, CACHE_NAMES.enum_str(cache)
                                 )
                             )
            return

        del self.caches[cache][key]

    def get(self, cache, key):
        '''Retrieves the cached contents for a given
        cache and key combination'''
        if cache not in self.caches:
            raise InvalidCacheException(CACHE_NAMES.enum_str(cache))
        if key not in self.caches[cache]:
            return None
        return self.caches[cache][key]

    def update(self, cache, key, val):
        '''Updates the relevant cache and key combination with
        the new value'''
        if cache not in self.caches:
            raise InvalidCacheException(CACHE_NAMES.enum_str(cache))
        self.caches[cache][key] = val

    @staticmethod
    def dec(cache, key_lambda):
        '''Decorates a function to cache it's return values in 'cache', uses
        'key_lambda' to convert the arguments of the function into a key for
        the cache.'''
        def wrapper(fun):
            '''Wraps function fun.'''
            @functools.wraps(fun)
            def wrapped_fun(db_iface, *args, **kwargs):
                '''Caches the return of fun using key_lambda to convert
                it's arguments into a key.'''
                if cache not in db_iface.cache_man.caches:
                    raise InvalidCacheException(CACHE_NAMES.enum_str(cache))

                key = key_lambda(*args, **kwargs)

                if key in db_iface.cache_man.caches[cache]:
                    return db_iface.cache_man.caches[cache][key]

                val = fun(db_iface, *args, **kwargs)

                db_iface.cache_man.caches[cache][key] = val
                return val
            return wrapped_fun
        return wrapper


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

    def create_relationship(self, from_node, to_node, rel_type, state=None):
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
    TIME_INDEX = "TIME_INDEX"

    def __init__(self, filename, neo4j_cfg):
        super(DBInterface, self).__init__()

        config_params = self._configure_neo4j(neo4j_cfg)

        from neo4j import GraphDatabase

        self.trans_lock = threading.Lock()
        self.mono_time = None
        try:
            self.db = GraphDatabase(filename, **config_params)
            self.file_index = None
            self.proc_index = None
            self.node_id_idx = None
            self.id_node = None
            self.sys_time = int(time.time())

            self.cache_man = CacheManager([CACHE_NAMES.LOCAL_GLOBAL,
                                           CACHE_NAMES.LAST_EVENT,
                                           CACHE_NAMES.VALID_LOCAL,
                                           CACHE_NAMES.NODE_BY_ID,
                                           CACHE_NAMES.IO_EVENT_CHAIN])

            with self.start_transaction():
                # Unique ID index
                if self.db.node.indexes.exists(DBInterface.UNIQ_ID_IDX):
                    uniq_id_idx = self.db.node.indexes.get(
                        DBInterface.UNIQ_ID_IDX)
                    id_nodes = uniq_id_idx['node']['UNIQ_ID']
                    if len(id_nodes) == 1:
                        self.id_node = id_nodes[0]
                    else:
                        raise UniqueIDException()
                else:
                    uniq_id_idx = self.db.node.indexes.create(
                        DBInterface.UNIQ_ID_IDX)
                    self.id_node = self.db.node()
                    self.id_node['serial_id'] = 0
                    uniq_id_idx['node']['UNIQ_ID'] = self.id_node

                # File index
                if self.db.node.indexes.exists(DBInterface.FILE_INDEX):
                    self.file_index = self.db.node.indexes.get(
                        DBInterface.FILE_INDEX)
                else:
                    self.file_index = self.db.node.indexes.create(
                        DBInterface.FILE_INDEX)

                # Process index
                if self.db.node.indexes.exists(DBInterface.PROC_INDEX):
                    self.proc_index = self.db.node.indexes.get(
                        DBInterface.PROC_INDEX)
                else:
                    self.proc_index = self.db.node.indexes.create(
                        DBInterface.PROC_INDEX)

            # Fix for the class load error when using multiple threads
            rows = self.db.query("START n=node(1) RETURN n")
            for row in rows:
                row['n']

        except Exception as exc:
            logging.error("Error: %s", str(exc))
            raise exc

    def _config_jvm(self, neo4j_cfg):
        '''Configures the JVM heap sizes'''
        max_jvm_heap_in_mb = 0.0
        min_jvm_heap_in_mb = 0.0

        if(neo4j_cfg['max_jvm_heap_size'] == 'default' or
           neo4j_cfg['min_jvm_heap_size'] == 'default'):
            logging.info("Proceeding with default NEO4J JVM settings")
            return

        if 'max_jvm_heap_size' in neo4j_cfg:
            if neo4j_cfg['max_jvm_heap_size'] in 'auto':
                logging.info("Calculating maximum JVM heap size "
                             "from available memory")
                vminfo = psutil.virtual_memory()
                max_jvm_heap_in_mb = ((neo4j_cfg['jvm_from_avail_mem'] *
                                      vminfo.available) / (1024 * 1024))
            else:
                max_jvm_heap_in_mb = neo4j_cfg['max_jvm_heap_size']
            logging.info("Max JVM heap size: %f MB", max_jvm_heap_in_mb)

        if 'min_jvm_heap_size' in neo4j_cfg:
            if neo4j_cfg['min_jvm_heap_size'] == 'auto':
                logging.info("Calculating minimum JVM heap size...")
                min_jvm_heap_in_mb = 0.25 * max_jvm_heap_in_mb
            else:
                min_jvm_heap_in_mb = neo4j_cfg['min_jvm_heap_size']
            logging.info("Min JVM heap size: %f MB", min_jvm_heap_in_mb)

        if max_jvm_heap_in_mb > min_jvm_heap_in_mb:
            logging.info("Setting max_heap: %f MB, min_heap: %f MB",
                         max_jvm_heap_in_mb, min_jvm_heap_in_mb)
            os.environ['NEO4J_PYTHON_JVMARGS'] = '-Xms%dM -Xmx%dM' % (
                int(min_jvm_heap_in_mb), int(max_jvm_heap_in_mb))
        else:
            logging.info("Max JVM heap is not greater than min JVM heap, "
                         "proceeding with default NEO4J JVM settings")

    def _config_buffer_cache(self, cfg, bcfg):
        '''Configures the buffer cache used by NEO4J'''
        buff_cache_size = bcfg['buffer_cache_size']

        if buff_cache_size == 'default':
            logging.info("Proceeding with default settings "
                         "for the NEO4J buffer cache")
            return
        elif buff_cache_size == 'auto':
            logging.info("Determining max buffer cache size from "
                         "available memory")
            vminfo = psutil.virtual_memory()
            buff_cache_size = ((bcfg['buff_cache_auto'] *
                                vminfo.available) / (1024 * 1024))

        logging.info("Max buffer cache size: %f MB", buff_cache_size)

        propstore = int(bcfg['propstore'] * buff_cache_size)
        cfg['neostore.propertystore.db.mapped_memory'] = str('%dM' %
                                                             (propstore))
        logging.info("neostore.propertystore.db.mapped_memory: %f MB",
                     propstore)

        nodestore = int(bcfg['nodestore'] * buff_cache_size)
        cfg['neostore.nodestore.db.mapped_memory'] = str('%dM' %
                                                         (nodestore))
        logging.info("neostore.nodestore.db.mapped_memory: %f MB",
                     nodestore)

        relstore = int(bcfg['relstore'] * buff_cache_size)
        cfg['neostore.relationshipstore.db.mapped_memory'] = str('%dM' %
                                                                 (relstore))
        logging.info("neostore.relationshipstore.db.mapped_memory: %f MB",
                     relstore)

        strings = int(bcfg['strings'] * buff_cache_size)
        cfg['neostore.propertystore.db.strings.mapped_memory'] = str('%dM' %
                                                                     (strings))
        logging.info("neostore.propertystore.db.strings.mapped_memory: %f MB",
                     strings)

        arrays = int(bcfg['arrays'] * buff_cache_size)
        cfg['neostore.propertystore.db.arrays.mapped_memory'] = str('%dM' %
                                                                    (arrays))
        logging.info("neostore.propertystore.db.arrays.mapped_memory: %f MB",
                     arrays)

    def _configure_neo4j(self, neo4j_cfg):
        '''Configures the JVM heap, Neo4j buffer cache size
        and other Neo4j parameters'''
        config_params = {}

        self._config_jvm(neo4j_cfg)
        self._config_buffer_cache(config_params, neo4j_cfg['buffer_cache'])

        if 'keep_logical_logs' in neo4j_cfg:
            if neo4j_cfg['keep_logical_logs']:
                config_params['keep_logical_logs'] = str('true')
            else:
                config_params['keep_logical_logs'] = str('false')

        if 'cache_type' in neo4j_cfg:
            config_params['cache_type'] = neo4j_cfg['cache_type']

        return config_params

    def close(self):
        '''Shutdown the database'''
        self.db.shutdown()

    def start_transaction(self):
        '''Returns a Neo4J transaction'''

        class TransactionWrapper(object):

            def __init__(self, lock, wraped):
                self.lock = lock
                self.wraped = wraped

            def __enter__(self, *args, **kwargs):
                self.lock.acquire()
                return self.wraped.__enter__(*args, **kwargs)

            def __exit__(self, *args, **kwargs):
                ret = self.wraped.__exit__(*args, **kwargs)
                self.lock.release()
                return ret

        return TransactionWrapper(self.trans_lock, self.db.transaction)

    def set_sys_time_for_msg(self, sys_time):
        '''Stores the system time passed in the header
        for each message being processed'''
        self.sys_time = sys_time
        self.mono_time = None

    def set_mono_time_for_msg(self, mono_time):
        self.mono_time = mono_time

    def create_node(self, node_type):
        '''Creates a node and sets the node ID, type and timestamp'''
        node = self.db.node()
        node_id = self.__get_next_id()
        node['node_id'] = node_id
        node['type'] = node_type
        node['sys_time'] = self.sys_time
        if node_type == NodeType.LOCAL:
            if self.mono_time is None:
                logging.error("Error: Attempted to use monotime in a function"
                              " that does not supply it.")
            node['mono_time'] = str(self.mono_time)
        return node

    def create_relationship(self, from_node, to_node, rel_type, state=None):
        '''Creates a relationship of given type'''
        rel = from_node.relationships.create(rel_type, to_node)
        if state is not None:
            rel['state'] = state
        else:
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
        hourly_bucket = sys_time_val - (sys_time_val % 3600)
        idx['time'][hourly_bucket] = glob_node

    def update_index(self, idx_type, idx_name, idx_key, idx_val):
        '''Adds value to a given index type with the name and key'''
        if idx_type == DBInterface.FILE_INDEX:
            self.file_index[idx_name][idx_key] = idx_val
        elif idx_type == DBInterface.PROC_INDEX:
            self.proc_index[idx_name][idx_key] = idx_val

    def __get_next_id(self):
        '''Returns a unique node ID'''
        node_id = None
        if self.id_node is not None:
            node_id = self.id_node['serial_id']
            self.id_node['serial_id'] = node_id + 1
            return node_id
        else:
            raise UniqueIDException()

    def find_and_del_rel(self, from_node, to_node):
        '''Finds a relation of type rel_type between two nodes
        and deletes it'''
        for rel in from_node.relationships.outgoing:
            if rel.end.id == to_node.id:
                rel.delete()

    def delete_relationship(self, rel):
        '''Deletes relatioship given a relationship object'''
        rel.delete()

    @CacheManager.dec(CACHE_NAMES.NODE_BY_ID,
                      lambda node_id: node_id)
    def get_node_by_id(self, node_id):
        '''Returns a node object given the ID'''
        _node = self.db.node[node_id]
        return _node

    def set_link_state(self, rel_list, status):
        '''Sets the link state to status'''
        for rel in rel_list:
            rel['state'] = status

    def query(self, qry, **kwargs):
        '''Executes query and returns result'''
        return self.db.query(qry, **kwargs)

    def locked_query(self, qry, **kwargs):
        '''Executes a query within a locking transaction.'''
        with self.trans_lock:
            return self.db.query(qry, **kwargs)
