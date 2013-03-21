#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Script to generate boiler plate code for function interposition based on a file
containing definitions of functions to interpose and a pair of templates for
the files to be genreated based on this gathered information.
'''
from __future__ import (unicode_literals, print_function,
                        absolute_import, division)

import argparse
import jinja2
import logging
import re
import sys

DEFINITION_REG = "([\w* _]+(?:\*| ))([\w_]+)\((.*?)\);"
ARG_SPLIT_REG = ",*\s*([^,]+),*"
ARG_DEF_REG = "^([\w* _]+(?:\*| ))([\w_]+)$"

PRINTF_MAP = {"int": '"%d"',
              "long int": '"%ld"',
              "long": '"%ld"',
              "off_t": '"%ld"',
              "uid_t": '"%u"',
              "gid_t": '"%u"',
              "mode_t": '"%u"',
              "size_t *": '"%p"',
              "off64_t": '"%ld"',
              "size_t": '"%lu"'}

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

    Returns (type,name,read)'''
    (read_sub, count) = re.subn("read ", "", arg)
    arg_read = count > 0

    arg_def = re.match(ARG_DEF_REG, read_sub)

    if arg_def is None:
        logging.error("Invalid Argument: %s", arg)
        raise InvalidArgumentException()
    else:
        (arg_type, arg_name) = arg_def.groups()
    return (arg_type.rstrip(), arg_name, arg_read)


def match_args_from_list(args):
    '''Given a list of arguments return a list of their argument information
    structures.'''
    ret = []
    inner_matches = re.findall(ARG_SPLIT_REG, args)
    for arg in inner_matches:
        (arg_type, arg_name, arg_read) = match_single_arg(arg)

        arg_info = {'type': arg_type,
                    'name': arg_name,
                    'read': arg_read}

        logging.info("Gathered argument from line: %s",
                     arg_info)

        ret += [arg_info]
    return ret


def match_func_in_line(line):
    '''Given a line for a function definition that is not empty or a comment
    parse the function information from that line.

    Returns (return_type,name,arg_list)'''
    outer = re.match(DEFINITION_REG, line)

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
        else:
            func_args = match_args_from_list(arg_list)

        return (func_ret.rstrip(), func_name, func_args)


def gather_funcs(file_handle):
    '''Parse a given file_handle, extracting function definitions from each
    line and returning a list of function objects.'''
    funcs = []
    for line in file_handle:
        if line == "\n" or line.startswith("#"):
            continue
        (func_ret, func_name, func_args) = match_func_in_line(line)

        function_info = {'name': func_name,
                         'ret': func_ret,
                         'args': func_args}

        logging.info("Gathered function from file: %s",
                     function_info)

        funcs += [function_info]
    return funcs


def main():
    '''Main function, parses command line arguments, parses the given file of
    function definitions then renders the two templates using the information
    extracted.'''

    logging.basicConfig(filename='gen_boiler.log',
                        filemode="w",
                        level=logging.INFO)
    parser = argparse.ArgumentParser(description="Creates a set of "
                                     "interposition functions from "
                                     "a description file.")
    parser.add_argument('input_file',
                        help="Name of the file to read the function "
                        "descriptions from, replace with - to use "
                        "STDIN instead.")
    parser.add_argument('output_dest',
                        default="./functions", nargs="?",
                        help="Location the created files will be "
                        "written to, in the form of a full filename "
                        "that will have .h and .C appended to it. "
                        "(Default is ./functions)")

    args = parser.parse_args()
    if args.input_file == "-":
        logging.info("Using STDIN as function definition source.")
        file_handle = sys.stdin
    else:
        logging.info("Using %s as function definition source.", args.input_file)
        file_handle = open(args.input_file, "rt")

    logging.info("Gathering function definitions from the source locaiton.")
    try:
        funcs = gather_funcs(file_handle)
    except FunctionParsingException:
        return None

    file_handle.close()

    logging.info("Initialising the Jinja template loader.")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

    logging.info("Beginning rendering of header file.")
    with open(args.output_dest + ".h", "wt") as header_file:
        logging.info("Rendering the header template to the header file %s.",
                     args.output_dest + ".h")
        header_tmpl = env.get_template("header.tmpl")
        header_file.write(header_tmpl.render(fn_list=funcs))
    logging.info("Completing redering of header file.")

    logging.info("Beginning rendering of object file.")
    with open(args.output_dest + ".C", "wt") as object_file:
        logging.info("Rendering the object template to the object file %s.",
                     args.output_dest + ".C")
        object_tmpl = env.get_template("func.tmpl")
        object_file.write(object_tmpl.render(fn_list=funcs,
                                             printf_map=PRINTF_MAP)
                          )
    logging.info("Completing rendering of object file.")


if __name__ == "__main__":
    main()
