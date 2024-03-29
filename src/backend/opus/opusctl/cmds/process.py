# -*- coding: utf-8 -*-
'''
Commands for launching processes with or without OPUS interposition.
'''
from __future__ import absolute_import, division, print_function

import argparse
import os
import psutil

from .. import config, server_start, utils


def get_current_shell():
    ppid = os.getppid()
    parent = psutil.Process(ppid);
    cur_shell = parent.exe()
    shell_args = parent.cmdline()[1:]
    return cur_shell, shell_args


@config.auto_read_config
def handle_launch(cfg, binary, arguments):
    if not utils.is_server_active(cfg=cfg):
        if not server_start.start_opus_server(cfg):
            print("Aborting command launch.")
            return

    opus_preload_lib = utils.path_normalise(os.path.join(cfg['install_dir'],
                                                         'lib',
                                                         'libopusinterpose.so')
                                            )
    if 'LD_PRELOAD' in os.environ:
        if opus_preload_lib not in os.environ['LD_PRELOAD']:
            os.environ['LD_PRELOAD'] = (os.environ['LD_PRELOAD'] + " " +
                                        opus_preload_lib)
    else:
        os.environ['LD_PRELOAD'] = opus_preload_lib

    if cfg['server_addr'][:4] == "unix":
        os.environ['OPUS_UDS_PATH'] = utils.path_normalise(cfg['server_addr'][7:])
        os.environ['OPUS_PROV_COMM_MODE'] = cfg['server_addr'][:4]
    else:
        os.environ['OPUS_PROV_COMM_MODE'] = cfg['server_addr'][:3]
        addr = cfg['server_addr'][6:].split(":")
        os.environ['OPUS_TCP_ADDRESS'] = addr[0]
        os.environ['OPUS_TCP_PORT'] = addr[1]
    os.environ['OPUS_MSG_AGGR'] = "1"
    os.environ['OPUS_MAX_AGGR_MSG_SIZE'] = "65536"
    os.environ['OPUS_LOG_LEVEL'] = "3"  # Log critical
    os.environ['OPUS_INTERPOSE_MODE'] = "1"  # OPUS lite

    if not binary:
        binary, arguments = get_current_shell()
    os.execvp(binary, [binary] + arguments)


@config.auto_read_config
def handle_exclude(cfg, binary, arguments):
    if utils.is_opus_active():
        utils.reset_opus_env(cfg)
    else:
        print("OPUS is not active.")

    if not binary:
        binary, arguments = get_current_shell()
    os.execvp(binary, [binary] + arguments)


def handle(cmd, **params):
    if cmd == "launch":
        handle_launch(**params)
    elif cmd == "exclude":
        handle_exclude(**params)


def setup_parser(parser):
    cmds = parser.add_subparsers(dest="cmd")

    launch = cmds.add_parser(
        "launch",
        help="Launch a process under OPUS.")
    launch.add_argument(
        "binary", nargs='?',
        help="The binary to be launched. Defaults to the current shell.")
    launch.add_argument(
        "arguments", nargs=argparse.REMAINDER,
        help="Any arguments to be passed.")

    exclude = cmds.add_parser(
        "exclude",
        help="Launch a process excluded from OPUS interposition.")
    exclude.add_argument(
        "binary", nargs='?',
        help="The binary to be launched. Defaults to the current shell.")
    exclude.add_argument(
        "arguments", nargs=argparse.REMAINDER,
        help="Any arguments to be passed.")
