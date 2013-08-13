#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''Main script to run the OPUS backend. Initialises the DaemonManager from
the appropriate config file and starts the applications main loop.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (analysis, common_utils, custom_time, production)

import argparse
import logging
import logging.config
import sys

try:
    import yaml
except ImportError:
    print("YAML module is not present!")
    print("Please install the PyYAML module.")
    sys.exit(1)


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


def pre_init_logging():
    '''Setup the logging framework.'''
    logging.basicConfig()


def init_logging(logging_cfg):
    '''Setup the logging framework.'''
    logging.config.dictConfig(logging_cfg)


def parse_args():
    parser = argparse.ArgumentParser(
                       description='OPUS backend storage and processing system.'
                                     )
    parser.add_argument('config', default="config.yaml", nargs='?',
                                  help='Location to load system config from.')
    args = parser.parse_args()
    return args.config


def command_help():
    print("======Commands======\n"
                  "Analyser Set    -> set\n"
                  "Analyser Type   -> type\n"
                  "Quit            -> quit\n"
                  "Help            -> ?\n")


def main():
    '''Main loop method, creates the mock daemon manager then loops for user
    input calling methods of the daemon manager as appropriate. Finally calls
    the daemon managers shutdown method.'''

    pre_init_logging()

    conf_file_loc = parse_args()

    try:
        with open(conf_file_loc, "rt") as conf:
            config = yaml.safe_load(conf)

        init_logging(config['LOGGING'])

        daemon_manager = MockDaemonManager(config)
    except InvalidConfigFileException:
        return
    except IOError:
        logging.error("Failed to read in config file.")
        return

    command_help()
    while True:
        command = raw_input("Enter Command:")
        if command == "quit":
            break
        elif command == "?":
            command_help()
        elif command == "type":
            print(daemon_manager.dbus_get_analyser())
        elif command == "set":
            new_analyser = raw_input("Enter desired analyser:")
            daemon_manager.dbus_set_analyser(new_analyser)

    daemon_manager.dbus_stop_service()


if __name__ == "__main__":
    custom_time.patch_custom_monotonic_time()
    main()
