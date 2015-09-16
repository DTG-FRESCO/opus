# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import os
import time
import sys

from . import utils
from .ext_deps import termcolor
from .. import cc_utils, exception


def elapsed(reset=False):
    if reset:
        elapsed.start = time.time()
    else:
        return time.time() - elapsed.start


def monitor_server_startup(cfg):
    elapsed(reset=True)
    time.sleep(0.1)
    helper = cc_utils.CommandConnectionHelper("localhost",
                                              int(cfg['cc_port']))
    while elapsed() < 20:
        server_active = utils.is_server_active()
        try:
            helper.make_request({'cmd': 'status'})
            server_responsive = True
        except exception.BackendConnectionError:
            server_responsive = False

        yes = termcolor.colored("yes", "green")
        no = termcolor.colored("no", "red")

        print((" " * 50), end="\r")
        print("Server Active: %s Server Responsive: %s" %
              ((yes if server_active else no),
               (yes if server_responsive else no)),
              end="\r")
        sys.stdout.flush()
        if not(server_active or server_responsive):
            break

        if server_active and server_responsive:
            print("\nServer sucessfully started.")
            return True
        time.sleep(0.1)
    print("\nServer startup failed, check the %s and %s error logs for "
          "information." % (os.path.join(cfg['install_dir'], "opus_err.log"),
                            os.path.join(cfg['install_dir'], "opus.log")))
    return False


def start_opus_server(cfg):
    print("Attempting to start OPUS server.")
    if utils.is_opus_active() or utils.is_opus_ipose_lib_set():
        utils.reset_opus_env(cfg)
    if 'JAVA_HOME' not in os.environ:
        os.environ['JAVA_HOME'] = cfg['java_home']

    try:
        pid = os.fork()
        if pid > 0:
            return True
            # NOTE : To be fixed with the new communication mechanism
            # return monitor_server_startup(cfg)
    except OSError:
        sys.exit(1)

    os.chdir(utils.path_normalise(cfg['install_dir']))
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)

    err_log = utils.path_normalise(os.path.join(cfg['install_dir'],
                                                "opus_err.log"))
    sys.stdout.flush()
    sys.stderr.flush()
    sti = file("/dev/null", 'r')
    sto = open(err_log, 'w+')
    os.dup2(sti.fileno(), sys.stdin.fileno())
    os.dup2(sto.fileno(), sys.stdout.fileno())
    os.dup2(sto.fileno(), sys.stderr.fileno())
    sto.close()

    server_cfg_path = utils.path_normalise(os.path.join(cfg['install_dir'],
                                                        "opus-cfg.yaml"))

    try:
        os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'cpp'
        os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION_VERSION'] = '2'
        os.execvp(cfg['python_binary'],
                  [cfg['python_binary'],
                   "-O",
                   "-m",
                   "opus.run_server",
                   server_cfg_path])
    except OSError:
        sys.exit(1)
