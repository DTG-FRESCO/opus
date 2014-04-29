# -*- coding: utf-8 -*-
'''
Utilities for manipulation of command control messages.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import struct

from opus import cc_msg_pb2


class BiDict(object):  # pylint: disable=R0903
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

    def __len__(self):
        '''Return the length of the dict.'''
        return len(self.dict)


def _msg_type_transcode(obj):
    '''Transform between either a message class or a message enum value.'''
    if not hasattr(_msg_type_transcode, "trans_dict"):
        trans_dict = BiDict()
        trans_dict[cc_msg_pb2.CMDCTL] = type(cc_msg_pb2.CmdCtlMessage())
        trans_dict[cc_msg_pb2.CMDCTLRSP] = type(cc_msg_pb2.CmdCtlMessageRsp())
        trans_dict[cc_msg_pb2.PSRSP] = type(cc_msg_pb2.PSMessageRsp())
        _msg_type_transcode.trans_dict = trans_dict
    return _msg_type_transcode.trans_dict[obj]


class RWPipePair(object):
    '''Pair of pipes that can be used to exchange data.'''
    def __init__(self, r_pipe, w_pipe):
        super(RWPipePair, self).__init__()
        self.r_pipe = r_pipe
        self.w_pipe = w_pipe

    def read(self):
        '''Reads a single message from the read pipe.'''
        hdr_size = struct.calcsize(str("@II"))
        hdr_buf = os.read(self.r_pipe, hdr_size)
        pay_len, pay_type = struct.unpack(str("@II"), hdr_buf)
        pay_buf = os.read(self.r_pipe, pay_len)
        pay_cls = _msg_type_transcode(pay_type)
        return pay_cls.FromString(pay_buf)

    def write(self, msg):
        '''Write a single message to the write pipe.'''
        msg_len = msg.ByteSize()
        msg_type = _msg_type_transcode(type(msg))
        buf = struct.pack(str("@II"), msg_len, msg_type)
        buf += msg.SerializeToString()
        os.write(self.w_pipe, buf)

    @classmethod
    def create_pair(cls):
        '''Creates a paired set of PW pipe pairs.'''
        (rd1, wr1) = os.pipe()
        (rd2, wr2) = os.pipe()

        pair1 = cls(rd1, wr2)
        pair2 = cls(rd2, wr1)
        return (pair1, pair2)


def send_cc_msg(sock, msg):
    '''Sends a command control message over the socket sock.'''
    msg_len = msg.ByteSize()
    msg_type = _msg_type_transcode(type(msg))
    buf = struct.pack(str("@II"), msg_len, msg_type)
    buf += msg.SerializeToString()
    sock.send(buf)


def __recv(sock, data_len):
    '''Recieves data of length data_len from socket sock.
    If the read from the socket fails at any point a IOError is thrown.'''
    buf = []
    size = data_len
    while size > 0:
        tmp = sock.recv(data_len)
        if tmp == "":
            raise IOError()
        buf += [tmp]
        size -= len(tmp)
    return "".join(buf)


def recv_cc_msg(sock):
    '''Receives a single command control message from the given socket sock.'''
    hdr_len = struct.calcsize(str("@II"))
    hdr_buf = __recv(sock, hdr_len)
    pay_len, pay_type = struct.unpack(str("@II"), hdr_buf)
    pay_buf = __recv(sock, pay_len)
    pay_cls = _msg_type_transcode(pay_type)
    pay = pay_cls.FromString(str(pay_buf))
    return pay
