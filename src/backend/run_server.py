#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''Main script to run the OPUS backend. Initialises the DaemonManager from
the appropriate config file and starts the applications main loop.
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (custom_time, management)

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

        daemon_manager = management.DaemonManager(config)
    except management.InvalidConfigFileException:
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
