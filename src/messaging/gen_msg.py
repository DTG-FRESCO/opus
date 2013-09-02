#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Script to generate messaging classes and structures for coomunication
between different parts of the application.
'''
from __future__ import (unicode_literals, print_function,
                        absolute_import, division)

import sys

import jinja2
import yaml

TYPE_MAP = {
    "uint64_t": "Q",
    "int64_t":  "q"
           }

def struct_string(msg):
    '''Construct a string for struct.pack/unpack.'''
    return "".join([TYPE_MAP[field["type"]] for field in msg["fields"]])

def render(tmpl, out, env, msgs):
    '''Render tmpl to out using env and msgs.'''
    tmpl_obj = env.get_template(tmpl)
    with open(out, "w") as handle:
        handle.write(tmpl_obj.render(msgs=msgs))

def main():
    '''Main function.'''
    with open(sys.argv[1], "r") as handle:
        msg_defs = yaml.safe_load(handle)

    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

    env.filters['struct_string'] = struct_string

    render("c.tmpl", "messaging.h", env, msg_defs)

    render("py.tmpl", "messaging.py", env, msg_defs)

main()