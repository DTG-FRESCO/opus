'''
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import os
import re
import socket


class MultiFamilySocket(object):
    def __init__(self, sock_type, addr=None):
        self.socket = None
        self.sock_type = sock_type
        self.address = None
        self.family = None
        if addr is not None:
            self._setup_socket(addr)

    def _parse_address(self, addr):
        tcp = re.match(r"tcp://(.*):(\d*)", addr)
        if tcp:
            self.family = socket.AF_INET
            self.address = (tcp.groups()[0], int(tcp.groups()[1]))
            return

        unix = re.match(r"unix://(.*)", addr)
        if unix:
            self.family = socket.AF_UNIX
            self.address = unix.group(1)
            return

        raise IOError("Invalid address format")

    def _setup_socket(self, addr):
        self._parse_address(addr)
        self.socket = socket.socket(self.family, self.sock_type)

    def bind(self, address):
        if self.socket is None:
            self._setup_socket(address)
        if(self.family == socket.AF_UNIX and os.path.exists(self.address)):
            os.unlink(self.address)
        return self.socket.bind(self.address)

    def connect(self, address):
        if self.socket is None:
            self._setup_socket(address)
        return self.socket.connect(self.address)

    def close(self):
        self.socket.close()
        if(self.family == socket.AF_UNIX and os.path.exists(self.address)):
            os.unlink(self.address)

    def __getattr__(self, name):
        return getattr(self.socket, name)
