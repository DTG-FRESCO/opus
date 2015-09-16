# -*- coding: utf-8 -*-
'''
Management systems for initialising system structure then handing off to the
control systems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from . import (cc_utils, command, command_interface,
               production, messaging, config_util)
from . import uds_msg_pb2 as uds_msg
from .analyser_controller import AnalyserController
from .pf_queue import ProducerFetcherQueue

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
        with open(touch_file, "w") as _:
            pass

    header.payload_len = term_msg.ByteSize()

    return header.dumps(), term_msg.SerializeToString()


def _shutdown_touch_file(touch_file):
    '''Removes the touch file, thus indicating a successful shutdown.'''
    os.remove(touch_file)


class DaemonManager(object):
    '''The daemon manager is created to launch the back-end.'''
    def __init__(self, config):
        self.config = config

        self.pf_queue = ProducerFetcherQueue()
        self.analyser_ctl = AnalyserController(self.pf_queue, self.config)

        (prod_comm, ctrl_prod) = cc_utils.RWPipePair.create_pair()

        self.producer = config_util.load_module(config, "Producer",
                                                production.Producer,
                                                {"pf_queue": self.pf_queue,
                                                 "comm_pipe": prod_comm})

        self.command = command.CommandControl(self, ctrl_prod)

        self.command.set_interface(config_util.load_module(
                        config, "CommandInterface",
                        command_interface.CommandInterface,
                        {"command_control": self.command})
        )

        self.analyser_ctl.start()

        startup_msg_pair = _startup_touch_file(config_util.safe_read_config(
                                                                self.config,
                                                                "GENERAL",
                                                                "touch_file"))
        self.pf_queue.enqueue([startup_msg_pair])
        self.producer.start()

    def loop(self):
        '''Execute the internal command and controls main loop.'''
        self.command.run()

    def set_analyser(self, new_analyser_type):
        '''Change the current analyser for a new analyser.'''
        # NOTE: Deprecate this function
        try:
            new_analyser = _load_module(self.config, "Analyser",
                                        analysis.Analyser,
                                        mod_type=new_analyser_type)
        except InvalidConfigFileException:
            return ("Please choose an analyser type that has a config"
                    " specified in the systems configuration file.")

        new_analyser.start()

        old_analyser = self.producer.switch_analyser(new_analyser)
        old_analyser.do_shutdown()
        self.analyser = new_analyser
        return "Sucess"

    def get_analyser(self):
        '''Return the current analyser thread.'''
        # NOTE: Must use the new communication mechanism
        return self.analyser_ctl.analyser.__class__.__name__

    def stop_service(self, drop):
        '''Cause the daemon to shutdown gracefully.'''
        if self.producer.do_shutdown():
            self.pf_queue.start_clear()
            self.analyser_ctl.do_shutdown(drop)
            self.analyser_ctl.join()
            _shutdown_touch_file(config_util.safe_read_config(
                                                   self.config,
                                                   "GENERAL",
                                                   "touch_file"))
            return True
        return False
