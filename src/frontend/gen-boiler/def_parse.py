#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''

'''
from __future__ import (print_function, absolute_import, division)

import logging
import re
import sys
import yaml

DEFINITION_REG = "([\w* _]+(?:\*| ))([\w_]+)\((.*?)\);"
ARG_SPLIT_REG = ",*\s*([^,]+),*"
ARG_DEF_REG = "^([\w* _]+(?:\*| ))([\w_]+)$"


class FunctionParsingException(Exception):
    '''General base exception class for any errors in parsing the function
    definitions file.'''
    pass


class InvalidLineException(FunctionParsingException):
    '''Exception indicating a failure to parse the outer body of a function.'''
    pass


class InvalidArgumentException(FunctionParsingException):
    '''Exception indicating a failure to parse an argument of a function.'''
    pass


def match_single_arg(arg):
    '''Given a single function argument string parse the arguments name,
    type and read value and return them.

    Returns (type,name,flags)'''
    arg_flags = []

    (read_sub, count) = re.subn("read ", "", arg)
    if count > 0:
        arg_flags += ["read"]

    (can_sub, count) = re.subn("can ", "", read_sub)
    if count > 0:
        arg_flags += ["can"]

    (abs_sub, count) = re.subn("abs ", "", can_sub)
    if count > 0:
        arg_flags += ["abs"]

    arg_def = re.match(ARG_DEF_REG, abs_sub)

    if arg_def is None:
        logging.error("Invalid Argument: %s", arg)
        raise InvalidArgumentException()
    else:
        (arg_type, arg_name) = arg_def.groups()
    return (arg_type.rstrip(), arg_name, arg_flags)


def match_args_from_list(args):
    '''Given a list of arguments return a list of their argument information
    structures.'''
    ret = []
    inner_matches = re.findall(ARG_SPLIT_REG, args)
    for arg in inner_matches:
        (arg_type, arg_name, arg_flags) = match_single_arg(arg)

        arg_info = {'type': arg_type,
                    'name': arg_name,
                    'flags': arg_flags}

        logging.info("Gathered argument from line: %s", arg_info)

        ret += [arg_info]
    return ret


def match_func_in_line(line):
    '''Given a line for a function definition that is not empty or a comment
    parse the function information from that line.

    Returns (return_type,name,arg_list)'''
    (nogen_sub, count) = re.subn("nogen ", "", line)
    nogen = count > 0

    outer = re.match(DEFINITION_REG, nogen_sub)

    if outer is None:
        logging.error("Invalid line: %s"
                      "All lines should either be empty, start with a # "
                      "or contain a valid function definition.",
                      line)
        raise InvalidLineException()
    else:
        (func_ret, func_name, arg_list) = outer.groups()

        if(arg_list == "void" or arg_list == ""):
            func_args = []
            func_flags = []
        elif(nogen):
            func_args = arg_list
            func_flags = ["nogen"]
        else:
            func_args = match_args_from_list(arg_list)
            func_flags = []

        return (func_ret.rstrip(), func_name, func_flags, func_args)


def gather_funcs(file_handle):
    '''Parse a given file_handle, extracting function definitions from each
    line and returning a list of function objects.'''
    funcs = []

    for line in file_handle:
        tmp_line_str = line
        if line == "\n" or line.startswith("#"):
            continue
        try:
            (func_ret, func_name, func_flags, func_args) = match_func_in_line(line)
        except FunctionParsingException:
            logging.error("Failed to parse the following function definition: "
                          "%s", line)
            continue

        function_info = {'name': func_name,
                         'ret': func_ret,
                         'flags': func_flags,
                         'args': func_args}

        logging.info("Gathered function from file: %s", function_info)

        funcs += [function_info]
    return funcs


def pretty_yaml(funcs):
    for func in funcs:
        print("- name: %s"%func['name'])
        print("  ret: \"%s\""%func['ret'])
        print("  flags: [%s]"%(",".join(func['flags'])))
        if isinstance(func['args'], list):
            if len(func['args']) == 0:
                print("  args: []")
            else:
                print("  args:")
                for arg in func['args']:
                    print("  - flags:")
		    for flag in arg['flags']:
			print("      %s: \"\""%(flag))
                    print("    name: %s"%arg['name'])
                    print("    type: \"%s\""%arg['type'])
                    print("")
        else:
            print("  args: \"%s\""%(func['args']))
        print("")


def main():
    pretty_yaml(gather_funcs(sys.stdin))


if __name__ == "__main__":
    main()
