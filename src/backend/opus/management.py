# -*- coding: utf-8 -*-
'''
Management systems for initialising system structure then handing off to the
control systems.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (analysis, common_utils, production, messaging)
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
    header.timestamp = (2**64)-1
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


class DaemonManager(object):
    '''The daemon manager is created to launch the back-end.'''
    def __init__(self, config):
        self.config = config

        analyser_type = _safe_read_config(self.config, "MODULES", "Analyser")
        analyser_args = _safe_read_config(self.config, 'ANALYSERS', 
                                          analyser_type)

        try:
            self.analyser = common_utils.meta_factory(analysis.Analyser,
                                                      analyser_type,
                                                      **analyser_args)
        except common_utils.InvalidTagException:
            logging.error("Invalid analyser type %s in config file.",
                          analyser_type)
            raise InvalidConfigFileException()
        except TypeError:
            logging.error("Config section %s is incorrectly setup.",
                          analyser_type)
            raise InvalidConfigFileException()

        producer_type = _safe_read_config(self.config, "MODULES", "Producer")
        producer_args = _safe_read_config(self.config, 'PRODUCERS',
                                          producer_type)
        producer_args['analyser_obj'] = self.analyser

        try:
            self.producer = common_utils.meta_factory(production.Producer,
                                                      producer_type,
                                                      **producer_args)
        except common_utils.InvalidTagException:
            logging.error("Invalid producer type %s in config file.",
                          producer_type)
            raise InvalidConfigFileException()
        except TypeError:
            logging.error("Config section %s is incorrectly setup.",
                          producer_type)
            raise InvalidConfigFileException()

        self.analyser.start()
        startup_msg_pair = _startup_touch_file(_safe_read_config(self.config,
                                                                 "GENERAL",
                                                                 "touch_file"))
        self.analyser.put_msg([startup_msg_pair])

        self.producer.start()

    def dbus_set_analyser(self, new_analyser_type):
        '''Handle a dbus message signalling for an analyser change.'''
        try:
            new_analyser_args = _safe_read_config(self.config, 'ANALYSERS', 
                                                  new_analyser_type)
        except InvalidConfigFileException:
            logging.error("Please choose an analyser type that has a config"
                          " specified in the systems configuration file.")
            return None

        try:
            new_analyser = common_utils.meta_factory(analysis.Analyser,
                                                     new_analyser_type,
                                                     **new_analyser_args)
        except common_utils.InvalidTagException:
            logging.error("That is an invalid analyser name.")
            return None
        except TypeError:
            logging.error("Config section %s is incorrectly setup.",
                          new_analyser_type)
            return None

        new_analyser.start()

        old_analyser = self.producer.switch_analyser(new_analyser)
        old_analyser.do_shutdown()
        self.analyser = new_analyser

    def dbus_get_analyser(self):
        '''Return the current analyser thread.'''
        return self.analyser.__class__.__name__

    def dbus_stop_service(self):
        '''Cause the daemon to shutdown gracefully.'''
        self.producer.do_shutdown()
        self.analyser.do_shutdown()

        _shutdown_touch_file(_safe_read_config(self.config,
                                               "GENERAL",
                                               "touch_file"))