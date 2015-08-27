# -*- coding: utf-8 -*-
'''
Utilities for manipulation of command control messages.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import json
import os
import socket
import struct

from .exception import BackendConnectionError

CC_HDR = struct.Struct(str("@I"))


class RWPipePair(object):
    '''Pair of pipes that can be used to exchange data.'''
    def __init__(self, r_pipe, w_pipe):
        super(RWPipePair, self).__init__()
        self.r_pipe = r_pipe
        self.w_pipe = w_pipe

    def read(self):
        '''Reads a single message from the read pipe.'''
        hdr_buf = os.read(self.r_pipe, CC_HDR.size)
        pay_len = CC_HDR.unpack(hdr_buf)[0]
        pay_buf = os.read(self.r_pipe, pay_len)
        return json.loads(pay_buf)

    def write(self, msg):
        '''Write a single message to the write pipe.'''
        msg_txt = json.dumps(msg)
        buf = CC_HDR.pack(len(msg_txt))
        buf += msg_txt
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
    msg_txt = json.dumps(msg)
    buf = CC_HDR.pack(len(msg_txt))
    buf += msg_txt
    sock.send(buf)


def __recv(sock, data_len):
    '''Recieves data of length data_len from socket sock.
    If the read from the socket fails at any point a IOError is thrown.'''
    buf = []
    size = data_len
    while size > 0:
        tmp = sock.recv(data_len)
        if tmp == str(""):
            raise IOError()
        buf += [tmp]
        size -= len(tmp)
    return str("").join(buf)


def recv_cc_msg(sock):
    '''Receives a single command control message from the given socket sock.'''
    hdr_buf = __recv(sock, CC_HDR.size)
    pay_len = CC_HDR.unpack(hdr_buf)[0]
    pay_buf = __recv(sock, pay_len)
    pay = json.loads(pay_buf)
    return pay


class CommandConnectionHelper(object):
    '''Manages a connection to the backend and provides helpers for making
    requests.'''
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def make_request(self, msg):
        '''Sends a request message to the backend and retrieves a response.'''
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.connect((self.host, self.port))
        except IOError as exc:
            raise BackendConnectionError("Failed to make contact with "
                                         "the backend: %s" % exc)

        try:
            send_cc_msg(conn, msg)
        except IOError as exc:
            raise BackendConnectionError("Failed to send message to backend:"
                                         " %s" % exc)
        try:
            return recv_cc_msg(conn)
        except IOError as exc:
            raise BackendConnectionError("Failed to receive message from"
                                         " backend: %s" % exc)
