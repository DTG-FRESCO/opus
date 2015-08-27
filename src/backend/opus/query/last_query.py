from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import datetime

from . import client_query


def fmt_time(time):
    return datetime.datetime.fromtimestamp(time).strftime('%Y-%m-%d %H:%M:%S')


@client_query.ClientQueryControl.register_query_method("query_file")
def query_file(db_iface, args):
    '''Given a file name, this method returns the
    last command that modified the file'''
    result_limit = "10"  # Default

    if 'name' not in args:
        return {"success": False, "msg": "File name not provided in message"}

    rows = db_iface.locked_query(
        "START g1=node:FILE_INDEX('name:" + args['name'] + "') "
        "MATCH (g1)-[:GLOBAL_OBJ_PREV*0..]->(gn)-[r1:LOC_OBJ]->(l)"
        "-[:PROC_OBJ]->(p)-[:OTHER_META]->(m) "
        "WHERE m.name = 'cmd_args' AND r1.state in [3,4] "
        "AND m.value <> '' "
        "RETURN distinct p, m.value as val "
        "ORDER BY p.sys_time DESC LIMIT " + result_limit)

    data = [{'ts': fmt_time(r['p']['sys_time']),
             'cmd': r['val']}
            for r in rows]

    if len(data) > 0:
        return {'success': True, 'data': data}
    else:
        return {'success': False, 'msg': "No data available for that file."}


@client_query.ClientQueryControl.register_query_method("query_folder")
def query_folder(db_iface, args):
    '''Given a folder name, this method returns the last N executed
    commands from that folder as current working directory'''
    result_limit = "20"  # Default

    if 'limit' in args:
        result_limit = str(args['limit'])

    if 'name' not in args:
        return {"success": False, "msg": "Folder name not provided in message"}

    rows = db_iface.locked_query(
        "START g=node:PROC_INDEX('name:*') "
        "MATCH (g)-[:LOC_OBJ]->(l)-[:PROC_OBJ]->(p),"
        "      (p)-[:OTHER_META]->(m),"
        "      (p)-[:OTHER_META]->(m1) "
        "WHERE m.name = 'cwd' AND m.value = \"" + args['name'] + "\" "
        "AND m1.name = 'cmd_args' "
        "AND m1.value <> '' "
        "RETURN m1.value as val, p "
        "ORDER BY p.sys_time DESC LIMIT " + result_limit)

    data = [{'ts': fmt_time(r['p']['sys_time']),
             'cmd': r['val']}
            for r in rows]

    if len(data) > 0:
        return {'success': True, 'data': data}
    else:
        return {'success': False,
                'msg': "No programs recorded executing from that directory."}
