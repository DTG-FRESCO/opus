from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from opus import (cc_msg_pb2)
from opus.query import client_query
from opus import storage, query_interface

import os
import datetime
import textwrap
from prettytable import PrettyTable

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
        self.set_current, self.set_past = set(current_dict.keys()), \
                                            set(past_dict.keys())
        self.intersect = self.set_current.intersection(self.set_past)

    def added(self):
        return self.set_current - self.intersect

    def removed(self):
        return self.set_past - self.intersect

    def changed(self):
        return set(o for o in self.intersect \
                if self.past_dict[o] != self.current_dict[o])

    def unchanged(self):
        return set(o for o in self.intersect \
                if self.past_dict[o] == self.current_dict[o])


def convert_to_dict(meta_lst):
    meta_dict = {}
    for meta_node in meta_lst:
        meta_dict[meta_node['name']] = meta_node['value']
    return meta_dict


def get_date_time_str(sys_time):
    return datetime.datetime.fromtimestamp(sys_time).strftime('%Y-%m-%d %H:%M:%S')


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
        if proc_node.PROC_PARENT.outgoing: # This is a child process, ignore it
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
    prog_list = []

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
    qry += " RETURN bin_glob_node, glob_node, proc_node"

    result = db_iface.locked_query(qry, w=storage.LinkState.WRITE,
                rw=storage.LinkState.RaW, bin=storage.LinkState.BIN)
    for row in result:
        bin_glob_node = row['bin_glob_node']
        glob_node = row['glob_node']
        proc_node = row['proc_node']
        cmd_args_node = None
        for tmp_rel in proc_node.OTHER_META.outgoing:
            if tmp_rel.end['name'] != "cmd_args":
                continue
            cmd_args_node = tmp_rel.end
        prog_list.append((glob_node, bin_glob_node, cmd_args_node))
    return prog_list


def print_diffs(dict1, dict2):
    diff = DictDiffer(dict2, dict1)

    added = None
    result = "Added:\n"
    for elem in diff.added():
        added = PrettyTable(["Key", "Value"])
        added.align["key"] = "l"
        added.padding_width = 1
        added.align["Value"] = "l"
        added.add_row([elem, textwrap.fill(dict2[elem], 50)])
    if added is not None:
        result += str(added)
        result += "\n"

    removed = None
    result += "Removed:\n"
    for elem in diff.removed():
        removed = PrettyTable(["Key", "Value"])
        removed.align["key"] = "l"
        removed.padding_width = 1
        removed.align["Value"] = "l"
        removed.add_row([elem, textwrap.fill(dict1[elem], 50)])
    if removed is not None:
        result += str(removed)
        result += "\n"

    changed = None
    result += "Changed:\n"
    for elem in diff.changed():
        changed = PrettyTable(["Key", "From", "To"])
        changed.align["key"] = "l"
        changed.padding_width = 1
        changed.align["From"] = "l"
        changed.align["To"] = "l"
        changed.add_row([elem, textwrap.fill(dict1[elem], 50),
                        textwrap.fill(dict2[elem], 50)])
    if changed is not None:
        result += str(changed)
        result += "\n"
    result += "\n"
    return result


def diff_other_meta(db_iface, proc_node1, proc_node2):
    result = "Differences in Resource limits, command line and user information:\n"
    other_meta_dict1 = convert_to_dict(get_meta_data(db_iface, proc_node1,
                                            storage.RelType.OTHER_META))
    other_meta_dict2 = convert_to_dict(get_meta_data(db_iface, proc_node2,
                                            storage.RelType.OTHER_META))
    result += print_diffs(other_meta_dict1, other_meta_dict2)
    return result


def diff_env_meta(db_iface, proc_node1, proc_node2):
    result = "Differences in Environment variables:\n"
    env_meta_dict1 = convert_to_dict(get_meta_data(db_iface, proc_node1,
                                            storage.RelType.ENV_META))
    env_meta_dict2 = convert_to_dict(get_meta_data(db_iface, proc_node2,
                                            storage.RelType.ENV_META))
    result += print_diffs(env_meta_dict1, env_meta_dict2)
    return result


def diff_lib_meta(db_iface, proc_node1, proc_node2):
    result = "Differences in libraries linked by program:\n"
    lib_meta_dict1 = convert_to_dict(get_meta_data(db_iface, proc_node1,
                                            storage.RelType.LIB_META))
    lib_meta_dict2 = convert_to_dict(get_meta_data(db_iface, proc_node2,
                                            storage.RelType.LIB_META))
    result += print_diffs(lib_meta_dict1, lib_meta_dict2)
    return result


@client_query.ClientQueryControl.register_query_method("get_execs")
def get_execs(db_iface, msg):
    rsp = cc_msg_pb2.ExecQueryMethodRsp()

    prog_name = None
    start_date = None
    end_date = None

    for arg in msg.args:
        if arg.key == "prog_name":
            prog_name = arg.value
        elif arg.key == "start_date":
            start_date = arg.value
        elif arg.key == "end_date":
            end_date = arg.value

    proc_list = get_proc_from_binary(db_iface, prog_name, start_date, end_date)
    if len(proc_list) == 0:
        rsp.error = "Could not find any execution instances" \
                    " for this binary and dates combination"
        return rsp
    elif len(proc_list) == 1:
        rsp.error = "Found only one execution instance"


    exec_id = 0
    exec_hist = PrettyTable(["ExecID", "Binary", "PID", "Date", "Command"])
    exec_hist.align["ExecID"] = "l"
    exec_hist.align["Binary"] = "l"
    exec_hist.align["Command"] = "l"
    for proc_node in proc_list:
        exec_id = exec_id + 1
        date_time = get_date_time_str(proc_node['sys_time'])

        cmd_line = ""
        other_meta_lst = get_meta_data(db_iface, proc_node,
                                storage.RelType.OTHER_META)
        for other_meta_node in other_meta_lst:
            if other_meta_node['name'] == "cmd_args":
                cmd_line = other_meta_node['value']
                exec_hist.add_row([exec_id, textwrap.fill(prog_name, 40),
                    proc_node['pid'], date_time, textwrap.fill(cmd_line, 40)])
                mapping = rsp.state_mapping.add()
                mapping.key = str(exec_id)
                mapping.value = str(proc_node.id)

    rsp.rsp_data = str(exec_hist)
    return rsp


@client_query.ClientQueryControl.register_query_method("get_diffs")
def get_diffs(db_iface, msg):
    '''Given two process node IDs, we can get the diffs between
    the environments of the process'''
    proc_node1 = None
    proc_node2 = None
    prog_name = None

    rsp = cc_msg_pb2.ExecQueryMethodRsp()

    for arg in msg.args:
        if arg.key == "node_id1":
            node_id1 = int(arg.value)
            proc_node1 = db_iface.db.node[node_id1]
        elif arg.key == "node_id2":
            node_id2 = int(arg.value)
            proc_node2 = db_iface.db.node[node_id2]
        elif arg.key == "prog_name":
            prog_name = arg.value

    if proc_node1 is None or proc_node2 is None:
        rsp.error = "Could not get process nodes"
        return rsp

    result = "\n"

    if prog_name is not None:
        result += "Modifications to binary \"%s\":\n" % (prog_name)
        prog_list = check_proc_bin_mod(db_iface, prog_name,
                                        proc_node1, proc_node2)
        mod_hist = PrettyTable(["Modified By", "Modified At"])
        mod_hist.align["Modified By"] = "l"
        for glob_node, bin_glob_node, cmd_args_node in prog_list:
            prog_bin_name = glob_node['name'][0]
            mod_program = bin_glob_node['name'][0]
            cmd_line = cmd_args_node['value']
            mod_hist.add_row([textwrap.fill(mod_program, 40),
                        get_date_time_str(glob_node['sys_time'])])
        result += str(mod_hist)
        result += "\n\n"

    result += diff_other_meta(db_iface, proc_node1, proc_node2)
    result += diff_env_meta(db_iface, proc_node1, proc_node2)
    result += diff_lib_meta(db_iface, proc_node1, proc_node2)

    rsp.rsp_data = result
    return rsp
