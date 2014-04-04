# -*- coding: utf-8 -*-
'''
Module containing classes related to enforcing orderings upon messages.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import Queue
import threading
import time

from opus import common_utils


class QueueClearingException(common_utils.OPUSException):
    '''Exception raised when attempting to put an item into a queue that is
    being cleared.'''
    def __init__(self):
        super(QueueClearingException, self).__init__(
            "Cannot insert message, queue clearing."
        )


def _cur_time():
    '''Returns the current monotonic time in milliseconds.'''
    return time.clock_gettime(time.CLOCK_MONOTONIC_RAW) * 1000000


class EventOrderer(object):
    '''In memory priority queue to order messages'''
    _EMWA_CONSTANT = 0.9

    def __init__(self, max_wind):
        super(EventOrderer, self).__init__()
        self.priority_queue = Queue.PriorityQueue()
        self.q_over_min = threading.Condition()
        self.max_wind = max_wind
        self.last_time = _cur_time()
        self.inter = 1
        self.min_inter = 100000
        self.clearing = False

    def _update_inter(self):
        '''Update the queues interval count.'''
        t_now = _cur_time()
        t_diff = (t_now - self.last_time)
        self.last_time = t_now
        self.inter = (self.inter * self._EMWA_CONSTANT +
                      t_diff * (1 - self._EMWA_CONSTANT))
        if self.inter < self.min_inter:
            self.min_inter = self.inter

    def _window_size(self):
        '''Return the current minimum window size.'''
        return max(self.max_wind * (self.min_inter / self.inter),
                   self.max_wind)

    def _extract_cond(self):
        '''Evaluate the extraction condition, queue_size > min_window'''
        return (self.clearing or
                self.priority_queue.qsize() > self._window_size())

    def push(self, msgs):
        '''Push a list of messages msgs onto the queue.'''
        with self.q_over_min:
            if self.clearing:
                raise QueueClearingException()
            for (pri, val) in msgs:
                self.priority_queue.put((pri, val), False)
            self._update_inter()
            if self._extract_cond():
                self.q_over_min.notify()

    def pop(self):
        '''Pop the message from the queue with the lowest priority.'''
        with self.q_over_min:
            while not self._extract_cond():
                self.q_over_min.wait()
            item = self.priority_queue.get(False)
            return item

    def start_clear(self):
        '''Clear the queue of message returning all remaining messages as a
        list.'''
        with self.q_over_min:
            self.clearing = True
            self.q_over_min.notify()

    def stop_clear(self):
        '''Stop a queue clear and resume normal activities.'''
        with self.q_over_min:
            self.clearing = False

    def get_queue_size(self):
        '''Returns queue size'''
        return self.priority_queue.qsize()
