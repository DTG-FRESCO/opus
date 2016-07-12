# -*- coding: utf-8 -*-
'''
Config for Command and control messages.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from .opusctl import config


def default_server():
    _, cfg = config.read_config(config.CONFIG_PATH)
    return cfg['cc_addr']
