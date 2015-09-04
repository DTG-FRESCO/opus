# -*- coding: utf-8 -*-
# pylint: disable=unused-import
from __future__ import absolute_import, division, print_function

import sys

try:
    import prettytable
    import psutil
    import yaml
    import termcolor
except ImportError as exe:
    if '-v' in sys.argv:
        print(exe.message)
    sys.exit(1)
