from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (cc_msg_pb2)
from opus.query import client_query
from opus import storage, query_interface

import datetime


class DictDiffer(object):
    """
    Calculate the difference between two dictionaries as:
    (1) items added
    (2) items removed
    (3) keys same in both but changed values
    (4) keys same in both and unchanged values
    """
    def __init__(self, current_dict, past_dict):
        self.current_dict, self.past_dict = current_dict, past_dict
        self.set_current, self.set_past = (set(current_dict.keys()),
                                           set(past_dict.keys()))
        self.intersect = self.set_current & self.set_past

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(o for o in self.intersect
                   if self.past_dict[o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect
                   if self.past_dict[o] == self.current_dict[o])


def convert_to_dict(meta_lst):
    meta_dict = {}
    for meta_node in meta_lst:
        meta_dict[meta_node['name']] = meta_node['value']
    return meta_dict


def get_date_time_str(sys_time):
    return datetime.datetime.fromtimestamp(sys_time).strftime(
        '%Y-%m-%d %H:%M:%S')


def get_proc_from_binary(db_iface, prog_name, start_date, end_date):
    proc_list = []

    qry = "START "
    qry += "bin_glob_node=node:PROC_INDEX('name:\"" + prog_name + "\"') "
    qry += "MATCH bin_glob_node-[:LOC_OBJ]->loc_node,  "
    qry += "loc_node-[:PROC_OBJ]->proc_node "

    if start_date is not None and end_date is not None:
        qry += "where proc_node.sys_time >= " + start_date
        qry += " and proc_node.sys_time <= " + end_date

    qry += " RETURN proc_node order by bin_glob_node.sys_time"

    rows = db_iface.locked_query(qry)
    for row in rows:
        proc_node = row['proc_node']
        if proc_node.PROC_PARENT.outgoing:  # This is a child process ignore it
            continue
        proc_list.append(proc_node)
    return proc_list


def get_meta_data(db_iface, proc_node, rel_type):
    '''Returns list of environment varialbles for the process'''
    meta_lst = []

    qry = "START "
    qry += "proc_node=node({id}) "
    qry += "MATCH proc_node-[:" + rel_type + "]->meta_node  "
    qry += "RETURN meta_node "
    rows = db_iface.locked_query(qry, id=proc_node.id)

    for row in rows:
        meta_node = row['meta_node']
        meta_lst.append(meta_node)
    return meta_lst


def check_proc_bin_mod(db_iface, prog_name, proc_node1, proc_node2):
    '''Returns the process(es) that wrote to the binary
    between two process invocations'''
    start_date = proc_node1['sys_time']
    end_date = proc_node2['sys_time']

    qry = "START glob_node=node:%s('%s %s')"
    time_idx_qry = query_interface.__construct_time_idx_qry(start_date,
                                                            end_date)
    if time_idx_qry is not None:
        time_idx_qry += " AND "
    else:
        time_idx_qry = ""
    qry = qry % (storage.DBInterface.FILE_INDEX, time_idx_qry,
                 query_interface.__construct_name_idx_qry(prog_name))
    qry += " MATCH glob_node-[r1:LOC_OBJ]->loc_node1,"
    qry += " loc_node1-[:PROC_OBJ]->proc_node,"
    qry += " proc_node<-[:PROC_OBJ]-loc_node2,"
    qry += " loc_node2<-[r2:LOC_OBJ]-bin_glob_node"
    qry += " where r1.state in [{w}, {rw}]"
    qry += " and r2.state in [{bin}]"
    qry += " and proc_node.sys_time >= " + str(start_date)
    qry += " and proc_node.sys_time <= " + str(end_date)
    qry += " RETURN distinct head(bin_glob_node.name) as mod_program, "
    qry += " head(glob_node.name) as bin_name, proc_node"

    result = db_iface.locked_query(qry,
                                   w=storage.LinkState.WRITE,
                                   rw=storage.LinkState.RaW,
                                   bin=storage.LinkState.BIN)
    return [{'prog': row['mod_program'],
             'date': get_date_time_str(row['proc_node']['sys_time'])}
            for row in result]


def get_diff(dict1, dict2):
    diff = DictDiffer(dict2, dict1)

    return {'added': [{'name': elem, 'value': dict2[elem]}
                      for elem in diff.added()],
            'removed': [{'name': elem, 'value': dict1[elem]}
                        for elem in diff.removed()],
            'changed': [{'name': elem,
                         'from': dict1[elem],
                         'to': dict2[elem]}
                        for elem in diff.changed()]}


def diff_other_meta(db_iface, proc_node1, proc_node2):
    other_meta_dict1 = convert_to_dict(get_meta_data(db_iface, proc_node1,
                                       storage.RelType.OTHER_META))
    other_meta_dict2 = convert_to_dict(get_meta_data(db_iface, proc_node2,
                                       storage.RelType.OTHER_META))
    return get_diff(other_meta_dict1, other_meta_dict2)


def diff_env_meta(db_iface, proc_node1, proc_node2):
    env_meta_dict1 = convert_to_dict(get_meta_data(db_iface, proc_node1,
                                     storage.RelType.ENV_META))
    env_meta_dict2 = convert_to_dict(get_meta_data(db_iface, proc_node2,
                                     storage.RelType.ENV_META))
    return get_diff(env_meta_dict1, env_meta_dict2)


def diff_lib_meta(db_iface, proc_node1, proc_node2):
    lib_meta_dict1 = convert_to_dict(get_meta_data(db_iface, proc_node1,
                                     storage.RelType.LIB_META))
    lib_meta_dict2 = convert_to_dict(get_meta_data(db_iface, proc_node2,
                                     storage.RelType.LIB_META))
    return get_diff(lib_meta_dict1, lib_meta_dict2)


@client_query.ClientQueryControl.register_query_method("get_execs")
def get_execs(db_iface, args):
    if 'prog_name' not in args:
        return {"success": False,
                "msg": "Missing program name."}
    proc_list = get_proc_from_binary(db_iface,
                                     args['prog_name'],
                                     args.get('start_date', None),
                                     args.get('end_date', None))
    if len(proc_list) == 0:
        return {"success": False,
                "msg": "Could not find any execution instances"
                       " for this binary and dates combination"}
    elif len(proc_list) == 1:
        return {"success": False,
                "msg": "Found only one execution instance"}

    rsp = {"success": True,
           "data": [],
           "mapping": {}}

    for exec_id, proc_node in enumerate(proc_list, 1):
        rsp['mapping'][str(exec_id)] = str(proc_node.id)
        rsp['data'] += [{'exec_id': exec_id,
                         'prog_name': args['prog_name'],
                         'pid': proc_node['pid'],
                         'date': get_date_time_str(proc_node['sys_time']),
                         'cmd_line': [node['value']
                                      for node in get_meta_data(
                                          db_iface,
                                          proc_node,
                                          storage.RelType.OTHER_META)
                                      if node['name'] == 'cmd_args'][0]
                         }]

    return rsp


@client_query.ClientQueryControl.register_query_method("get_diffs")
def get_diffs(db_iface, args):
    '''Given two process node IDs, we can get the diffs between
    the environments of the process'''
    if not all(n in args for n in ('node_id1', 'node_id2', 'prog_name')):
        return {"success": False,
                "msg": "Could not get process nodes"}
    proc_node1 = db_iface.db.node[int(args['node_id1'])]
    proc_node2 = db_iface.db.node[int(args['node_id2'])]

    return {"success": True,
            "bin_mods": check_proc_bin_mod(db_iface,
                                           args['prog_name'],
                                           proc_node1,
                                           proc_node2),
            "other_meta": diff_other_meta(db_iface, proc_node1, proc_node2),
            "env_meta": diff_env_meta(db_iface, proc_node1, proc_node2),
            "lib_meta": diff_lib_meta(db_iface, proc_node1, proc_node2)}
