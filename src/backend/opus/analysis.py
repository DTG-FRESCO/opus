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


from . import common_utils, exception, storage, order, messaging
from . import uds_msg_pb2 as uds_msg
from .pvm import posix


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
            self.file_object = open(self.logfile_path, "a+b")
        except IOError as exc:
            logging.error("Error: %d, Message: %s", exc.errno, exc.strerror)
            raise exception.OPUSException("log file open error")
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
    def __init__(self, opus_snapshot_dir, *args, **kwargs):
        super(OrderingAnalyser, self).__init__(*args, **kwargs)
        # TODO(tb403) - Proper max_wind
        self.event_orderer = order.EventOrderer(50)
        self.queue_cleared = threading.Event()
        self.msg_handler = self.process
        self.snapshot_state = False
        self.msg_fh = None
        self.opus_snapshot_dir = opus_snapshot_dir
        self.msg_queue_data_file = None
        self.load_orderer()

    def get_snapshot_dir(self):
        return self.opus_snapshot_dir

    def load_orderer(self):
        self.msg_queue_data_file = self.get_snapshot_dir()
        self.msg_queue_data_file += "/.opus_msg_queue.dat"
        if not os.path.isfile(self.msg_queue_data_file):
            return

        hdr_len = messaging.Header.length
        try:
            with open(self.msg_queue_data_file, "rb") as fp:
                while True:
                    hdr = fp.read(hdr_len)
                    if hdr == b'':
                        break
                    hdr_obj = messaging.Header()
                    hdr_obj.loads(hdr)

                    pay_len = hdr_obj.payload_len
                    if pay_len == 0:
                        continue
                    pay = fp.read(pay_len)
                    msg = [(hdr_obj.timestamp, (hdr, pay))]
                    self.event_orderer.push(msg)
        except IOError as exc:
            logging.error("Error: %d, Message: %s", exc.errno, exc.strerror)
            raise exception.OPUSException(
                  "Could not open OPUS message queue file for reading")

        if __debug__:
            logging.debug("Size of event_orderer: %d", self.event_orderer.get_queue_size())
            logging.debug("Removing file: %s", self.msg_queue_data_file)
        os.unlink(self.msg_queue_data_file)


    def run(self):
        '''Pull events from the queue and process them as long as the
        stop_event is not set.'''
        while not self.stop_event.is_set():
            try:
                _, msg = self.event_orderer.pop()
                self.msg_handler(msg)
            except Queue.Empty:
                if __debug__:
                    logging.debug("T:Queue cleared, clearing state tables.")
                self.queue_cleared.set()

                if self.snapshot_state:
                    os.fsync(self.msg_fh.fileno())
                    self.msg_fh.close()
                    self.dump_internal_state()

                self.cleanup()
                if __debug__:
                    logging.debug("T:Preparing to wait for clear completion.")
                while self.queue_cleared.is_set():
                    time.sleep(0)
                if __debug__:
                    logging.debug("T:Clear completed.")
                continue

    def do_shutdown(self, drop=False):
        '''Clear the event orderer and then shutdown the processing thread.'''
        if not self.isAlive():
            return True

        if not drop:
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

    def snapshot_shutdown(self):
        try:
            self.msg_fh = open(self.msg_queue_data_file, "wb")
        except IOError as exc:
            logging.error("Error: %d, Message: %s", exc.errno, exc.strerror)
            raise exception.OPUSException(
                  "Could not open OPUS message queue file for writing")

        self.snapshot_state = True
        self.msg_handler = self.put_msg_file
        self.do_shutdown()

    def put_msg_file(self, (hdr, pay)):
        self.msg_fh.write(hdr)
        self.msg_fh.write(pay)
        self.msg_fh.flush()

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

    def dump_internal_state(self):
        raise NotImplementedError()


class PVMAnalyser(OrderingAnalyser):
    '''The PVM analyser class implements the core of the PVM model, including
    the significant operations and their interactions with the underlying
    storage system.'''
    def __init__(self, storage_type, storage_args, opus_lite,
                 neo4j_cfg, *args, **kwargs):
        super(PVMAnalyser, self).__init__(*args, **kwargs)
        self.storage_type = storage_type
        self.storage_args = storage_args
        self.storage_args['neo4j_cfg'] = neo4j_cfg
        self.opus_lite = opus_lite
        self.proc_state_file = None

    def run(self):
        '''Run a standard processing loop, also close the storage interface
        once it is complete.'''
        self.db_iface = common_utils.meta_factory(storage.StorageIFace,
                                                  self.storage_type,
                                                  **self.storage_args)
        self.proc_state_file = self.get_snapshot_dir() + "/.opus_proc_state.dat"
        posix.handle_proc_load_state(self.proc_state_file)
        super(PVMAnalyser, self).run()
        self.db_iface.close()

    def cleanup(self):
        '''Clear the process data structures.'''
        posix.handle_cleanup()

    def dump_internal_state(self):
        if __debug__:
            logging.error("Dumping process state to file")
        posix.handle_proc_dump_state(self.proc_state_file)

    def process(self, (hdr, pay)):
        '''Process a single front end message, applying it's effects to the
        database.'''
        hdr_obj = messaging.Header()
        hdr_obj.loads(hdr)
        pay_obj = common_utils.get_payload_type(hdr_obj)
        pay_obj.ParseFromString(pay)

        # Set system time for current message
        self.db_iface.set_sys_time_for_msg(hdr_obj.sys_time)

        with self.db_iface.start_transaction():
            if hdr_obj.payload_type == uds_msg.FUNCINFO_MSG:
                posix.handle_function(self.db_iface,
                                      hdr_obj.pid,
                                      pay_obj)
            elif hdr_obj.payload_type == uds_msg.AGGREGATION_MSG:
                posix.handle_bulk_functions(self.db_iface,
                                            hdr_obj.pid,
                                            pay_obj)
            elif hdr_obj.payload_type == uds_msg.STARTUP_MSG:
                posix.handle_process(self.db_iface,
                                     hdr_obj,
                                     pay_obj,
                                     self.opus_lite)
            elif hdr_obj.payload_type == uds_msg.GENERIC_MSG:
                if pay_obj.msg_type == uds_msg.DISCON:
                    posix.handle_disconnect(self.db_iface,
                                            hdr_obj,
                                            hdr_obj.pid)
                elif pay_obj.msg_type == uds_msg.PRE_FUNC_CALL:
                    posix.handle_prefunc(hdr_obj.pid,
                                         pay_obj)
            elif hdr_obj.payload_type == uds_msg.TERM_MSG:
                posix.handle_startup(self.db_iface,
                                     pay_obj)
            elif hdr_obj.payload_type == uds_msg.LIBINFO_MSG:
                posix.handle_libinfo(self.db_iface,
                                     hdr_obj.pid,
                                     pay_obj)


class StatisticsAnalyser(PVMAnalyser):

    class Counter(object):
        def __init__(self):
            super(StatisticsAnalyser.Counter, self).__init__()
            self.last_count = 0
            self.last_time = time.time()
            self.count = 0
            self.rate = 0

        def add(self, n):
            self.count += n

        def update(self):
            tmp_count = self.count
            tmp_time = time.time()
            cdiff = tmp_count - self.last_count
            tdiff = tmp_time - self.last_time
            self.rate = cdiff/tdiff
            self.last_count = tmp_count
            self.last_time = tmp_time

    def __init__(self, *args, **kwargs):
        super(StatisticsAnalyser, self).__init__(*args, **kwargs)
        self.inbound = self.Counter()
        self.outbound = self.Counter()

        self.checker_thread = threading.Thread(
            target=StatisticsAnalyser._update_rate, args=(self,))
        self.checker_thread.daemon = True

    def _update_rate(self):
        while True:
            self.inbound.update()
            self.outbound.update()
            time.sleep(1)

    def run(self):
        self.checker_thread.start()
        return super(StatisticsAnalyser, self).run()

    def put_msg(self, msg_list):
        self.inbound.add(len(msg_list))
        return super(StatisticsAnalyser, self).put_msg(msg_list)

    def process(self, (hdr, pay)):
        self.outbound.add(1)
        return super(StatisticsAnalyser, self).process((hdr, pay))
