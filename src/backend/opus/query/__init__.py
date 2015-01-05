# -*- coding: utf-8 -*-
'''
Client Query - Init Module
'''

from opus.query.client_query import (ClientQueryControl)

# Import query methods here
from opus.query.env_diff import (get_execs, get_diffs)
from opus.query.last_query import (query_file, query_folder)
