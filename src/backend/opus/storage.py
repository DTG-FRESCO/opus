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

from opus import common_utils
from opus import prov_db_pb2 as prov_db
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
                                CLOEXEC = 9)



class AlreadyCommittedException(common_utils.OPUSException):
    '''Exception indicating that an operation is being attempted on a
    transaction that has already been committed.'''
    def __init__(self):
        super(AlreadyCommittedException, self).__init__(
            "Error: Transaction already committed."
        )


class UnknownObjectTypeException(common_utils.OPUSException):
    '''Exception indicating that a object type lookup failed to be matched.'''
    def __init__(self):
        super(UnknownObjectTypeException, self).__init__(
            "Error: Unknown db object type referefence."
        )


class ReadOnlyException(common_utils.OPUSException):
    '''Exception indicating that an invalid operation was invoked on a
    read-only transaction.'''
    def __init__(self):
        super(ReadOnlyException, self).__init__(
            "Error: Invalid access of read-only transaction."
        )

class UniqueIDException(common_utils.OPUSException):
    '''Exception when unique ID cannot be generated'''
    def __init__(self):
        super(UniqueIDException, self).__init__(
            "Error: Unique ID generation error"
        )


OBJ_TYPE_MAP = {
    prov_db.ANNOT: prov_db.AnnotationObj,
    prov_db.EVENT: prov_db.EventObj,
    prov_db.GLOBAL: prov_db.GlobalObj,
    prov_db.LOCAL: prov_db.LocalObj,
    prov_db.META: prov_db.MetaObj,
    prov_db.PROCESS: prov_db.ProcObj,
    prov_db.TERM: prov_db.TermMarkerObj
}


def get_db_obj_class(obj_type):
    '''Given an object type identifier return either the matching class or
    raise UnknownObjectTypeException.'''
    if obj_type in OBJ_TYPE_MAP:
        return OBJ_TYPE_MAP[obj_type]
    else:
        raise UnknownObjectTypeException()


class BatchWrapper(object):
    '''Wrapper for a batch operation on a database.'''
    def put(self, key, value):
        '''Write the given value for the given key.'''
        raise NotImplementedError()

    def delete(self, key):
        '''Remove the given key.'''
        raise NotImplementedError()


class LevelBatch(BatchWrapper):
    '''Batch object for levelDB database interfaces.'''
    def __init__(self):
        super(LevelBatch, self).__init__()
        self.batch = leveldb.WriteBatch()

    def put(self, key, value):
        self.batch.Put(key, value)

    def delete(self, key):
        self.batch.Delete(key)


class DBWrapper(object):
    '''Wrapper for a database interface object.'''
    def put(self, key, value):
        '''Write the given value to the given key in the database.'''
        raise NotImplementedError()

    def get(self, key):
        '''Retrieve the value associated with the given key from the
        database.'''
        raise NotImplementedError()

    def delete(self, key):
        '''Remove the given key from the database.'''
        raise NotImplementedError()

    def write(self, batch):
        '''Commit the given batch to the database.'''
        raise NotImplementedError()

    def iter(self, from_key, to_key):
        '''Return an iterator over the range from_key->to_key.'''
        raise NotImplementedError()

    def start_batch(self):
        '''Return a BatchWrapper object for the given database.'''
        raise NotImplementedError()


class LevelDBWrapper(DBWrapper):
    '''Interface to a levelDB database.'''
    def __init__(self, filename):
        super(LevelDBWrapper, self).__init__()
        try:
            # Try to load existing DB
            self.db_ref = leveldb.LevelDB(filename, create_if_missing=False)
        except leveldb.LevelDBError:
            # No existing DB, so create one.
            self.db_ref = leveldb.LevelDB(filename)
            for obj_type in OBJ_TYPE_MAP:
                self.db_ref.Put(to_int64(comp_id(0xFF, obj_type)), to_int64(0))

    def put(self, key, value):
        self.db_ref.Put(key, value)

    def get(self, key):
        return self.db_ref.Get(key)

    def delete(self, key):
        self.db_ref.Delete(key)

    def write(self, batch):
        self.db_ref.Write(batch.batch)

    def iter(self, from_key, to_key):
        return self.db_ref.RangeIter(from_key, to_key)

    def start_batch(self):
        return LevelBatch()


def to_int64(val):
    '''Pack a python int into a big-endian int64.'''
    return struct.pack(str(">Q"), val)


def from_int64(data):
    '''Unpack a big-endian int64 into a python int.'''
    return struct.unpack(str(">Q"), data)[0]


def comp_id(obj_type, obj_id):
    '''Given a type identifier and id comput the full id.'''
    return (obj_type << 56) + obj_id


def derv_type(obj_id):
    '''Given an object ID return the type identifier.'''
    return (obj_id >> 56)


def commit_wrapper(func):
    '''Decorator to add already committed checking to a function.'''
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        '''commit_wrapper internal.'''
        if self.db_ref is None or self.batch is None:
            raise AlreadyCommittedException()
        return func(self, *args, **kwargs)
    wrapper.internal_fn = func
    return wrapper


class DBTransaction(object):
    '''Database transaction manager.'''
    def __init__(self, db_ref):
        super(DBTransaction, self).__init__()
        self.db_ref = db_ref
        self.batch = db_ref.start_batch()
        self.id_map = {}
        self.name_map = {}
        self.obj_map = {}
        for obj_type in OBJ_TYPE_MAP:
            obj_type_key = to_int64(comp_id(0xFF, obj_type))
            self.id_map[obj_type] = from_int64(self.db_ref.get(obj_type_key))

    @commit_wrapper
    def get(self, db_id, cache=True):
        '''Return the object matching the given db_id.'''
        if db_id in self.obj_map:
            return self.obj_map[db_id]
        obj = self.db_ref.get(to_int64(db_id))
        obj_type = derv_type(db_id)
        try:
            obj_cls = get_db_obj_class(obj_type)
            obj_real = obj_cls.FromString(obj)
            if cache:
                self.obj_map[db_id] = obj_real
            return obj_real
        except UnknownObjectTypeException:
            return obj

    @commit_wrapper
    def put(self, db_id, obj):
        '''Insert obj into the database with key db_id.'''
        self.batch.put(to_int64(db_id), obj.SerializeToString())

    @commit_wrapper
    def create(self, obj_type):
        '''Create an object of type obj_type in the database, return a tuple
        of the object and its id.'''
        obj = get_db_obj_class(obj_type)()

        new_obj_id = self.id_map[obj_type] + 1
        self.id_map[obj_type] = new_obj_id

        new_real_id = comp_id(obj_type, new_obj_id)

        self.obj_map[new_real_id] = obj

        packed_real = to_int64(new_real_id)
        self.batch.put(packed_real, obj.SerializeToString())
        return (new_real_id, obj)

    @commit_wrapper
    def name_get(self, name):
        '''Retrieve the ID mapping for the given entity name.'''
        if name in self.name_map:
            return self.name_map[name]
        sha = hashlib.new('sha256')
        sha.update(name)
        db_id = struct.pack(str(">B"), 0xFE) + sha.digest()
        try:
            return from_int64(self.db_ref.get(db_id))
        except KeyError:
            return None

    @commit_wrapper
    def name_put(self, name, obj_id):
        '''Update the ID mapping for the given entity name.'''
        sha = hashlib.new('sha256')
        sha.update(name)
        db_id = struct.pack(str(">B"), 0xFE) + sha.digest()
        packed_id = to_int64(obj_id)
        self.batch.put(db_id, packed_id)
        self.name_map[name] = obj_id

    @commit_wrapper
    def id_state(self):
        '''Displays the current state of the ID mappings for the database.'''
        return self.id_map

    @commit_wrapper
    def commit(self):
        '''Commit the transaction to the database.'''
        for obj_type in OBJ_TYPE_MAP:
            id_key = comp_id(0xFF, obj_type)
            id_val = self.id_map[obj_type]
            self.batch.put(to_int64(id_key), to_int64(id_val))

        for o_id in self.obj_map:
            self.put(o_id, self.obj_map[o_id])

        self.db_ref.write(self.batch)
        self.db_ref = None
        self.batch = None


class ReadOnlyTransaction(DBTransaction):
    '''Implemenets a read-only transaction that forbids any mutating
    operation.'''
    def __init__(self, db_ref):
        self.db_ref = db_ref
        self.obj_map = []
        self.name_map = []

    def get(self, db_id):
        '''Forwards read actions to it's base class after ensuring the cache
        flag to be false.'''
        return super(ReadOnlyTransaction, self).get.internal_fn(self,
                                                                db_id,
                                                                False)

    def put(self, db_id, obj):
        raise ReadOnlyException()

    def create(self, obj_type):
        raise ReadOnlyException()

    def name_put(self, name, obj_id):
        raise ReadOnlyException()

    def commit(self):
        raise ReadOnlyException()


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

    def __init__(self, filename):
        super(Neo4JInterface, self).__init__()
        try:
            self.db = GraphDatabase(filename)
            self.file_index = None
            self.proc_index = None
            self.node_id_idx = None
            self.id_node = None

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

        except Exception as e:
            logging.error("Error: %s", str(e))


    def close(self):
        '''Shutdown the database'''
        self.db.shutdown()


    def start_transaction(self):
        '''Returns a Neo4J transaction'''
        return self.db.transaction


    def create_node(self, node_type):
        '''Creates a node and sets the node type'''
        node = self.db.node()
        node_id = self.get_next_id()
        node['node_id'] = node_id
        node['type'] = node_type

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
        node_id = 0
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
        qry = "START n=node:FILE_INDEX('name:" + name + "') "
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

        qry = "START loc_node=node(" + str(loc_node.id) + ") "
        qry += "MATCH loc_node<-[rel:LOC_OBJ]-glob_node "
        qry += "RETURN glob_node, rel"

        rows = self.db.query(qry)
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

        qry = "START proc_node=node(" + str(proc_node.id) + ") "
        qry += "MATCH proc_node<-[lp_rel:PROC_OBJ]-loc_node "
        qry += "WHERE lp_rel.state <> " + str(LinkState.CLOSED)
        qry += " AND loc_node.name = '" + loc_name + "' "
        qry += "RETURN loc_node, lp_rel "
        qry += "ORDER by loc_node.node_id DESC limit 1"

        rows = self.db.query(qry)
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


