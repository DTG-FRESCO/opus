# -*- coding: utf-8 -*-
'''
Management systems for initialising system structure then handing off to the
control systems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (analysis, command, common_utils, production, messaging)
from opus import uds_msg_pb2 as uds_msg

import logging
import os
import os.path


class InvalidConfigFileException(common_utils.OPUSException):
    '''Error in the formatting or content of the systems config file.'''
    def __init__(self):
        super(InvalidConfigFileException, self).__init__(
                                            "Error: Failed to load config file."
                                                         )


def _safe_read_config(cfg, section, key):
    '''Read the value of key from section in cfg while appropriately catching
    missing section and key exceptions and handling them by re-raising invalid
    config errors.'''
    try:
        sec = cfg[section]
    except KeyError:
        logging.error("Config file lacks %s section.", section)
        raise InvalidConfigFileException()
    try:
        return sec[key]
    except KeyError:
        logging.error("Config file lacks %s key in section %s.", key, section)
        raise InvalidConfigFileException()


def _startup_touch_file(touch_file):
    '''Generate a term message based on the presence or non-presence of the
    touch file. Then create the touch file if necessary.'''
    term_msg = uds_msg.TermMessage()
    term_msg.downtime_start = 0
    term_msg.downtime_end = 0

    header = messaging.Header()
    header.pid = 0
    #Max int64 so ensure sorted after any messages in the queue
    header.timestamp = (2**64) - 1
    header.tid = 0
    header.payload_type = uds_msg.TERM_MSG

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


def _load_module(config, mod_name, mod_base,
                 mod_extra_args=None, mod_type=None):
    if mod_type is None:
        mod_type = _safe_read_config(config, "MODULES", mod_name)

    mod_args = _safe_read_config(config, mod_name.upper(), mod_type)

    if mod_extra_args is not None:
        mod_args.update(mod_extra_args)

    try:
        mod = common_utils.meta_factory(mod_base,
                                        mod_type,
                                        **mod_args)
    except common_utils.InvalidTagException:
        logging.error("Invalid %s type %s in config file.",
                      mod_name, mod_type)
        raise InvalidConfigFileException()
    except TypeError:
        logging.error("Config section %s is incorrectly setup.",
                      mod_type)
        raise InvalidConfigFileException()
    return mod


class DaemonManager(object):
    '''The daemon manager is created to launch the back-end.'''
    def __init__(self, config):
        self.config = config

        self.analyser = _load_module(config, "Analyser", analysis.Analyser)

        (prod_comm, ctrl_prod) = common_utils.RWPipePair.create_pair()

        self.producer = _load_module(config, "Producer", production.Producer,
                                     {"analyser_obj": self.analyser,
                                      "comm_pipe": prod_comm})

        self.command = command.CommandControl(self, ctrl_prod)

        self.command.set_interface(
            _load_module(config, "CommandInterface", command.CommandInterface,
                         {"command_control": self.command})
        )

        self.analyser.start()
        startup_msg_pair = _startup_touch_file(_safe_read_config(self.config,
                                                                 "GENERAL",
                                                                 "touch_file"))
        self.analyser.put_msg([startup_msg_pair])

        self.producer.start()

    def loop(self):
        '''Execute the internal command and controls main loop.'''
        self.command.run()

    def set_analyser(self, new_analyser_type):
        '''Change the current analyser for a new analyser.'''
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
        return self.analyser.__class__.__name__

    def stop_service(self):
        '''Cause the daemon to shutdown gracefully.'''
        if self.producer.do_shutdown():
            if self.analyser.do_shutdown():
                _shutdown_touch_file(_safe_read_config(self.config,
                                                       "GENERAL",
                                                       "touch_file"))
                return True
        return False
