# -*- coding: utf-8 -*-
'''
This module fetches provenance data from the producer
via a multiprocessing queue. It also starts an analyser
thread using configuration information and communicates
provenance data to with via a priority queue.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import multiprocessing
import Queue
import logging

from . import config_util


class AnalyserController(multiprocessing.Process):
    '''Controller class that fetches data from the producer
    and hands it out to the analyser for processing'''
    def __init__(self, pf_queue, config):
        multiprocessing.Process.__init__(self)
        self.pf_queue = pf_queue
        self.config = config
        self.drop = False
        self.stop_event = multiprocessing.Event()
        self.analyser = None

    def run(self):
        from . import analysis
        self.analyser = config_util.load_module(self.config, "Analyser",
                                                analysis.Analyser)
        if __debug__:
            logging.debug("Starting analyser....")
        self.analyser.start()

        while True:
            try:
                msg = self.pf_queue.dequeue()
                self.analyser.put_msg(msg)
            except Queue.Empty:
                if (self.stop_event.is_set() and
                    self.pf_queue.get_queue_size() == 0):
                    break

        if __debug__:
            logging.debug("Shutting down analyser....")

        if self.analyser.do_shutdown(self.drop):
            if __debug__:
               logging.debug("Analyser has successfully shutdown")
        else:
            if __debug__:
                logging.debug("Failed to shutdown analyser")

    def snapshot_shutdown(self):
        '''Tells the analyser take a snaphot of its state and shutdown'''
        pass

    def do_shutdown(self, drop):
        '''Initiates shutdown of analyser controller'''
        self.drop = drop
        self.stop_event.set()

