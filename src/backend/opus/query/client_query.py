# -*- coding: utf-8 -*-
'''
TODO
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging
from opus import (cc_msg_pb2)

class ClientQueryControl(object):
    client_qry_methods = {}

    @classmethod
    def register_query_method(cls, query_method):
        def wrap(method):
            cls.client_qry_methods[query_method] = method
            return method
        return wrap

    @classmethod
    def exec_method(cls, db_iface, msg):
        if msg.qry_method in cls.client_qry_methods:
            return cls.client_qry_methods[msg.qry_method](db_iface, msg)
        else:
            rsp = cc_msg_pb2.ExecQueryMethodRsp()
            rsp.error = "Invalid command name."
            return rsp
