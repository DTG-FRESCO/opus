#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""

"""
from __future__ import (absolute_import, division,
                        print_function)


import argparse
import functools
import hashlib
import os
import os.path
import sys

import psutil
import yaml


class OPUSctlError(Exception):
    pass


class FailedConfigError(OPUSctlError):
    pass


def memoised(func):
    cache = func.cache = {}

    @functools.wraps(func)
    def inner(*args, **kwargs):
        key = str(args) + str(kwargs)
        if key not in cache:
            cache[key] = func(*args, **kwargs)
        return cache[key]
    return inner


def cmd_handler(cmd):
    if not hasattr(cmd_handler, "handlers"):
        handlers = cmd_handler.handlers = {}
    else:
        handlers = cmd_handler.handlers

    def inner(func):
        handlers[cmd] = func
        return func
    return inner


@memoised
def path_normalise(path):
    return os.path.abspath(os.path.expanduser(path))


DEFAULT_CONFIG_PATH = "~/.opus-cfg"

if 'OPUS_MASTER_CONFIG' in os.environ:
    CONFIG_PATH = path_normalise(os.environ['OPUS_MASTER_CONFIG'])
else:
    CONFIG_PATH = path_normalise(DEFAULT_CONFIG_PATH)

CONFIG_SETUP = [
    {'key': 'master_config',
     'def': lambda _: DEFAULT_CONFIG_PATH,
     'prompt': 'Choose a location for the OPUS master config'},

    {'key': 'install_dir',
     'def': lambda _: '~/.opus',
     'prompt': 'Choose a directory for your OPUS installation to reside in'},

    {'key': 'uds_path',
     'def': lambda cfg: os.path.join(cfg['install_dir'], 'uds_sock'),
     'prompt': 'Choose a location for the OPUS Unix Domain Socket'},

    {'key': 'db_path',
     'def': lambda cfg: os.path.join(cfg['install_dir'], 'prov.neo4j'),
     'prompt': 'Choose a location for the OPUS database to reside in'},

    {'key': 'bash_var_path',
     'def': lambda _: '~/.opus-vars',
     'prompt': 'Choose a location for the OPUS bash variables cfg_file'},

    {'key': 'python_binary',
     'def': lambda _: '/usr/bin/python2.7',
     'prompt': 'What is the location of your python 2.7 binary'},

    {'key': 'java_home',
     'def': lambda _: '/usr/lib/jvm/java-7-common',
     'prompt': 'Where is your jvm installation'},

    {'key': 'debug_mode',
     'def': lambda _: False,
     'prompt': 'Set OPUS to debug mode'}
]


def auto_read_config(func):

    @functools.wraps(func)
    def inner(config, *args, **kwargs):
        if config is not None:
            cfg = load_config(config)
        else:
            cfg = load_config()
        return func(cfg, *args, **kwargs)
    return inner


@memoised
def compute_config_check(cfg):
    sha1 = hashlib.sha1()

    cfg_str = yaml.dump(cfg)
    sha1.update(cfg_str)
    return cfg_str, sha1.hexdigest()


def is_opus_active():
    return ("LD_PRELOAD" in os.environ and
            "libopusinterpose.so" in os.environ['LD_PRELOAD'] and
            ("OPUS_INTERPOSE_MODE" in os.environ and
             os.environ['OPUS_INTERPOSE_MODE'] != "0"))


def read_config(config_path):
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as cfg_file:
                check = cfg_file.readline()
                return (check, yaml.load(cfg_file.read()))
        except [yaml.error.YAMLError, IOError]:
            raise FailedConfigError()
    else:
        raise FailedConfigError()


def write_config(config_path, cfg):
    config_path = path_normalise(config_path)
    cfg_str, cfg_check = compute_config_check(cfg)
    with open(config_path, "w") as cfg_file:
        cfg_file.write(cfg_check)
        cfg_file.write("\n")
        cfg_file.write(cfg_str)


def load_config(config_path=CONFIG_PATH):
    try:
        check, cfg = read_config(config_path)
    except FailedConfigError:
        print("Error: Your config file is missing.")
        resp = raw_input("Do you want to regenerate it? [Y/n]")
        if resp == "" or resp.upper() == "Y":
            cfg = generate_config()
            check = ""
        else:
            raise

    _, cfg_check = compute_config_check(cfg)
    if check != cfg_check:
        update_config_subsidiaries(cfg)
        write_config(config_path, cfg)
    return cfg


def update_config_subsidiaries(cfg):
    print("Config file modified, applying...")
    generate_bash_var_file(cfg)
    generate_backend_cfg_file(cfg)
    print("Application complete.")


def generate_config(existing=None):
    if existing is None:
        existing = {}
    cfg = {}

    for quest in CONFIG_SETUP:
        if quest['key'] in existing:
            default = existing[quest['key']]
        else:
            default = quest['def'](cfg)
        prompt = "{} [{}]:".format(quest['prompt'], default)
        resp = raw_input(prompt)
        if resp == "":
            cfg[quest['key']] = default
        else:
            cfg[quest['key']] = resp

    return cfg


def generate_bash_var_file(cfg):
    var_file_path = path_normalise(cfg['bash_var_path'])

    with open(var_file_path, "w") as var_file:
        var_file.write(
            "#Auto generated by opusctl\n"
            "export PATH=$PATH:{bin_dir}\n"
            "export PYTHONPATH=$PYTHONPATH:{lib_dir}:{py_dir}\n"
            "export PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=cpp\n"
            "export OPUS_MASTER_CONFIG={conf_loc}\n".format(
                bin_dir=path_normalise(
                    os.path.join(cfg['install_dir'], "bin")
                ),
                lib_dir=path_normalise(
                    os.path.join(cfg['install_dir'], "lib")
                ),
                py_dir=path_normalise(
                    os.path.join(cfg['install_dir'], "src", "backend")
                ),
                conf_loc=path_normalise(
                    cfg['master_config']
                )
            )
        )


def generate_backend_cfg_file(cfg):
    backend_cfg_path = path_normalise(os.path.join(cfg['install_dir'],
                                                   "opus-cfg.yaml"))

    log_level = "DEBUG" if cfg['debug_mode'] else "ERROR"
    log_file = path_normalise(os.path.join(cfg['install_dir'], "opus.log"))
    uds_sock = path_normalise(cfg['uds_path'])
    db_path = path_normalise(cfg['db_path'])
    touch_file = path_normalise(os.path.join(cfg['install_dir'], ".opus-live"))

    with open(backend_cfg_path, "w") as backend_cfg:
        backend_cfg.write(
            "LOGGING:\n"
            "  version: 1\n"
            "  formatters:\n"
            "    full:\n"
            "      format: \"%(asctime)s %(levelname)s "
            "L%(lineno)d -> %(message)s\"\n"
            "  handlers:\n"
            "    file:\n"
            "      class: logging.FileHandler\n"
            "      level: DEBUG\n"
            "      formatter: full\n"
            "      filename: {log_file}\n"
            "  root:\n"
            "    level: {log_level}\n"
            "    handlers: [file]\n\n"
            "MODULES:\n"
            "  Producer: SocketProducer\n"
            "  Analyser: PVMAnalyser\n"
            "  CommandInterface: TCPInterface\n\n"
            "PRODUCER:\n"
            "  SocketProducer:\n"
            "    comm_mgr_type: UDSCommunicationManager\n"
            "    comm_mgr_args:\n"
            "        uds_path: {uds_sock}\n"
            "        max_conn: 10\n"
            "        select_timeout: 5.0\n\n"
            "ANALYSER:\n"
            "  PVMAnalyser:\n"
            "    storage_type: DBInterface\n"
            "    storage_args:\n"
            "      filename: {db_path}\n"
            "    opus_lite: true\n"
            "COMMANDINTERFACE:\n"
            "  TCPInterface:\n"
            "    listen_addr: localhost\n"
            "    listen_port: 10101\n\n"
            "GENERAL:\n"
            "  touch_file: {touch_file}\n".format(
                log_level=log_level,
                log_file=log_file,
                uds_sock=uds_sock,
                db_path=db_path,
                touch_file=touch_file))


def is_backend_active(cfg):
    opus_pid_file = path_normalise(os.path.join(cfg['install_dir'], ".pid"))
    try:
        with open(opus_pid_file, "r") as p_file:
            opus_pid = int(p_file.read())
    except IOError:
        return False

    try:
        opus = psutil.Process(opus_pid)
    except psutil.NoSuchProcess:
        return False

    cmd_str = ' '.join(opus.cmdline())
    return "run_server.py" in cmd_str


def start_opus_backend(cfg):
    if is_opus_active():
        os.environ['OPUS_INTERPOSE_MODE'] = "0"
    if 'JAVA_HOME' not in os.environ:
        os.environ['JAVA_HOME'] = cfg['java_home']

    try:
        pid = os.fork()
        if pid > 0:
            return
    except OSError:
        sys.exit(1)

    os.chdir(path_normalise(cfg['install_dir']))
    os.setsid()
    os.umask(0)

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)

    err_log = path_normalise(os.path.join(cfg['install_dir'], "opus_err.log"))
    sys.stdout.flush()
    sys.stderr.flush()
    sti = file("/dev/null", 'r')
    sto = open(err_log, 'w+')
    os.dup2(sti.fileno(), sys.stdin.fileno())
    os.dup2(sto.fileno(), sys.stdout.fileno())
    os.dup2(sto.fileno(), sys.stderr.fileno())
    sto.close()

    opus_pid_file = path_normalise(os.path.join(cfg['install_dir'],
                                                ".pid"))

    backend_cfg_path = path_normalise(os.path.join(cfg['install_dir'],
                                                   "opus-cfg.yaml"))
    run_server_path = path_normalise(os.path.join(cfg['install_dir'],
                                                  "src", "backend",
                                                  "run_server.py"))

    try:
        pid = os.fork()
        if pid > 0:
            os.waitpid(pid, 0)
        else:
            pid = str(os.getpid())
            p_file = open(opus_pid_file, 'w+')
            p_file.write(pid)
            p_file.close()
            os.execvp(cfg['python_binary'],
                      [cfg['python_binary'],
                       "-O",
                       run_server_path,
                       backend_cfg_path])
    except OSError:
        sys.exit(1)

    os.unlink(opus_pid_file)


@cmd_handler('launch')
@auto_read_config
def launch_under_opus(cfg, binary, arguments):

    if not is_backend_active(cfg):
        print("Attempting to start OPUS backend.")
        start_opus_backend(cfg)

    opus_preload_lib = path_normalise(os.path.join(cfg['install_dir'],
                                                   'lib',
                                                   'libopusinterpose.so'))
    if 'LD_PRELOAD' in os.environ:
        if opus_preload_lib not in os.environ['LD_PRELOAD']:
            os.environ['LD_PRELOAD'] = (os.environ['LD_PRELOAD'] + " " +
                                        opus_preload_lib)
    else:
        os.environ['LD_PRELOAD'] = opus_preload_lib

    os.environ['OPUS_UDS_PATH'] = path_normalise(cfg['uds_path'])
    os.environ['OPUS_MSG_AGGR'] = "1"
    os.environ['OPUS_MAX_AGGR_MSG_SIZE'] = "65536"
    os.environ['OPUS_LOG_LEVEL'] = "3"  # Log critical
    os.environ['OPUS_INTERPOSE_MODE'] = "1"  # OPUS lite

    os.execvp(binary, [binary] + arguments)


@cmd_handler('exclude')
@auto_read_config
def launch_excluded(_, binary, arguments):
    if is_opus_active():
        os.environ['OPUS_INTERPOSE_MODE'] = "0"
    else:
        print("OPUS is not active.")
    os.execvp(binary, [binary] + arguments)


@cmd_handler('enable')
@auto_read_config
def handle_enable(cfg):
    '''Starts OPUS backend.'''
    if not is_backend_active(cfg):
        print("Attempting to start OPUS backend.")
        start_opus_backend(cfg)
    else:
        print("OPUS backend already running.")


@cmd_handler('conf')
def handle_reconfigure(config):
    try:
        if config is not None:
            _, cfg = read_config(config)
        else:
            _, cfg = read_config(CONFIG_PATH)
    except FailedConfigError:
        _, cfg = "", {}

    if config is not None:
        cfg['master_config'] = config

    new_cfg = generate_config(cfg)

    update_config_subsidiaries(new_cfg)

    write_config(new_cfg['master_config'], new_cfg)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=False)

    sub_parsers = parser.add_subparsers(title="commands", dest="cmd")
    sub_parsers.add_parser("conf")

    launch = sub_parsers.add_parser("launch")
    launch.add_argument("binary", nargs='?', default=os.environ['SHELL'])
    launch.add_argument("arguments", nargs=argparse.REMAINDER)

    exclude = sub_parsers.add_parser("exclude")
    exclude.add_argument("binary", nargs='?', default=os.environ['SHELL'])
    exclude.add_argument("arguments", nargs=argparse.REMAINDER)

    sub_parsers.add_parser("enable")

    return parser.parse_args()


def main():
    args = parse_args()

    params = {k: v for k, v in args._get_kwargs() if k != 'cmd'}

    try:
        cmd_handler.handlers[args.cmd](**params)
    except FailedConfigError:
        print("Failed to execute command due to insufficient configuration. "
              "Please run the '{} conf' command "
              "to reconfigure the program.".format(sys.argv[0]))

if __name__ == "__main__":
    main()
