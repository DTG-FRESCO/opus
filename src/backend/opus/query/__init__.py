# -*- coding: utf-8 -*-
'''
Client Query - Init Module
'''

from .client_query import (ClientQueryControl)

# Import query methods here
from .env_diff import (get_execs, get_diffs)
from .last_query import (query_file, query_folder)
