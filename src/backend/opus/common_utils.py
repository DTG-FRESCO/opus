'''
Contains common classes and functions that can
be used by multiple modules in the OPUS backend
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import bisect
import collections
import copy
import logging
import time
import os

from . import uds_msg_pb2
from .exception import InvalidTagException


# Number of seconds to wait for a thread to join on shutdown.
THREAD_JOIN_SLACK = 30
FCNTL_F_DUPFD_CLOEXEC = 1030  # From header file fcntl.h

# Constants for tweaking memory usage
HEAP_PERCENT_MEM = 0.25
HEAP_USAGE_THRESHOLD = 0.90
MIN_PERCENT_AVAIL_MEM = 0.25
MAX_RSS_PERCENT_MEM = 0.35


class FixedDict(object):  # pylint: disable=R0903
    '''Ensures keys are fixed in the dictionary'''
    def __init__(self, dictionary):
        '''Take a copy of the dictionary'''
        super(FixedDict, self).__init__()
        self._dictionary = copy.deepcopy(dictionary)

    def __setitem__(self, key, item):
        '''Sets a value for a valid key'''
        if key not in self._dictionary:
            raise KeyError("The key {} is not defined.".format(key))
        self._dictionary[key] = item

    def __getitem__(self, key):
        '''Returns the value for a valid key'''
        if key not in self._dictionary:
            raise KeyError("The key {} is not defined.".format(key))
        return self._dictionary[key]

    def __delitem__(self, key):
        '''Removing items from fixed dict not allowed.'''
        raise NotImplementedError("Removing key from FixedDict not supported.")

    def __len__(self):
        '''Returns the length of the dictionary.'''
        return len(self._dictionary)


class IndexList(collections.MutableSequence):
    '''A list that maintains a bisectable index based on a key function.'''
    def __init__(self, key):
        self.key = key
        self.list = []
        self.index = []

    def insert(self, i, val):
        '''Insert an item into the list.'''
        self.list.insert(i, val)
        self.index.insert(i, self.key(val))

    def find(self, val, key=None):
        '''Find an items position in the list by bisecting the index.'''
        if key is None:
            return bisect.bisect(self.index, self.key(val))
        else:
            return bisect.bisect(self.index, key(val))

    def __getitem__(self, i):
        return self.list[i]

    def __setitem__(self, i, x):
        self.list[i] = x
        self.index[i] = self.key(x)

    def __delitem__(self, i):
        del self.list[i]
        del self.index[i]

    def __len__(self):
        return len(self.list)

    def __contains__(self, x):
        return x in self.list

    def __repr__(self):
        return str(self.index)


def meta_factory(base, tag, *args, **kwargs):
    '''Return an instance of the class
    derived from base with the name "tag"'''
    def compute_subs(cls):
        '''Compute the transitive colsure of
        the subclass relation on the given class'''
        sub_classes = [cls]
        for sub_class in cls.__subclasses__():
            sub_classes += compute_subs(sub_class)
        return sub_classes

    sub_classes = compute_subs(base)
    for sub_class in sub_classes:
        if sub_class.__name__ == tag:
            return sub_class(*args, **kwargs)
    raise InvalidTagException(tag)


def enum(**enums):
    '''Returns an enum class object'''
    enums['enum_str'] = staticmethod(lambda x: {val: key
                                                for key, val in enums.items()
                                               }[x])
    return type(str('Enum'), (), enums)


def get_payload_type(header):
    '''Returns the appropriate payload object'''
    pay_obj = None
    if header.payload_type == uds_msg_pb2.STARTUP_MSG:
        pay_obj = uds_msg_pb2.StartupMessage()
    elif header.payload_type == uds_msg_pb2.LIBINFO_MSG:
        pay_obj = uds_msg_pb2.LibInfoMessage()
    elif header.payload_type == uds_msg_pb2.FUNCINFO_MSG:
        pay_obj = uds_msg_pb2.FuncInfoMessage()
    elif header.payload_type == uds_msg_pb2.GENERIC_MSG:
        pay_obj = uds_msg_pb2.GenericMessage()
    elif header.payload_type == uds_msg_pb2.TERM_MSG:
        pay_obj = uds_msg_pb2.TermMessage()
    elif header.payload_type == uds_msg_pb2.TELEMETRY_MSG:
        pay_obj = uds_msg_pb2.FrontendTelemetry()
    elif header.payload_type == uds_msg_pb2.AGGREGATION_MSG:
        pay_obj = uds_msg_pb2.AggregationMessage()
    else:
        logging.error("Invalid payload type %d", header.payload_type)
    return pay_obj


def calc_exec_time(func):
    '''Decorator to measure function execution time'''
    if not hasattr(calc_exec_time, "counter"):
        calc_exec_time.counter = 0

    def timex(*args, **kw):
        '''Tracks the execution time of 'func'.'''
        start_time = time.clock()
        ret = func(*args, **kw)
        end_time = time.clock()
        calc_exec_time.counter = calc_exec_time.counter + 1
        print("%d - %s, %2.5f" % (calc_exec_time.counter,
                                  func.__name__,
                                  (end_time - start_time)))
        return ret
    return timex


def canonicalise_file_path(file_name):
    file_name = os.path.abspath(file_name)

    if os.path.isfile(file_name):
        file_name = os.path.realpath(file_name)
    else:
        print("File does not exist in the filesystem, "
              "cannot determine real path.")
    return file_name
