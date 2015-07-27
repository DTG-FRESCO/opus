#! /usr/bin/env python2.7
# -*- coding: utf-8 -*-
'''
Generates EPSRC report
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import sys
import datetime
import yaml
import jinja2
import webbrowser
import argparse
import shutil
import tempfile
from termcolor import colored

import workflow_helper as wfh

exec_list = []  # Contains list of executables
visited_list = []
# pid -> {read_files, write_files, read_write_files, executed_files}
pid_files_map = {}

src_code_extns = ['.py', '.c', '.cpp', '.C', '.sh', '.pl']
start_filters = ['/tmp/']
end_filters = ['.cls', '.aux', '.cache']

class FailedOpusPath(Exception):
    pass

class FileTypes(object):
    BINARY = "bin"
    SOURCECODDE = "source code"
    DATA = "data"


def check_filter(file_name):
    for f in start_filters:
        if file_name.startswith(f):
            return False
    for f in end_filters:
        if file_name.endswith(f):
            return False
    return True


def check_src_bin_data(f):
    global exec_list
    if f in exec_list or ".so" in f:
        return FileTypes.BINARY

    for ext in src_code_extns:
        if f.endswith(ext):
            return FileTypes.SOURCECODDE

    return FileTypes.DATA


def get_date_time_str(sys_time):
    return datetime.datetime.fromtimestamp(sys_time).strftime(
        '%Y-%m-%d %H:%M:%S')


def static_var(varname, value):
    def decorate(func):
        setattr(func, varname, value)
        return func
    return decorate


@static_var("counter", 0)
def get_next_key():
    get_next_key.counter += 1
    return get_next_key.counter


def copy_files(pid, proc_rec):
    if pid not in pid_files_map:
        return

    if len(pid_files_map[pid]['read_files']) > 0:
        proc_rec['read_files'].extend(pid_files_map[pid]['read_files'])
    if len(pid_files_map[pid]['write_files']) > 0:
        proc_rec['write_files'].extend(pid_files_map[pid]['write_files'])
    if len(pid_files_map[pid]['read_write_files']) > 0:
        proc_rec['read_write_files'].extend(
            pid_files_map[pid]['read_write_files'])
    if len(pid_files_map[pid]['executed_files']) > 0:
        proc_rec['executed_files'].extend(pid_files_map[pid]['executed_files'])


def filter_sys_meta(sys_meta_map):
    new_sys_meta_map = {}
    for name, value in sys_meta_map.iteritems():
        if name.startswith("RLIMIT_"):
            continue
        new_sys_meta_map[name] = value
    return new_sys_meta_map


def filter_env_meta(env_meta_map):
    new_env_meta_map = {}
    for name, value in env_meta_map.iteritems():
        if name.startswith("OPUS_"):
            continue
        new_env_meta_map[name] = value
    return new_env_meta_map


def get_children(level, node_id, proc_tree_map, yaml_map,
                 level_cmd, yaml_key=0, how_str=""):
    if node_id in visited_list:
        return
    visited_list.append(node_id)

    if len(proc_tree_map[node_id]['cmd_args']) > 0:
        cmd = proc_tree_map[node_id]['cmd_args']

        if level == 1:  # User initiated commands
            yaml_key = get_next_key()
            level_cmd = cmd

        date_time_str = get_date_time_str(
            proc_tree_map[node_id]['sys_time'])

        pid = proc_tree_map[node_id]['pid']
        copy_files(pid, proc_tree_map[node_id])

        produced_list = []
        if len(proc_tree_map[node_id]['write_files']) > 0:
            produced_list.extend(proc_tree_map[node_id]['write_files'])

        if len(proc_tree_map[node_id]['read_write_files']) > 0:
            produced_list.extend(
                proc_tree_map[node_id]['read_write_files'])

        produced_list = sorted(set(produced_list))

        used_list = []
        if len(proc_tree_map[node_id]['read_files']) > 0:
            used_list.extend(proc_tree_map[node_id]['read_files'])

        global exec_list
        if len(proc_tree_map[node_id]['executed_files']) > 0:
            exec_list.extend(proc_tree_map[node_id]['executed_files'])
            used_list.extend(proc_tree_map[node_id]['executed_files'])

        exec_list = sorted(set(exec_list))
        used_list = sorted(set(used_list))

        if yaml_key not in yaml_map:
            cwd = proc_tree_map[node_id]['cwd']

            sys_meta = filter_sys_meta(proc_tree_map[node_id]['sys_meta'])
            env_meta = filter_env_meta(proc_tree_map[node_id]['env_meta'])

            yaml_map[yaml_key] = {'when': date_time_str, 'cmd': level_cmd,
                                  'sys_meta': sys_meta,
                                  'env_meta': env_meta,
                                  'lib_meta': proc_tree_map[node_id]['lib_meta'],
                                  'used': used_list,
                                  'where': cwd,
                                  'produced': produced_list}
        else:
            yaml_map[yaml_key]['cmd'] = level_cmd

            ulist = yaml_map[yaml_key]['used']
            ulist.extend(list(set(used_list) - set(ulist)))

            plist = yaml_map[yaml_key]['produced']
            plist.extend(list(set(produced_list) - set(plist)))
    else:  # Forked process
        pid = proc_tree_map[node_id]['pid']
        if pid not in pid_files_map:
            pid_files_map[pid] = {'read_files': [], 'write_files': [],
                                  'read_write_files': [], 'executed_files': []}

        if len(proc_tree_map[node_id]['write_files']) > 0:
            pid_files_map[pid]['write_files'] = sorted(set(
                proc_tree_map[node_id]['write_files']))
        if len(proc_tree_map[node_id]['read_files']) > 0:
            pid_files_map[pid]['read_files'] = sorted(set(
                proc_tree_map[node_id]['read_files']))
        if len(proc_tree_map[node_id]['read_write_files']) > 0:
            pid_files_map[pid]['read_write_files'] = sorted(set(
                proc_tree_map[node_id]['read_write_files']))
        if len(proc_tree_map[node_id]['executed_files']) > 0:
            pid_files_map[pid]['executed_files'] = sorted(set(
                proc_tree_map[node_id]['executed_files']))

    # Recursively get data for children or execed processes
    if 'execed' in proc_tree_map[node_id]:
        el = proc_tree_map[node_id]['execed']
        el.sort()
        for ni in el:
            get_children(level, ni, proc_tree_map,
                         yaml_map, level_cmd, yaml_key)
    elif 'forked' in proc_tree_map[node_id]:
        fl = proc_tree_map[node_id]['forked']
        fl.sort()
        for ni in fl:
            get_children(level + 1, ni, proc_tree_map,
                         yaml_map, level_cmd, yaml_key)


def is_used_elsewhere(f, queried_file, used_file_map, cur_key):
    if f == queried_file:
        return True

    if f not in used_file_map:
        return False
    else:
        for key in used_file_map[f]:
            if key != cur_key:
                return True
    return False


def is_produced_elsewhere(f, produced_file_map, cur_key):
    if f not in produced_file_map:
        return False
    else:
        for key in produced_file_map[f]:
            if key != cur_key:
                return True
    return False


def gen_yaml_file(proc_tree_map, queried_file):
    yaml_map = {}  # command -> {when, where, how, used}
    level = 0
    level_cmd = ""
    for key in sorted(proc_tree_map):
        if key in visited_list:
            continue

        if 'forked' in proc_tree_map[key]:
            fl = proc_tree_map[key]['forked']
            fl.sort()
            date_time_str = get_date_time_str(
                proc_tree_map[key]['sys_time'])

            visited_list.append(key)
            for node_id in fl:
                get_children(level + 1, node_id, proc_tree_map,
                             yaml_map, level_cmd)

    used_file_map = {}  # file -> [list of keys]
    produced_file_map = {}  # file -> [list of keys]

    for key, rec in yaml_map.iteritems():
        for uf in rec['used']:
            if uf not in used_file_map:
                used_file_map[uf] = [key]
            else:
                used_file_map[uf].append(key)

        for pf in rec['produced']:
            if pf not in produced_file_map:
                produced_file_map[pf] = [key]
            else:
                produced_file_map[pf].append(key)

    rec_list_for_upload = []
    output = []

    for key in list(reversed(sorted(yaml_map.keys()))):
        rec = yaml_map[key]
        for f in rec['produced']:
            if not is_used_elsewhere(f, queried_file, used_file_map, key):
                continue

            rec_list_for_upload.append(f)

            output_elm = {"name": f,
                          "id": key,
                          "when": rec['when'],
                          "where": rec['where'],
                          "how": rec['cmd']}

            meta_type_list = ['sys_meta', 'env_meta', 'lib_meta']
            for meta_type in meta_type_list:
                if meta_type in rec:
                    output_elm[meta_type] = []
                    for tmp_key, tmp_val in rec[meta_type].iteritems():
                        output_elm[meta_type] += [{"name": tmp_key,
                                                   "value": tmp_val}]

            output_elm['used'] = []
            if len(rec['used']) != 0:
                dir_file_map = {}
                for uf in rec['used']:
                    if check_filter(uf) is False:
                        continue
                    group_common_dir(uf, dir_file_map)

                for dir in sorted(dir_file_map.keys()):
                    file_lst = dir_file_map[dir]
                    used_elm = {"dir": dir,
                                "files": []}
                    for filex in file_lst:
                        tag = check_src_bin_data(filex)
                        rec_list_for_upload.append(dir + "/" + filex)

                        file_elm = {'name': filex}
                        if is_produced_elsewhere((dir + "/" + filex),
                                                 produced_file_map, key):
                            file_elm['link'] = ""
                            file_elm['tag'] = tag
                        else:
                            file_elm['tag'] = tag
                        used_elm['files'] += [file_elm]
                    output_elm['used'] += [used_elm]
            output += [output_elm]
    return output, rec_list_for_upload


def group_common_dir(file_path, dir_file_map):
    tokens = file_path.split('/')
    fname = tokens.pop()
    dir = '/'.join(tokens)

    if dir in dir_file_map:
        dir_file_map[dir].append(fname)
    else:
        dir_file_map[dir] = [fname]



def add_file_to_map(file_map, first_key, f):
    tokens = f.split('/')
    fname = tokens.pop()
    dir = '/'.join(tokens)

    if dir in file_map[first_key]:
        file_map[first_key][dir].append(fname)
    else:
        file_map[first_key][dir] = [fname]


def package_code_data(rec_list_for_upload, files_data, dest_dir, cur_time):
    rec_list_for_upload = sorted(set(rec_list_for_upload))

    tmp_dir = tempfile.mkdtemp()
    code_dir = os.path.join(tmp_dir, "epsrc_pkg", "code")
    data_dir = os.path.join(tmp_dir, "epsrc_pkg", "data")
    os.makedirs(code_dir)
    os.makedirs(data_dir)

    epsrc_pkg = os.path.join(dest_dir, "epsrc_pkg." + cur_time)

    file_map = {'src_code': {}, 'data': {}}

    print("\nGenerating EPSRC archive")

    for f in rec_list_for_upload:
        if not os.path.isfile(f):
            print("Could not find file: %s" % (f))
            continue

        tag = check_src_bin_data(f)
        if tag == FileTypes.BINARY:
            print("Skipping binary: %s" % colored(f, 'green'))
            continue
        elif tag == FileTypes.SOURCECODDE:
            add_file_to_map(file_map, 'src_code', f)
            shutil.copy(f, code_dir)
        else:
            add_file_to_map(file_map, 'data', f)
            shutil.copy(f, data_dir)

    render_data = {"summary": {},
                   "files": files_data}
    for k in file_map.keys():
        render_data['summary'][k] = []
        for dir, dir_files in file_map[k].iteritems():
            render_data['summary'][k] += [{'dir': dir,
                                           'files': [f for f in dir_files]}]

    archive_file = shutil.make_archive(epsrc_pkg, 'gztar', tmp_dir)
    shutil.rmtree(tmp_dir)

    if not os.path.isfile(archive_file):
        print("Could not create EPSRC archive")
        return

    print("Successfully created EPSRC archive file %s" %
          colored(archive_file, 'red'))
    return render_data


def get_opus_scripts_dir():
    config_path = "~/.opus-cfg"
    if 'OPUS_MASTER_CONFIG' in os.environ:
        config_path = os.environ['OPUS_MASTER_CONFIG']
        config_path = os.path.abspath(os.path.expanduser(config_path))

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as cfg_file:
                cfg_file.readline().rstrip() # First line not needed
                cfg = yaml.load(cfg_file.read())
            opus_scripts_path = os.path.join(cfg['install_dir'], "src", "backend", "scripts")
            opus_scripts_path = os.path.abspath(os.path.expanduser(opus_scripts_path))
            return opus_scripts_path
        except [yaml.error.YAMLError, IOError]:
            raise FailedOpusPath()
    else:
        raise FailedOpusPath()


def main():
    parser = argparse.ArgumentParser(description="This program retrieves the" \
                    " workflow used to produce the queried file "
                    " and generates a report for the EPSRC open data compliance")

    args = wfh.parse_command_line(parser)
    proc_tree_map, queried_file = wfh.make_workflow_qry(args)
    cur_time = wfh.get_cur_time()

    if proc_tree_map is None:
        print("Could not retrieve process tree map")
        return

    print("Generating EPSRC report for %s" % colored(queried_file, 'green'))

    files_data, rec_list_for_upload = gen_yaml_file(proc_tree_map,
                                                    queried_file)
    render_data = package_code_data(rec_list_for_upload, files_data,
                                    args.dest, cur_time)

    try:
        opus_scripts_dir = get_opus_scripts_dir()
    except FailedOpusPath:
        print("Error: Could not find OPUS install path")
        return

    workflow_script_dir = os.path.join(opus_scripts_dir, "workflow")
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(workflow_script_dir))
    report_file_name = "epsrc_report." + cur_time + ".html"
    epsrc_report = os.path.join(args.dest, report_file_name)
    try:
        with open(epsrc_report, "wt") as epsrc_file:
            epsrc_tmpl = env.get_template("epsrc.tmpl")
            epsrc_file.write(epsrc_tmpl.render(file_list=render_data))
    except IOError as exc:
        print(exc)
        return

    print("\nEPSRC report %s generated successfully.\n" %
          colored(epsrc_report, 'green'))
    raw_input("Hit %s to open" % colored("Enter", 'red'))
    webbrowser.open_new(epsrc_report)

if __name__ == "__main__":
    main()
