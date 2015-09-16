# -*- coding: utf-8 -*-
'''
This module wraps the python Queue class with helper methods
necessary to work in a single producer and consumer scenario.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import logging

from multiprocessing import Queue as MPQueue, Event, Condition

class ProducerFetcherQueue(object):
    '''Wrapper around multiprocessing Queue'''

    def __init__(self):
        super(ProducerFetcherQueue, self).__init__()
        self.pf_queue = MPQueue()
        self.pfq_cond = Condition()
        self.clear_event = Event()

    def enqueue(self, msg):
        with self.pfq_cond:
            if self.clear_event.is_set():
                logging.debug("Cannot enqueue, queue is in clearing mode")
                return
            self.pf_queue.put(msg)
            self.pfq_cond.notify()

    def dequeue(self):
        with self.pfq_cond:
            while not (self.clear_event.is_set() or
                       self.pf_queue.qsize() > 0):
                if __debug__:
                    logging.debug("Waiting on queue condition")
                self.pfq_cond.wait()
            return self.pf_queue.get(False)

    def start_clear(self):
        with self.pfq_cond:
            self.clear_event.set()
            self.pfq_cond.notify()

    def snapshot_queue(self):
        '''Write queue contents to file'''
        pass

    def get_queue_size(self):
        return self.pf_queue.qsize()
