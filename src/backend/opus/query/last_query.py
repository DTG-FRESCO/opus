from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (cc_msg_pb2)
from opus.query import client_query
from opus import storage, query_interface

@client_query.ClientQueryControl.register_query_method("query_file")
def query_file(db_iface, msg):
    '''Given a file name, this method returns the
    last command commands on that file'''
    file_name = None
    rsp = cc_msg_pb2.ExecQueryMethodRsp()

    for arg in msg.args:
        if arg.key == "name":
            file_name = arg.value

    if file_name is None:
        rsp.error = "File name not provided in message"
        return rsp

    rows = db_iface.locked_query(
                 "START g1=node:FILE_INDEX('name:" + file_name + "') "
                 "MATCH (g1)-[:GLOBAL_OBJ_PREV*0..]->(gn)-[r1:LOC_OBJ]->(l)"
                 "-[:PROC_OBJ]->(p)-[:OTHER_META]->(m) "
                 "WHERE m.name = 'cmd_args' AND r1.state in [3,4]"
                 "RETURN m.value as val ORDER BY p.timestamp LIMIT 1")
    result = ""
    for row in rows:
        result += row['val']
        result += "\n"

    rsp.rsp_data = result
    return rsp


@client_query.ClientQueryControl.register_query_method("query_folder")
def query_folder(db_iface, msg):
    '''Given a folder name, this method returns the last N executed
    commands from that folder as current working directory'''
    folder_name = None
    result_limit = "5" # Default

    rsp = cc_msg_pb2.ExecQueryMethodRsp()

    for arg in msg.args:
        if arg.key == "name":
            folder_name = arg.value
        elif arg.key == "limit":
            result_limit = arg.value

    if folder_name is None:
        rsp.error = "Folder name not provided in message"
        return rsp

    rows = db_iface.locked_query("START g=node:PROC_INDEX('name:*') "
                 "MATCH (g)-[:LOC_OBJ]->(l)-[:PROC_OBJ]->(p),"
                 "      (p)-[:OTHER_META]->(m),"
                 "      (p)-[:OTHER_META]->(m1) "
                 "WHERE m.name = 'cwd' AND m.value = \"" + folder_name + "\" "
                 "AND m1.name = 'cmd_args' "
                 "RETURN m1.value as val "
                 "ORDER BY p.timestamp DESC LIMIT " + result_limit)
    result = ""
    for row in rows:
        result += row['val']
        result += "\n"

    rsp.rsp_data = result
    return rsp
