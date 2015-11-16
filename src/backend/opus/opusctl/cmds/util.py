# -*- coding: utf-8 -*-
'''
Utility functions for OPUS.
'''
from __future__ import absolute_import, division, print_function

import sys

from .. import utils


def handle_ps_line(cfg, mode):
    term_status = utils.is_opus_ipose_lib_set()
    server_status = utils.is_server_active(cfg=cfg)
    if mode == "unicode":
        if term_status:
            if server_status:
                print(u"☑".encode("utf-8"), end="")
            else:
                print(u"☒".encode("utf-8"), end="")
    elif mode == "return":
        return_code = 0
        if server_status:
            return_code |= 0b1
        if term_status:
            return_code |= 0b10
        sys.exit(return_code)


def handle(cmd, **params):
    if cmd == "ps-line":
        handle_ps_line(**params)


def setup_parser(parser):
    cmds = parser.add_subparsers(dest="cmd")
    ps_line_parser = cmds.add_parser(
        "ps-line",
        help="Provides a $PS line component for indicating the status "
             "of OPUS.")

    ps_mode = ps_line_parser.add_mutually_exclusive_group(required=True)
    ps_mode.add_argument("--unicode", dest="mode",
                         action="store_const", const="unicode",
                         help=u"Express OPUS status using unicode symbols. "
                         u"Prints nothing if the terminal interposition is "
                         u"off. Prints ☒ if the terminal is interposed but "
                         u"the server is off. Prints ☑ if both the terminal "
                         u"is interposed and the server is "
                         u"on.".encode("utf-8"))
    ps_mode.add_argument("--return", dest="mode",
                         action="store_const", const="return",
                         help="Express OPUS status as the return code of "
                         "this command. The return code of this command "
                         "encodes the status of the OPUS server and the "
                         "terminal interposition. The lowest bit gives "
                         "the server status and the next bit gives the "
                         "terminal status.")
