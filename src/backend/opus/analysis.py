# -*- coding: utf-8 -*-
'''
This module performs the analysis of incoming
provenance data sent by the producer. Various
types of analysers have been defined in this file.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import Queue
import os
import logging
import threading
import time
import opuspb  # pylint: disable=W0611


from opus import common_utils, storage, order, messaging
from opus import uds_msg_pb2 as uds_msg
from opus.pvm import posix


class Analyser(threading.Thread):
    '''Base class for the analyser'''
    def __init__(self, *args, **kwargs):
        '''Initialize class members'''
        super(Analyser, self).__init__(*args, **kwargs)
        self.stop_event = threading.Event()
        self.daemon = True

    def run(self):
        '''Should be overridden in the derived class'''
        pass

    def put_msg(self, msg_data):
        '''Should be overridden in the derived class'''
        pass

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        if __debug__:
            logging.debug("Shutting down thread....")
        self.stop_event.set()
        try:
            self.join(common_utils.THREAD_JOIN_SLACK)
        except RuntimeError as exc:
            logging.error("Failed to shutdown thread sucessfully.")
            logging.error(exc)
            return False
        return not self.isAlive()


class LoggingAnalyser(Analyser):
    '''Implementation of a logging analyser'''
    def __init__(self, log_path, *args, **kwargs):
        '''Initialize class members'''
        super(LoggingAnalyser, self).__init__(*args, **kwargs)
        self.file_object = None
        self.logfile_path = log_path

        try:
            self.file_object = open(self.logfile_path, "ab+")
        except IOError as (err, msg):
            logging.error("Error: %d, Message: %s", err, msg)
            raise common_utils.OPUSException("log file open error")
        if __debug__:
            logging.debug("Opened file %s", self.logfile_path)

    def put_msg(self, msg_list):
        '''Takes a list of tuples (header, payload)
        and writes them to a file'''
        for msg in msg_list:
            if msg[0] and msg[1]:
                self.file_object.write(msg[0])
                self.file_object.write(msg[1])
        self.file_object.flush()

    def do_shutdown(self):
        '''Flush all pending writes to disk
        and close the file object'''
        os.fsync(self.file_object.fileno())
        self.file_object.close()
        return True


class OrderingAnalyser(Analyser):
    '''The ordering analyser implements a event ordering queue and calls the
    process method to consume messages.'''
    def __init__(self, *args, **kwargs):
        super(OrderingAnalyser, self).__init__(*args, **kwargs)
        # TODO(tb403) - Proper max_wind
        self.event_orderer = order.EventOrderer(50)
        self.queue_cleared = threading.Event()

    def run(self):
        '''Pull events from the queue and process them as long as the
        stop_event is not set.'''
        while not self.stop_event.is_set():
            try:
                _, msg = self.event_orderer.pop()
                self.process(msg)
            except Queue.Empty:
                if __debug__:
                    logging.debug("T:Queue cleared, clearing state tables.")
                self.queue_cleared.set()
                self.cleanup()
                if __debug__:
                    logging.debug("T:Preparing to wait for clear completion.")
                while self.queue_cleared.is_set():
                    time.sleep(0)
                if __debug__:
                    logging.debug("T:Clear completed.")
                continue

    def do_shutdown(self):
        '''Clear the event orderer and then shutdown the processing thread.'''
        if __debug__:
            logging.debug("M:Shutting down analyser.")
            logging.debug("M:Starting queue flush.")
        self.event_orderer.start_clear()
        if __debug__:
            logging.debug("M:Waiting for queue flush completion.")
        self.queue_cleared.wait()
        if __debug__:
            logging.debug("M:Stopping thread.")
        self.stop_event.set()
        if __debug__:
            logging.debug("M:Completing flush.")
        self.queue_cleared.clear()
        return super(OrderingAnalyser, self).do_shutdown()

    def put_msg(self, msg_list):
        '''Place a set of messages onto the queue, clearing the queue if any
        blank markers are found.'''
        msg_chunk = []
        for hdr, pay in msg_list:
            hdr_obj = messaging.Header()
            hdr_obj.loads(hdr)

            msg_chunk += [(hdr_obj.timestamp, (hdr, pay))]

            if hdr_obj.payload_type == uds_msg.TERM_MSG:
                if __debug__:
                    logging.debug("M:Received term message.")
                    logging.debug("M:Pushing remaining message chunk.")
                    logging.debug("M:Message chunk length:%d", len(msg_chunk))
                self.event_orderer.push(msg_chunk)
                msg_chunk = []
                if __debug__:
                    logging.debug("M:Signalling queue clear.")
                self.event_orderer.start_clear()
                if __debug__:
                    logging.debug("M:Waiting for completion.")
                self.queue_cleared.wait()
                if __debug__:
                    logging.debug("M:Stopping clear.")
                self.event_orderer.stop_clear()
                if __debug__:
                    logging.debug("M:Signalling clear completed.")
                self.queue_cleared.clear()
                if __debug__:
                    logging.debug("M:Queue cleared, continuing.")

        self.event_orderer.push(msg_chunk)

    def cleanup(self):
        '''Run any code that needs to happen whenever the queue is cleared.'''
        raise NotImplementedError()

    def process(self, (hdr, pay)):
        '''Process a single message.'''
        raise NotImplementedError()


class PVMAnalyser(OrderingAnalyser):
    '''The PVM analyser class implements the core of the PVM model, including
    the significant operations and their interactions with the underlying
    storage system.'''
    def __init__(self, storage_type, storage_args, *args, **kwargs):
        super(PVMAnalyser, self).__init__(*args, **kwargs)
        self.storage_iface = common_utils.meta_factory(storage.StorageIFace,
                                                storage_type, **storage_args)

    def run(self):
        '''Run a standard processing loop, also close the storage interface
        once it is complete.'''
        super(PVMAnalyser, self).run()
        self.storage_iface.close()

    def cleanup(self):
        '''Clear the process data structures.'''
        posix.handle_cleanup()

    def process(self, (hdr, pay)):
        '''Process a single front end message, applying it's effects to the
        database.'''
        hdr_obj = messaging.Header()
        hdr_obj.loads(hdr)
        pay_obj = common_utils.get_payload_type(hdr_obj)
        pay_obj.ParseFromString(pay)

        # Set system time for current message
        self.storage_iface.set_sys_time_for_msg(hdr_obj.sys_time)

        with self.storage_iface.start_transaction():
            if hdr_obj.payload_type == uds_msg.FUNCINFO_MSG:
                posix.handle_function(self.storage_iface, hdr_obj.pid, pay_obj)
            elif hdr_obj.payload_type == uds_msg.STARTUP_MSG:
                posix.handle_process(self.storage_iface, hdr_obj, pay_obj)
            elif hdr_obj.payload_type == uds_msg.GENERIC_MSG:
                if pay_obj.msg_type == uds_msg.DISCON:
                    posix.handle_disconnect(hdr_obj.pid)
                elif pay_obj.msg_type == uds_msg.PRE_FUNC_CALL:
                    posix.handle_prefunc(hdr_obj.pid, pay_obj)
            elif hdr_obj.payload_type == uds_msg.TERM_MSG:
                    posix.handle_startup(self.storage_iface, pay_obj)
