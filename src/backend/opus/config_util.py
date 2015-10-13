# -*- coding: utf-8 -*-
'''
Config utility for the OPUS backend
'''
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from .exception import InvalidConfigFileException, InvalidTagException
from . import (common_utils)

import logging


def safe_read_config(cfg, section, key=None):
    '''Read the value of key from section in cfg while appropriately catching
    missing section and key exceptions and handling them by re-raising invalid
    config errors.'''
    try:
        sec = cfg[section]
    except KeyError:
        logging.error("Config file lacks %s section.", section)
        raise InvalidConfigFileException()
    if key is None:
        return sec
    else:
        try:
            return sec[key]
        except KeyError:
            logging.error("Config file lacks %s key in section %s.",
                          key, section)
            raise InvalidConfigFileException()


def load_module(config, mod_name, mod_base,
                mod_extra_args=None, mod_type=None):
    '''Loads the configuration for a module of name and base class from config,
    allows the load to be augmented with extra arguments and allow config type
    lookup to be overridden.'''
    if mod_type is None:
        mod_type = safe_read_config(config, "MODULES", mod_name)

    mod_args = safe_read_config(config, mod_name.upper(), mod_type)

    if mod_extra_args is not None:
        mod_args.update(mod_extra_args)

    try:
        mod = common_utils.meta_factory(mod_base,
                                        mod_type,
                                        **mod_args)
    except InvalidTagException:
        logging.error("Invalid %s type %s in config file.",
                      mod_name, mod_type)
        raise InvalidConfigFileException()
    except TypeError:
        logging.error("Config section %s is incorrectly setup.",
                      mod_type)
        raise InvalidConfigFileException()
    return mod
