'''
Contains common classes and functions that can
be used by multiple modules in the OPUS backend
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import copy
import logging
import threading
import functools
import os
import struct

from opus import uds_msg_pb2, cc_msg_pb2


'''Number of seconds to wait for a thread to join on shutdown.'''
THREAD_JOIN_SLACK = 30


class OPUSException(Exception):
    '''Simple exception handling class'''
    def __init__(self, msg):
        '''Initialize message'''
        super(OPUSException, self).__init__()
        self.msg = msg
    def __str__(self):
        '''Return message'''
        return self.msg


class InvalidTagException(OPUSException):
    '''Exception class to handle invalid tags'''
    def __init__(self, tag):
        '''Set the message in the base class'''
        super(InvalidTagException, self).__init__("Invalid tag: %s" % tag)


class FixedDict(object):
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


class BiDict(object):
    '''Implements a one-to-one mapping.'''
    def __init__(self):
        self.dict = {}

    def __getitem__(self, key):
        '''Retrieve the value associated with key.'''
        return self.dict[key]

    def __setitem__(self, key, value):
        '''Set the pair key and value.'''
        self.dict[key] = value
        self.dict[value] = key

    def __delitem__(self, key):
        '''Remove the pair including key.'''
        self.dict.pop(self.dict.pop(key))


def _cc_msg_type_transcode(obj):
    if not hasattr(_cc_msg_type_transcode, "trans_dict"):
        trans_dict = BiDict()
        trans_dict[cc_msg_pb2.CMDCTL] = type(cc_msg_pb2.CmdCtlMessage())
        trans_dict[cc_msg_pb2.CMDCTLRSP] = type(cc_msg_pb2.CmdCtlMessageRsp())
        trans_dict[cc_msg_pb2.PSRSP] = type(cc_msg_pb2.PSMessageRsp())
        _cc_msg_type_transcode.trans_dict = trans_dict
    return _cc_msg_type_transcode.trans_dict[obj]


class RWPipePair(object):
    '''Pair of pipes that can be used to exchange data.'''
    def __init__(self, r_pipe, w_pipe):
        super(RWPipePair, self).__init__()
        self.r_pipe = r_pipe
        self.w_pipe = w_pipe

    def read(self):
        hdr_size = struct.calcsize(str("@II"))
        hdr_buf = os.read(self.r_pipe, hdr_size)
        pay_len, pay_type = struct.unpack(str("@II"), hdr_buf)
        pay_buf = os.read(self.r_pipe, pay_len)
        pay_cls = _cc_msg_type_transcode(pay_type)
        return pay_cls.FromString(pay_buf)

    def write(self, msg):
        msg_len = msg.ByteSize()
        msg_type = _cc_msg_type_transcode(type(msg))
        buf = struct.pack(str("@II"), msg_len, msg_type)
        buf += msg.SerializeToString()
        os.write(self.w_pipe, buf)

    @classmethod
    def create_pair(cls):
        (rd1, wr1) = os.pipe()
        (rd2, wr2) = os.pipe()

        pair1 = cls(rd1, wr2)
        pair2 = cls(rd2, wr1)
        return (pair1, pair2)


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
    return type(str('Enum'), (), enums)


def analyser_lock(func):
    '''Decorator method for accessing analyser object'''
    if not hasattr(analyser_lock, "mutex"):
        analyser_lock.mutex = threading.Lock()
    @functools.wraps(func)
    def deco(self, *args, **kwargs):
        '''Wraps function call with lock acquire and release'''
        with analyser_lock.mutex:
            return func(self, *args, **kwargs)
    return deco


def header_size():
    '''Creates a header object and returns the object size'''
    if hasattr(header_size, "size"):
        return header_size.size
    header = uds_msg_pb2.Header()
    header.timestamp = 0
    header.pid = 0
    header.tid = 0
    header.payload_type = 0
    header.payload_len = 0
    header_size.size = header.ByteSize()
    return header_size.size


def get_payload_type(header):
    '''Returns the appropriate payload object'''
    if header.payload_type == uds_msg_pb2.STARTUP_MSG:
        return uds_msg_pb2.StartupMessage()
    elif header.payload_type == uds_msg_pb2.LIBINFO_MSG:
        return uds_msg_pb2.LibInfoMessage()
    elif header.payload_type == uds_msg_pb2.FUNCINFO_MSG:
        return uds_msg_pb2.FuncInfoMessage()
    elif header.payload_type == uds_msg_pb2.GENERIC_MSG:
        return uds_msg_pb2.GenericMessage()
    elif header.payload_type == uds_msg_pb2.TERM_MSG:
        return uds_msg_pb2.TermMessage()
    elif header.payload_type == uds_msg_pb2.TELEMETRY_MSG:
        return uds_msg_pb2.FrontendTelemetry()
    else:
        logging.error("Invalid payload type %d", header.payload_type)
