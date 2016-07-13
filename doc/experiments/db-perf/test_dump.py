#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import json
import os

import timer


class DumpModule():
    def __init__(self, sync_freq):
        self.sync_freq = sync_freq
        self.sync_count = 0
        track = timer.track("dump-{}".format(sync_freq))
        self.dump = track(self.dump)
        self.sync = track(self.sync)
        self.process_msg = track(self.process_msg)

    def setup(self):
        self.fh = open("/tmp/prov-{}.log".format(self.sync_freq), "w")

    def teardown(self):
        self.fh.close()
        os.unlink("/tmp/prov-{}.log".format(self.sync_freq))

    def dump(self, msg):
        json.dump(msg, self.fh)

    def sync(self):
        self.sync_count += 1
        if self.sync_count >= self.sync_freq:
            os.fdatasync(self.fh.fileno())
            self.sync_count = 0

    def process_msg(self, msg):
        self.dump(msg)
        self.sync()
