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
import sys
import yaml

try:
    import jinja2
except ImportError:
    print("Jinja2 module is not present!")
    print("Please install the Jinja2 module.")
    sys.exit(1)


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
        if 'read' in arg['flags']:
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

    funcs = yaml.safe_load(file_handle)
    file_handle.close()

    logging.info("Initialising the Jinja template loader.")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader("."))

    env.filters['capture_arg'] = filter_capture_arg

    logging.info("Beginning rendering of header file.")
    try:
        header_name = "func_ptr_types.h"
        with open(header_name, "wt") as header_file:
            logging.info("Rendering the header template to the header file %s.",
                         header_name)
            header_tmpl = env.get_template("header.tmpl")
            header_file.write(header_tmpl.render(fn_list=funcs))
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
            object_file.write(object_tmpl.render(fn_list=funcs))
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
