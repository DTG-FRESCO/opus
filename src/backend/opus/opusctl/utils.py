# -*- coding: utf-8 -*-
from __future__ import absolute_import, division, print_function

import os

from .. import cc_utils, exception


def path_normalise(path):
    return os.path.abspath(os.path.expanduser(path))


def is_opus_ipose_lib_set():
    return ("LD_PRELOAD" in os.environ and
            "libopusinterpose.so" in os.environ['LD_PRELOAD'])


def is_opus_active():
    return (is_opus_ipose_lib_set() and
            ("OPUS_INTERPOSE_MODE" in os.environ and
             os.environ['OPUS_INTERPOSE_MODE'] != "0"))


def is_server_active(cfg=None, helper=None):
    if helper is None:
        if cfg is not None:
            helper = cc_utils.CommandConnectionHelper(cfg['cc_addr'])
        else:
            raise ValueError("One of cfg and helper must not be None.")
    else:
        if cfg is not None:
            raise ValueError("One of cfg and helper must not be None.")

    try:
        helper.make_request({"cmd": "status"})
    except exception.BackendConnectionError:
        return False
    return True


def reset_opus_env(cfg):
    opus_vars = ['OPUS_INTERPOSE_MODE',
                 'OPUS_UDS_PATH',
                 'OPUS_MSG_AGGR',
                 'OPUS_MAX_AGGR_MSG_SIZE',
                 'OPUS_LOG_LEVEL']
    for var in opus_vars:
        if var in os.environ:
            del os.environ[var]

    opus_preload_lib = path_normalise(os.path.join(cfg['install_dir'],
                                                   'lib',
                                                   'libopusinterpose.so'))
    if 'LD_PRELOAD' in os.environ:
        if os.environ['LD_PRELOAD'] == opus_preload_lib:
            del os.environ['LD_PRELOAD']
        else:
            os.environ['LD_PRELOAD'] = os.environ['LD_PRELOAD'].replace(
                opus_preload_lib, ""
            ).strip()
