# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import argparse
import sys

from . import config

from .cmds import conf, process, server, util


def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conf", required=False, default=config.CONFIG_PATH,
                        help="Path to OPUS master config file.")

    parser.add_argument("-v", action="store_true",
                        help="Print verbose errors.")

    group_parser = parser.add_subparsers(dest="group")
    for cmd in [conf, process, server, util]:
        name = cmd.__name__.split(".")[-1]
        doc = cmd.__doc__.strip()
        cmd_parse = group_parser.add_parser(name, help=doc)
        cmd.setup_parser(cmd_parse)

    return parser


def run():
    try:
        parser = make_parser()
        args = parser.parse_args()

        params = {k: v
                  for k, v in args._get_kwargs()  # pylint: disable=W0212
                  if k not in ['group', 'v']}

        if args.group == "process":
            process.handle(**params)
        elif args.group == "server":
            server.handle(**params)
        elif args.group == "conf":
            conf.handle(**params)
        elif args.group == "util":
            util.handle(**params)
    except config.FailedConfigError:
        print("Failed to execute command due to insufficient configuration. "
              "Please run the '{} conf' command "
              "to reconfigure the program.".format(sys.argv[0]))
    except KeyboardInterrupt:
        pass
