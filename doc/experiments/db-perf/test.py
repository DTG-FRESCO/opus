#! /usr/local/bin/python2.7
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import argparse
import random
import traceback

import timer

import test_dump
#import test_sql
#import test_neo4j
#import test_sqldump


CANDIDATES = [#test_neo4j,
              #test_sql,
              #test_dump,
              #test_sqldump]
              test_dump.DumpModule(2**i) for i in range(21)]

# Defaults
ITERATIONS = 1000
UNIQUE_FILES = 500
UNIQUE_FDS = 100


class MsgFields(object):
    MSG_TYPE = 1

    # Optional fields
    FUNC_NAME = 2
    FILE_NAME = 3
    FILE_DESC = 4
    PID = 5
    FILE_MODE = 6


def create_msg_list(iters, unique_files, unique_fds):
    msg_list = []

    msg1 = {}
    msg1[MsgFields.MSG_TYPE] = "PROCESS_START"
    msg1[MsgFields.FILE_NAME] = "/usr/bin/gcc"
    msg1[MsgFields.PID] = "1234"
    msg_list.append(msg1)

    for i in range(iters):
        msg2 = {}
        msg2[MsgFields.MSG_TYPE] = "FUNC_MSG"
        msg2[MsgFields.FUNC_NAME] = "open"
        msg2[MsgFields.FILE_NAME] = ("/home/nb466/a" +
                                     str(i % unique_files) +
                                     ".txt")
        msg2[MsgFields.FILE_DESC] = str(i % unique_fds)
        msg2[MsgFields.FILE_MODE] = "r"
        msg2[MsgFields.PID] = "1234"
        msg_list.append(msg2)

        msg3 = {}
        msg3[MsgFields.MSG_TYPE] = "FUNC_MSG"
        msg3[MsgFields.FUNC_NAME] = "close"
        msg3[MsgFields.FILE_DESC] = str(i % unique_fds)
        msg3[MsgFields.PID] = "1234"
        msg_list.append(msg3)

    return msg_list


def main(config):
    msg_list = create_msg_list(config.iters,
                               config.files,
                               config.fds)

    for m in CANDIDATES:
        m.setup()

    success = True
    try:
        for m in random.sample(CANDIDATES, len(CANDIDATES)):
            for msg in msg_list:
                m.process_msg(msg)
    except Exception:
        traceback.print_exc()
        success = False

    for m in CANDIDATES:
        m.teardown()

    if success:
        timer.display()
        timer.gnuplot()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run message processing benchmarks.")
    parser.add_argument('--iters', type=int, default=ITERATIONS,
                        help="Set the number of messages to generate.")
    parser.add_argument('--files', type=int, default=UNIQUE_FILES,
                        help="Set the number of unique files.")
    parser.add_argument('--fds', type=int, default=UNIQUE_FDS,
                        help="Set the number of unique file descriptors.")
    main(parser.parse_args())
