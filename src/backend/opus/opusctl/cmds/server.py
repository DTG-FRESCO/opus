# -*- coding: utf-8 -*-
'''
Commands for controlling the provenance collection server.
'''
from __future__ import absolute_import, division, print_function

import sys
import time

from .. import config, server_start, utils
from ..ext_deps import prettytable, psutil
from ... import cc_utils, exception


def handle_start(cfg):
    '''Starts OPUS server.'''
    if not utils.is_server_active(cfg=cfg):
        server_start.start_opus_server(cfg)
    else:
        print("OPUS server already running.")


def _calc_rem_time(msgs):
    this = _calc_rem_time
    if not hasattr(this, "msgs"):
        this.msgs = msgs
        this.time = time.time()
        return ""
    else:
        msg_diff = this.msgs-msgs
        if msg_diff == 0:
            return ""
        time_diff = time.time()-this.time
        msg_per_s = msg_diff/time_diff
        rem_secs = int(msgs/msg_per_s)
        m, s = divmod(rem_secs, 60)
        h, m = divmod(m, 60)
        return "{:02d}:{:02d}:{:02d}".format(h, m, s)


def monitor_shutdown(helper, msg):
    print("Shutdown initiated.")
    print("Shutting down Producer...", end="")
    try:
        while True:
            ret = helper.make_request({"cmd": "status"})
            if ret['producer']['status'] == "Dead":
                break
    except exception.BackendConnectionError:
        pass
    print("Done.")
    print("Shutting down Analyser...")
    print("Flushing remaining messages...")
    total_msgs = msg['msg_count']
    if total_msgs > 0:
        try:
            while True:
                ret = helper.make_request({"cmd": "status"})
                if ret['analyser']['status'] == 'Dead':
                    break
                cur_msg = ret['analyser']['num_msgs']

                rem_time = _calc_rem_time(cur_msg)

                print(" "*50, end="\r")
                print("{:.2f}% [{}/{}] {}".format((1-(cur_msg/total_msgs))*100,
                                                  cur_msg,
                                                  total_msgs,
                                                  rem_time),
                      end="\r")
                sys.stdout.flush()

                time.sleep(2)
        except exception.BackendConnectionError:
            pass
        print(" "*50, end="\r")
    print("Message processing complete.")
    print("Shutdown complete.")


def _rewind(n):
    print("\033[{:d}F".format(n), end="")


def monitor_status(helper, follow):
    pay = helper.make_request({'cmd': 'status'})
    print_status_rsp(pay)
    n = (len(pay) - 1) + (len(pay['analyser']) - 1)
    while follow:
        _rewind(n)
        print("\n".join([" "*50]*n))
        _rewind(n)
        pay = helper.make_request({'cmd': 'status'})
        print_status_rsp(pay)
        n = (len(pay) - 1) + (len(pay['analyser']) - 1)
        sys.stdout.flush()
        time.sleep(1)


def print_status_rsp(pay):
    '''Prints status response to stdout'''
    print("{0:<20} {1:<12}".format("Producer", pay['producer']['status']))

    tmp_an = pay['analyser']
    print("{0:<20} {1:<12}".format("Analyser", tmp_an['status']))
    if 'num_msgs' in tmp_an:
        print("    {:d} msgs in queue".format(tmp_an['num_msgs']))
    if 'inbound_rate' in tmp_an:
        print("    {:.1f}/s msgs added".format(tmp_an['inbound_rate']))
    if 'outbound_rate' in tmp_an:
        print("    {:.1f}/s msgs processed".format(tmp_an['outbound_rate']))

    print("{0:<20} {1:<12}".format("Query Interface", pay['query']['status']))


@config.auto_read_config
def handle(cfg, cmd, **params):
    helper = cc_utils.CommandConnectionHelper(cfg['cc_addr'])
    if cmd == "start":
        handle_start(cfg=cfg, **params)
    elif cmd == "restart":
        if utils.is_server_active(helper=helper):
            print("===Shutting down OPUS server===")
            pay = helper.make_request({'cmd': 'stop'})
            monitor_shutdown(helper, pay)
        print("===Starting OPUS server===")
        server_start.start_opus_server(cfg)
    elif cmd == "status":
        if not utils.is_server_active(helper=helper):
            print("Server is not running.")
            return
        monitor_status(helper, **params)
    else:
        if not utils.is_server_active(helper=helper):
            print("Server is not running.")
            return
        msg = {"cmd": cmd}
        msg.update(params)
        pay = helper.make_request(msg)

        if not pay['success']:
            print(pay['msg'])
        elif cmd == "stop":
            monitor_shutdown(helper, pay)
        elif cmd == "ps":
            tab = prettytable.PrettyTable(['Pid',
                                           'Command Line',
                                           'Thread Count'])
            print("Interposed Processes:\n\n")
            for pid, count in pay['pid_map'].items():
                cmd_line = " ".join(
                    psutil.Process(
                        int(pid)
                        ).cmdline()
                    )
                tab.add_row([pid, cmd_line, count])
            print(tab)
        else:
            print(pay['msg'])


def setup_parser(parser):
    cmds = parser.add_subparsers(dest="cmd")
    cmds.add_parser(
        "start",
        help="Start the OPUS provenance collection server.")

    stop_parser = cmds.add_parser(
        "stop",
        help="Stop the OPUS provenance collection server.")
    stop_parser.add_argument(
        "--drop-queue", action="store_true",
        help="Force the server to drop all messages currently awaiting "
        "processing. This will cause you to potentially lose provenance "
        "data.")

    cmds.add_parser(
        "restart",
        help="Restart the OPUS provenance collection server.")
    cmds.add_parser(
        "ps",
        help="Display a list of processes currently being interposed.")

    status_parser = cmds.add_parser(
        "status",
        help="Display a status readout for the provenance collection server.")
    status_parser.add_argument(
        "--follow", "-f", action="store_true",
        help="Continue to refresh the counts until stopped.")

    detach_parser = cmds.add_parser(
        "detach",
        help="Deactivates OPUS interposition on a running process.")
    detach_parser.add_argument(
        "pid", type=int,
        help="The PID requiring interposition deactivation.")

    cmds.add_parser("getan")

    setan_parser = cmds.add_parser("setan")
    setan_parser.add_argument("new_an")
