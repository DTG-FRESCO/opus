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
import logging
import re
import sys

try:
    import jinja2
except ImportError:
    print("Jinja2 module is not present!")
    print("Please install the Jinja2 module.")
    sys.exit(1)

DEFINITION_REG = "([\w* _]+(?:\*| ))([\w_]+)\((.*?)\);"
ARG_SPLIT_REG = ",*\s*([^,]+),*"
ARG_DEF_REG = "^([\w* _]+(?:\*| ))([\w_]+)$"

PRINTF_MAP = {"int": '"%d"',
              "long int": '"%ld"',
              "long": '"%ld"',
              "off_t": '"%ld"',
              "mode_t": '"%u"',
              "size_t *": '"%p"',
              "off64_t": '"%ld"',
              "size_t": '"%lu"',
              "FILE *": ''}

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

        logging.info("Gathered argument from line: %s", arg_info)

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

def get_func_ptr(line):
    ''' Given a line this function returns a function name as string
    along with the function pointer type'''
    line = line.replace("nogen ","")
    line = line.replace("read ","")

    outer = re.match(DEFINITION_REG, line)
    if outer is None:
        logging.error("Invalid line: %s"
                      "All lines should either be empty, start with a # "
                      "or contain a valid function definition.",
                      line)
        raise InvalidLineException()
    else:
        (func_ret, func_name, arg_list) = outer.groups()
        func_ptr_name = "*" + func_name.upper() + "_POINTER"
        typedef_str = "typedef " + func_ret + "(" + func_ptr_name + ")" + "(" + arg_list + ");"

        return (func_name, typedef_str)

def gather_funcs(file_handle):
    '''Parse a given file_handle, extracting function definitions from each
    line and returning a list of function objects.'''
    funcs = []
    func_ptrs = []

    for line in file_handle:
        tmp_line_str = line
        if line == "\n" or line.startswith("#"):
            continue
        try:
            func_name_str, func_ptr_type = get_func_ptr(tmp_line_str)
            func_ptr_info = {'func_name_str': func_name_str,
                            'func_ptr_type': func_ptr_type }
            func_ptrs += [func_ptr_info]

            if line.startswith("nogen"):
                continue

            (func_ret, func_name, func_args) = match_func_in_line(line)
        except FunctionParsingException:
            logging.error("Failed to parse the following function definition: "
                          "%s", line)
            continue

        function_info = {'name': func_name,
                         'ret': func_ret,
                         'args': func_args}

        logging.info("Gathered function from file: %s", function_info)

        funcs += [function_info]
    return funcs, func_ptrs


def init_logging():
    '''Setup the logging framework.'''
    form_file = logging.Formatter(fmt="%(asctime)s %(levelname)s"
                                      " L%(lineno)d -> %(message)s")
    form_con = logging.Formatter(fmt="%(levelname)s:%(message)s")

    logging.getLogger('').setLevel(logging.INFO)

    hand_con = logging.StreamHandler()
    hand_con.setLevel(logging.ERROR)
    hand_con.setFormatter(form_con)
    logging.getLogger('').addHandler(hand_con)

    try:
        hand_file = logging.FileHandler("gen_boiler.log","w")
    except IOError as exc:
        logging.error("Failed to open log file.")
        logging.error(exc)
    else:
        hand_file.setLevel(logging.INFO)
        hand_file.setFormatter(form_file)
        logging.getLogger('').addHandler(hand_file)


def filter_capture_arg(args):
    '''Check the args list for any captured arguments.'''
    for arg in args:
        if arg['read']:
            return True
    return False


def filter_buffer_arg(args):
    '''Check the args list for any arguments that need conversion to strings.'''
    for arg in args:
        if arg['read'] and arg['type'] in PRINTF_MAP:
            return True
    return False


def main():
    '''Main function, parses command line arguments, parses the given file of
    function definitions then renders the two templates using the information
    extracted.'''

    init_logging()

    parser = argparse.ArgumentParser(description="Creates a set of "
                                     "interposition functions from "
                                     "a description file.")
    parser.add_argument('input_file',
                        help="Name of the file to read the function "
                        "descriptions from, replace with - to use "
                        "STDIN instead.")
    parser.add_argument('output_dest',
                        default="./functions.C", nargs="?",
                        help="Location the created files will be "
                        "written to, in the form of a full filename. "
                        "(Default is ./functions.C)")

    args = parser.parse_args()
    if args.input_file == "-":
        logging.info("Using STDIN as function definition source.")
        file_handle = sys.stdin
    else:
        logging.info("Using %s as function definition source.", args.input_file)
        try:
            file_handle = open(args.input_file, "rt")
        except IOError as exc:
            logging.critical("Failed to open input file %s.", args.input_file)
            logging.critical(exc)
            return None

    logging.info("Gathering function definitions from the source locaiton.")

    funcs, func_ptrs = gather_funcs(file_handle)
    file_handle.close()

    logging.info("Initialising the Jinja template loader.")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

    env.filters['capture_arg'] = filter_capture_arg
    env.filters['buffer_arg'] = filter_buffer_arg

    logging.info("Beginning rendering of header file.")
    try:
        header_name = "func_ptr_types.h"
        with open(header_name, "wt") as header_file:
            logging.info("Rendering the header template to the header file %s.",
                         header_name)
            header_tmpl = env.get_template("header.tmpl")
            header_file.write(header_tmpl.render(func_ptr_types=func_ptrs))
    except IOError as exc:
        logging.critical("Failed to open header output file %s.", header_name)
        logging.critical(exc)
        return None
    logging.info("Completing rendering of header file.")

    logging.info("Beginning rendering of object file.")
    try:
        with open(args.output_dest, "wt") as object_file:
            logging.info("Rendering the object template to the object file %s.",
                         args.output_dest)
            object_tmpl = env.get_template("func.tmpl")
            object_file.write(object_tmpl.render(fn_list=funcs,
                                                 printf_map=PRINTF_MAP)
                                                )
    except IOError as exc:
        logging.critical("Failed to open object output file %s.",
                         args.output_dest)
        logging.critical(exc)
        return None
    logging.info("Completing rendering of object file.")
    return 0


if __name__ == "__main__":
    if main() is None:
        sys.exit(1)
