# -*- coding: utf-8 -*-
'''
Management systems for initialising system structure then handing off to the
control systems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from . import (command, config_util, ipc, production, messaging)
from . import uds_msg_pb2 as uds_msg
from .analyser_controller import AnalyserController
from .pf_queue import ProducerFetcherQueue

import multiprocessing
import os
import os.path
import time

def _startup_touch_file(touch_file):
    '''Generate a term message based on the presence or non-presence of the
    touch file. Then create the touch file if necessary.'''
    term_msg = uds_msg.TermMessage()
    term_msg.downtime_start = 0
    term_msg.downtime_end = 0

    header = messaging.Header()
    header.pid = 0
    # Max int64 so ensure sorted after any messages in the queue
    header.timestamp = (2**64) - 1
    header.tid = 0
    header.payload_type = uds_msg.TERM_MSG
    header.sys_time = int(time.time())

    if os.path.exists(touch_file):
        term_msg.reason = uds_msg.TermMessage.CRASH
    else:
        term_msg.reason = uds_msg.TermMessage.SHUTDOWN
        open(touch_file, "w").close()

    header.payload_len = term_msg.ByteSize()

    return header.dumps(), term_msg.SerializeToString()


def _shutdown_touch_file(touch_file):
    '''Removes the touch file, thus indicating a successful shutdown.'''
    os.remove(touch_file)


class DaemonManager(object):
    '''The daemon manager is created to launch the back-end.'''
    def __init__(self, config):
        self.config = config

        self.router = ipc.Router(queue_class=multiprocessing.Queue)
        self.router.run_forever()

        self.pf_queue = ProducerFetcherQueue()

        analyser_ctlr_cfg = config_util.safe_read_config(self.config,
                                                         "ANALYSER_CONTROLLER")
        self.analyser_ctl = AnalyserController(self.pf_queue,
                                               self.router,
                                               self.config,
                                               **analyser_ctlr_cfg)

        self.producer = config_util.load_module(config, "Producer",
                                                production.Producer,
                                                {"pf_queue": self.pf_queue,
                                                 "router": self.router})

        command_cfg = config_util.safe_read_config(self.config, "COMMAND")

        self.command = command.CommandControl(self,
                                              router=self.router,
                                              **command_cfg)

        self.analyser_ctl.start_service()

        startup_msg_pair = _startup_touch_file(
            config_util.safe_read_config(self.config, "GENERAL", "touch_file")
            )
        self.pf_queue.enqueue([startup_msg_pair])
        self.producer.start()

    def loop(self):
        '''Execute the internal command and controls main loop.'''
        self.command.run()

    def stop_service(self, drop):
        '''Cause the daemon to shutdown gracefully.'''
        if self.producer.do_shutdown():
            self.pf_queue.start_clear()
            if self.analyser_ctl.do_shutdown(drop):
                _shutdown_touch_file(config_util.safe_read_config(self.config,
                                                                  "GENERAL",
                                                                  "touch_file"))
                return True
        return False
