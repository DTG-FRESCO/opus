# -*- coding: utf-8 -*-
'''
Configuration of the OPUS environment.
'''
from __future__ import absolute_import, division, print_function

from .. import config


def handle(conf, install):
    try:
        _, cfg = config.read_config(conf)
    except config.FailedConfigError:
        cfg = {}

    if conf is not None:
        cfg['master_config'] = conf

    new_cfg = config.generate_config(cfg)

    config.update_config_subsidiaries(new_cfg)

    config.write_config(new_cfg['master_config'], new_cfg)

    if install:
        with open("/tmp/install-opus", "w") as o_file:
            o_file.write("source " + new_cfg['bash_var_path'])


def setup_parser(parser):
    parser.add_argument(
        "--install", "-i", action='store_true',
        help="Triggers additional output during the install procedure.")
