'''
Contains clock_gettime implementation
for python versions before 3.3
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import time
import sys
import ctypes
import errno
import logging

class ClockConstant(object):
    '''Clock type values from from <linux/time.h>'''
    CLOCK_MONOTONIC = 1
    CLOCK_MONOTONIC_RAW = 4


class Timespec(ctypes.Structure):
    '''Describes the fields in timespec structure'''
    _fields_ = [ ('tv_sec', ctypes.c_long), ('tv_nsec', ctypes.c_long) ]


def monotonic_time(clock_type):
    '''Takes a clock type and returns the appropriate time in secs.nanosecs'''
    if not hasattr(monotonic_time, "clock_gettime"):
        librt = ctypes.CDLL('librt.so.1', use_errno=True)
        monotonic_time.clock_gettime = librt.clock_gettime
        monotonic_time.clock_gettime.argtypes = \
                [ctypes.c_int, ctypes.POINTER(Timespec)]

    _time = Timespec()
    if monotonic_time.clock_gettime(clock_type, 
                            ctypes.pointer(_time)) != 0:
        _errno = ctypes.get_errno()
        raise OSError(_errno, os.strerror(_errno))
    return _time.tv_sec + _time.tv_nsec * 1e-9


def patch_custom_monotonic_time():
    '''Patches the custom monotonic time
    function for python versions older than 3.3'''
    if sys.version_info >= (3, 3):
        return

    mono_invalid = 0
    mono_raw_invalid = 0

    try:
        monotonic_time(ClockConstant.CLOCK_MONOTONIC)
        time.CLOCK_MONOTONIC = ClockConstant.CLOCK_MONOTONIC
    except OSError as (_errno, err_msg):
        if _errno == errno.EINVAL:
            mono_invalid = 1
            logging.error("%s, %d", err_msg, ClockConstant.CLOCK_MONOTONIC)

    try:
        monotonic_time(ClockConstant.CLOCK_MONOTONIC_RAW)
        time.CLOCK_MONOTONIC_RAW = ClockConstant.CLOCK_MONOTONIC_RAW
    except OSError as (_errno, err_msg):
        if _errno == errno.EINVAL:
            mono_raw_invalid = 1
            logging.error("%s, %d", err_msg, ClockConstant.CLOCK_MONOTONIC_RAW)
            if not mono_invalid:
                time.CLOCK_MONOTONIC_RAW = ClockConstant.CLOCK_MONOTONIC

    if mono_invalid and mono_raw_invalid:
        logging.error("Cannot patch custom monotonic time")
        return

    time.clock_gettime = monotonic_time
