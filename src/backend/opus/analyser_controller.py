# -*- coding: utf-8 -*-
'''
This module controls the fetcher and analyser. It also starts
a thread that monitors the memory usage in the analyser process.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import threading
import multiprocessing
import Queue
import logging
import types
import psutil
import time
import commands

from . import config_util, ipc
from .exception import SnapshotException


class AnalyserController(object):
    '''Controller class that starts a fetcher process and
    a memory monitor thread that periodically checks memory
    usage of the ananlyser process'''
    def __init__(self, pf_queue, router, config,
                 mem_mon_params, memory_params):
        self.config = config
        self.queue_triple = None
        self.node = None
        self.router = router
        self.drop = False
        self.pf_queue = pf_queue

        self.fetcher = None
        self.fetcher_stop_event = multiprocessing.Event()
        self.snapshot_event = multiprocessing.Event()

        self.analyser = None
        self.query = None

        self.mem_monitor = None
        self.mem_mon_stop_event = threading.Event()
        self.mem_mon_params = mem_mon_params
        self.memory_params = memory_params

        self.neo4j_params = config_util.safe_read_config(self.config,
                                                         "NEO4J_PARAMS")

    def _handle_command(self, msg):
        cmd = msg.cont
        if cmd['cmd'] == 'status':
            ret = {}
            try:
                ret['num_msgs'] = self.analyser.event_orderer.get_queue_size()
            except AttributeError:
                pass
            try:
                ret['inbound_rate'] = self.analyser.inbound.rate
                ret['outbound_rate'] = self.analyser.outbound.rate
            except AttributeError:
                pass
            return ret
        elif cmd['cmd'] == "exec_qry_method":
            return self.query(cmd)

    def start_service(self):
        '''Starts the fetcher process and memory monitor thread'''
        self._start_fetcher()
        self._start_mem_monitor()

    def _start_fetcher(self):
        '''Initialises fetcher process specific members and
        starts the fetcher'''
        self.queue_triple = self.router.add("ANALYSER",
                                            queue_class=multiprocessing.Queue,
                                            queue_triple=True)
        self.fetcher_stop_event.clear()
        self.snapshot_event.clear()
        self.fetcher = multiprocessing.Process(name='fetcher',
                                               target=self._run_fetcher)
        self.fetcher.start()
        if __debug__:
            logging.debug("Started fetcher process with pid: %d",
                          self.fetcher.pid)

    def _start_mem_monitor(self):
        '''Initialises and starts the memory monitor thread'''
        if not self.mem_mon_params['mon_status']:
            logging.info("Memory monitor thread is not set to ON status. "
                         "Cannot start thread")
            return
        self.mem_mon_stop_event.clear()
        self.mem_monitor = threading.Thread(name='mem_monitor',
                                            target=self._run_mem_monitor)
        self.mem_monitor.start()
        if __debug__:
            logging.debug("Started the memory monitor thread")

    def _run_fetcher(self):
        '''Runs the fetcher process loop'''
        import jpype
        from . import analysis
        from . import query

        self.node = ipc.Worker(ident="ANALYSER",
                               queue_triple=self.queue_triple,
                               handler=self._handle_command,
                               queue_class=multiprocessing.Queue)
        self.node.run_forever()

        neo4j_cfg = {}
        neo4j_cfg['neo4j_cfg'] = self.neo4j_params
        self.analyser = config_util.load_module(self.config, "Analyser",
                                                analysis.Analyser,
                                                neo4j_cfg)

        def _query(self, msg):
            if not jpype.isThreadAttachedToJVM():
                jpype.attachThreadToJVM()

            return query.ClientQueryControl.exec_method(
                self.analyser.db_iface, msg)

        self.query = types.MethodType(_query, self)

        if __debug__:
            logging.debug("Starting analyser....")

        self.analyser.start()
        self.pf_queue.register_event(self.snapshot_event, SnapshotException())

        while True:
            try:
                if self.snapshot_event.is_set():
                    if __debug__:
                        logging.debug("Snapshot event set, "
                                      "fetcher exiting loop")
                    break
                msg = self.pf_queue.dequeue()
                self.analyser.put_msg(msg)
            except Queue.Empty:
                if (self.fetcher_stop_event.is_set() and
                    self.pf_queue.get_queue_size() == 0):
                    break
            except SnapshotException:
                logging.error("Snapshot event set!!")
                self.analyser.snapshot_shutdown()
                break

        if __debug__:
            logging.debug("Shutting down analyser....")

        if self.analyser.do_shutdown(self.drop):
            if __debug__:
                logging.debug("Analyser has successfully shutdown")
        else:
            if __debug__:
                logging.debug("Failed to shutdown analyser")

    def _check_mem_condition(self, fetch_proc):
        '''Checks JVM heap memory size and available memory on the system'''
        proc_mem_info = fetch_proc.get_memory_info()
        if __debug__:
            logging.debug("RSS: %d", proc_mem_info.rss)

        # If the JVM's current heap size is greater than 90%
        # of the maximum value of heap size, restart analyser
        (status, output) = commands.getstatusoutput(
                           'jstat -gccapacity %d' % (fetch_proc.pid))
        if status != 0:
            logging.error("%d: %s", status, output)
        else:
            lines = output.split('\n')
            fields = lines[1].split()
            jstat_max_jvm = float(fields[1]) + float(fields[7])
            heap_size = float(fields[3]) + float(fields[4])
            heap_size += float(fields[5]) + float(fields[9])
            if __debug__:
                logging.debug("JVM current heap size: %f MB, "
                              "Max heap size: %f MB",
                              (heap_size / 1024),
                              (jstat_max_jvm / 1024))

            if (heap_size >=
                (self.memory_params['jvm_usage_threshold'] * jstat_max_jvm)):
                logging.error("Warning!! JVM heap size above threshold, "
                              "current_heap: %f MB, max_heap: %f MB",
                              (heap_size / 1024), (jstat_max_jvm / 1024))
                return True


        # If the resident set size has increased beyond the maximum
        # RSS threshold, restart the analyser
        if ('max_rss_threshold' in self.memory_params and
            self.memory_params['max_rss_threshold'] is not None):
            rss_in_mb = proc_mem_info.rss / (1024 * 1024)
            if rss_in_mb > self.memory_params['max_rss_threshold']:
                logging.info("Warning!! RSS: %f MB exceeded beyond "
                             "maximum threshold: %f MB",
                             rss_in_mb, self.memory_params['max_rss_threshold'])
                return True

        # If system available memory is less than 25% of total memory
        # and the analyser's RSS is more than 35% of the total memory,
        # then restart the analyser
        sys_mem_info = psutil.virtual_memory()
        avail_mem = sys_mem_info.available
        total_mem = sys_mem_info.total
        if ((avail_mem < (self.memory_params['min_percent_avail_mem']
                          * total_mem)) and
            (proc_mem_info.rss > (self.memory_params['max_rss_percent_mem']
                                  * total_mem))):
            logging.error("System is running low on memory!!")
            logging.error("Total mem: %d, Available mem: %d, Analyser mem: %d",
                          total_mem, avail_mem, proc_mem_info.rss)
            return True
        return False

    def _run_mem_monitor(self):
        '''Monitor the memory usage of the fetcher process'''
        fetch_proc = psutil.Process(self.fetcher.pid)
        time.sleep(1)

        while not self.mem_mon_stop_event.is_set():
            if not fetch_proc.is_running():
                logging.error("Error: Fetcher with pid: %d is not running",
                              self.fetcher.pid)
                break

            if self._check_mem_condition(fetch_proc):
                if self.snapshot_shutdown():
                    self._start_fetcher()
                    fetch_proc = psutil.Process(self.fetcher.pid)
                else:
                    logging.error(
                    "Failed to shutdown fetcher/analyser, restart manually")
                    break
            time.sleep(self.mem_mon_params['mon_interval'])

    def snapshot_shutdown(self):
        '''Tells the analyser take a snapshot of its state and shutdown'''
        self.snapshot_event.set()
        self.pf_queue.wakeup()
        try:
            self.fetcher.join()
        except RuntimeError as exc:
            logging.error("Failed to snapshot and shutdown fetcher.")
            logging.error(exc)
            return False
        return True

    def _stop_mem_monitor(self):
        '''Stops the memory monitor thread'''
        if not self.mem_mon_params['mon_status']:
            return True

        self.mem_mon_stop_event.set()
        try:
            if __debug__:
                logging.debug("Waiting for the memory monitor to join")
            self.mem_monitor.join(self.mem_mon_params['mon_interval'] * 2)
        except RuntimeError as exc:
            logging.error("Failed to shutdown memory monitor thread.")
            logging.error(exc)
            return False
        return True


    def do_shutdown(self, drop):
        '''Initiates shutdown of analyser controller'''
        self.drop = drop
        self.fetcher_stop_event.set()
        try:
            self.fetcher.join()
        except RuntimeError as exc:
            logging.error("Failed to shutdown fetcher process sucessfully.")
            logging.error(exc)
            return False
        return self._stop_mem_monitor()
