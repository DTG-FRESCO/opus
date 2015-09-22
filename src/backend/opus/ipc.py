# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import collections
import Queue
import threading
import uuid

from . import common_utils

Message = collections.namedtuple("Message", ['id',
                                             'src',
                                             'dest',
                                             'type',
                                             'cont'])

MSG_TYPE = common_utils.enum(REQUEST=0,
                             RESPONSE=1,
                             ERROR=-1)


class QueuePair(object):
    def __init__(self, recv_queue, send_queue, watch_queue=None):
        self.recv = recv_queue
        self.send = send_queue
        self.watch = watch_queue

    def get(self, *args, **kwargs):
        return self.recv.get(*args, **kwargs)

    def put(self, msg, *args, **kwargs):
        if self.watch is not None:
            self.watch.put(msg.src)
        return self.send.put(msg, *args, **kwargs)

    @classmethod
    def create_pair(cls, queue_class=Queue.Queue,
                    watch_queue=None, queue_triple=False):
        roli = queue_class()
        rilo = queue_class()

        router_queue = cls(recv_queue=rilo,
                           send_queue=roli)
        if queue_triple:
            leaf_queue = (roli, rilo, watch_queue)
        else:
            leaf_queue = cls(recv_queue=roli,
                             send_queue=rilo,
                             watch_queue=watch_queue)
        return (router_queue, leaf_queue)


class Node(object):
    def __init__(self):
        self.thread = threading.Thread(target=self._main_loop)
        self.thread.daemon = True

    def _main_loop(self):
        raise NotImplementedError()

    def run_forever(self, threaded=True):
        if threaded:
            self.thread.start()
        else:
            self._main_loop()


class Client(Node):
    def __init__(self, ident, router=None,
                 queue_triple=None, queue_class=Queue.Queue):
        super(Client, self).__init__()
        self.ident = ident
        if queue_triple is not None:
            self.queue = QueuePair(*queue_triple)
        else:
            self.queue = router.add(ident, queue_class)

    def _main_loop(self):
        raise NotImplementedError()

    def _send(self, msg):
        self.queue.put(msg)

    def _get(self):
        return self.queue.get()


class Worker(Client):
    def __init__(self, handler, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.handler = handler

    def _main_loop(self):
        while True:
            msg = self._get()
            if msg.type == MSG_TYPE.REQUEST:
                ret = self.handler(msg)
                self._send(Message(id=msg.id,
                                   src=self.ident,
                                   dest=msg.src,
                                   type=MSG_TYPE.RESPONSE,
                                   cont=ret))
            elif msg.type == MSG_TYPE.RESPONSE:
                self._send(Message(id=msg.id,
                                   src=self.ident,
                                   dest=msg.src,
                                   type=MSG_TYPE.ERROR,
                                   cont="Sent RESPONSE type "
                                        "message to worker."))


class Master(Client):
    class Future(object):
        def __init__(self):
            self.ready = threading.Event()
            self.data = None

        def result(self):
            self.ready.wait()
            return self.data

        def fulfill(self, data):
            self.data = data
            self.ready.set()

    def __init__(self, *args, **kwargs):
        super(Master, self).__init__(*args, **kwargs)
        self.futures = {}

    def send(self, dest, msg):
        future = Master.Future()
        msg_id = uuid.uuid4().hex
        self.futures[msg_id] = future
        self._send(Message(id=msg_id,
                           src=self.ident,
                           dest=dest,
                           type=MSG_TYPE.REQUEST,
                           cont=msg))
        return future

    def _main_loop(self):
        while True:
            msg = self._get()
            if msg.type == MSG_TYPE.RESPONSE:
                self.futures[msg.id].fulfill(msg.cont)
                del self.futures[msg.id]
            elif msg.type == MSG_TYPE.REQUEST:
                self._send(Message(id=msg.id,
                                   src=self.ident,
                                   dest=msg.src,
                                   type=MSG_TYPE.ERROR,
                                   cont="Send REQUEST type "
                                        "message to master."))


class Router(Node):
    def __init__(self, queue_class=Queue.Queue):
        super(Router, self).__init__()
        self.clients = {}
        self.wait_queue = queue_class()

    def _main_loop(self):
        while True:
            elm = self.wait_queue.get()
            msg = self.clients[elm].get()
            if msg.dest in self.clients:
                self.clients[msg.dest].put(msg)
            else:
                self.clients[elm].put(Message(id=msg.id,
                                              src=None,
                                              dest=None,
                                              type=MSG_TYPE.ERROR,
                                              cont="That destination "
                                                   "does not exist."))

    def add(self, ident, queue_class=Queue.Queue, queue_triple=False):
        router, leaf = QueuePair.create_pair(queue_class,
                                             self.wait_queue,
                                             queue_triple)
        self.clients[ident] = router
        return leaf
