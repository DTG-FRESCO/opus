# -*- coding: utf-8 -*-
'''
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (analysis, common_utils, production)

import logging
import logging.config


class InvalidConfigFileException(common_utils.OPUSException):
    '''Error in the formatting or content of the systems config file.'''
    def __init__(self):
        super(InvalidConfigFileException, self).__init__(
                                            "Error: Failed to load config file."
                                                         )


def safe_read_config(cfg, section, key):
    '''Read the value of key from section in cfg while appropriatly catching
    missing section and key exceptions and handling them by reraising invalid
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


class MockDaemonManager(object):
    '''The daemon manager is created to launch the back-end. It creates and
    starts the two working threads then listens for commands via DBUS.'''
    def __init__(self, config):
        self.config = config

        analyser_type = safe_read_config(self.config, "MODULES", "Analyser")
        analyser_args = safe_read_config(self.config, 'ANALYSERS', 
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

        producer_type = safe_read_config(self.config, "MODULES", "Producer")
        producer_args = safe_read_config(self.config, 'PRODUCERS',
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
        self.producer.start()

    def dbus_set_analyser(self, new_analyser_type):
        '''Handle a dbus message signalling for an analyser change.'''
        try:
            new_analyser_args = safe_read_config(self.config, 'ANALYSERS', 
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