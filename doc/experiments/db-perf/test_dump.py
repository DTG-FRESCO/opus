#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import json
import os

import timer

fh = None

track = timer.track("dump")


@track
def dump(msg):
    json.dump(msg, fh)


@track
def sync():
    os.fdatasync(fh.fileno())


@track
def process_msg(msg):
    # TODO: Test out a workflow extraction query
    dump(msg)
    sync()


def setup():
    global fh
    fh = open("prov.log", "w")


def teardown():
    fh.close()
    os.unlink("prov.log")
