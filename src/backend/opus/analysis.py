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


from opus import common_utils, storage, order
from opus import uds_msg_pb2 as uds_msg
from opus.pvm import posix


class Analyser(threading.Thread):
    '''Base class for the analyser'''
    def __init__(self, *args, **kwargs):
        '''Initialize class members'''
        super(Analyser, self).__init__(*args, **kwargs)
        self.stop_event = threading.Event()

    def run(self):
        '''Should be overridden in the derived class'''
        pass

    def put_msg(self, msg_data):
        '''Should be overridden in the derived class'''
        pass

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        logging.debug("Shutting down thread....")
        self.stop_event.set()
        try:
            self.join(common_utils.THREAD_JOIN_SLACK)
        except RuntimeError as exc:
            logging.error("Failed to shutdown thread sucessfully.")
            logging.error(exc)
            return False
        return not self.isAlive()


def create_blank_marker():
    '''Create a blank message to be inserted as a break into the log.'''
    logging.debug("Creating blank message.")
    if hasattr(create_blank_marker, "blank_msg"):
        return create_blank_marker.blank_msg

    header = uds_msg.Header()
    header.timestamp = 0
    header.pid = 0
    header.tid = 0
    header.payload_type = uds_msg.BLANK_MSG
    header.payload_len = 0

    create_blank_marker.blank_msg = header.SerializeToString()

    return create_blank_marker.blank_msg


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
        logging.debug("Opened file %s", self.logfile_path)

        #Write a blank sentinal to the file.
        self.file_object.write(create_blank_marker())

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


class OrderingAnalyser(Analyser):
    '''The ordering analyser implements a event ordering queue and calls the
    process method to consume messages.'''
    def __init__(self, *args, **kwargs):
        super(OrderingAnalyser, self).__init__(*args, **kwargs)
        self.event_orderer = order.EventOrderer(50) #TODO - Proper max_wind
        self.queue_cleared = threading.Event()

    def run(self):
        '''Pull events from the queue and process them as long as the stop_event
        is not set.'''
        while not self.stop_event.is_set():
            try:
                _, msg = self.event_orderer.pop()
                self.process(msg)
            except Queue.Empty:
                logging.debug("T:Queue cleared, clearing state tables.")
                self.queue_cleared.set()
                self.cleanup()
                logging.debug("T:Preparing to wait for clear completion.")
                while self.queue_cleared.is_set():
                    time.sleep(0)
                logging.debug("T:Clear completed.")
                continue

    def do_shutdown(self):
        '''Clear the event orderer and then shutdown the processing thread.'''
        logging.debug("M:Shutting down analyser.")
        logging.debug("M:Starting queue flush.")
        self.event_orderer.start_clear()
        logging.debug("M:Waiting for queue flush completion.")
        self.queue_cleared.wait()
        logging.debug("M:Stopping thread.")
        self.stop_event.set()
        logging.debug("M:Completing flush.")
        self.queue_cleared.clear()
        super(OrderingAnalyser, self).do_shutdown()

    def put_msg(self, msg_list):
        '''Place a set of messages onto the queue, clearing the queue if any
        blank markers are found.'''
        msg_chunk = []
        for hdr, pay in msg_list:
            hdr_obj = uds_msg.Header()
            hdr_obj.ParseFromString(hdr)
            pay_obj = common_utils.get_payload_type(hdr_obj)
            pay_obj.ParseFromString(pay)

            if hdr_obj.payload_type == 0:
                logging.debug("M:Received blank message.")
                logging.debug("M:Pushing remaining message chunk.")
                logging.debug("M:Message chunk length:%d", len(msg_chunk))
                self.event_orderer.push(msg_chunk)
                logging.debug("M:Signalling queue clear.")
                self.event_orderer.start_clear()
                logging.debug("M:Waiting for completion.")
                self.queue_cleared.wait()
                logging.debug("M:Stopping clear.")
                self.event_orderer.stop_clear()
                logging.debug("M:Signalling clear completed.")
                self.queue_cleared.clear()
                logging.debug("M:Queue cleared, continuing.")
            else:
                msg_chunk += [(hdr_obj.timestamp, (hdr_obj, pay_obj))]
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
    def __init__(self, storage_args, *args, **kwargs):
        super(PVMAnalyser, self).__init__(*args, **kwargs)
        self.storage_interface = storage.StorageIFace(**storage_args)
        
    def run(self):
        '''Run a standard processing loop, also close the storage interface once
        it is complete.'''
        super(PVMAnalyser, self).run()
        self.storage_interface.close()

    def cleanup(self):
        '''Clear the process data structures.'''
        posix.PIDMAP.clear()
        posix.DisconController.clear()

    def process(self, (hdr, pay)):
        '''Process a single front end message, applying it's effects to the
        database.'''
        tran = self.storage_interface.start_transaction()
        if hdr.payload_type == uds_msg.FUNCINFO_MSG:
            posix.handle_function(tran, hdr.pid, pay)
        elif hdr.payload_type == uds_msg.STARTUP_MSG:
            posix.handle_process(tran, hdr, pay)
        elif hdr.payload_type == uds_msg.GENERIC_MSG:
            if pay.msg_type == uds_msg.DISCON:
                posix.handle_disconnect(hdr.pid)
            elif pay.msg_type == uds_msg.PRE_FUNC_CALL:
                posix.handle_prefunc(hdr.pid, pay)
        tran.commit()
