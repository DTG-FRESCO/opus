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

from opus import common_utils
from opus import prov_db_pb2 as prov_db


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
    '''Exception indicating that an invalid operation was invoked on a read-only
    transaction.'''
    def __init__(self):
        super(ReadOnlyException, self).__init__(
                               "Error: Invalid access of read-only transaction."
                                    )


OBJ_TYPE_MAP = {
    prov_db.ANNOT:prov_db.AnnotationObj,
    prov_db.EVENT:prov_db.EventObj,
    prov_db.GLOBAL:prov_db.GlobalObj,
    prov_db.LOCAL:prov_db.LocalObj,
    prov_db.META:prov_db.MetaObj,
    prov_db.PROCESS:prov_db.ProcObj,
    prov_db.TERM:prov_db.TermMarkerObj
}


def get_db_obj_class(obj_type):
    '''Given an object type identifier return either the matching class or raise
    UnknownObjectTypeException.'''
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
            # Try to lead existing DB
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
    '''A storage interface instance allows for access to a provenance database
    collection using a series of operations. It encapsulates the type of
    database and it's method of access.'''
    def __init__(self, db_type, db_args):
        super(StorageIFace, self).__init__()
        self.db_ref = common_utils.meta_factory(DBWrapper, db_type, **db_args)

    def close(self):
        '''Close all active database connections.'''
        pass

    def start_transaction(self, read_only=False):
        '''Return a fresh transaction object for the current database.'''
        if read_only:
            return ReadOnlyTransaction(self.db_ref)
        else:
            return DBTransaction(self.db_ref)

    def get_id_list_from_name(self, ename):
        '''Return the list of db_ids that match the given entity name in the
        index.'''
        pass

    def get_id_list_from_time_range(self, start, finish):
        '''Return a list of all db_ids within the given time range.'''
        pass
