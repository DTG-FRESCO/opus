# -*- coding: utf-8 -*-
'''
PVM posix core package.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import logging
import cPickle as pickle

from ... import common_utils, pvm, storage, traversal, exception
from . import actions, utils


def create_proc(db_iface, pid, time_stamp):
    '''Create a process node with the given pid and timestamp.'''
    proc_node = db_iface.create_node(storage.NodeType.PROCESS)

    # Set properties on the process node
    proc_node['pid'] = pid
    proc_node['timestamp'] = time_stamp
    proc_node['status'] = storage.PROCESS_STATE.ALIVE

    # Cache the process node by its node_id property
    db_iface.cache_man.update(storage.CACHE_NAMES.NODE_BY_ID,
                            proc_node.id, proc_node)

    return proc_node


def expand_proc(db_iface, proc_node, pay, opus_lite):
    '''Expand a process node with a binary relation and with meta data
    from a given startup message payload 'pay'.'''
    time_stamp = proc_node['timestamp']
    proc_node['opus_lite'] = opus_lite

    loc_node = actions.touch_action(db_iface, proc_node, pay.exec_name)
    utils.set_link(db_iface, loc_node, storage.LinkState.BIN)

    if pay.HasField('cwd'):
        utils.add_meta_to_proc(db_iface, proc_node, "cwd", pay.cwd,
                               time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('cmd_line_args'):
        utils.add_meta_to_proc(db_iface, proc_node, "cmd_args",
                               pay.cmd_line_args, time_stamp,
                               storage.RelType.OTHER_META)

    if pay.HasField('user_name'):
        utils.add_meta_to_proc(db_iface, proc_node, "uid", pay.user_name,
                               time_stamp, storage.RelType.OTHER_META)

    if pay.HasField('group_name'):
        utils.add_meta_to_proc(db_iface, proc_node, "gid", pay.group_name,
                               time_stamp, storage.RelType.OTHER_META)

    for pair in pay.environment:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.ENV_META)

    for pair in pay.system_info:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.OTHER_META)

    for pair in pay.resource_limit:
        utils.add_meta_to_proc(db_iface, proc_node, pair.key, pair.value,
                               time_stamp, storage.RelType.OTHER_META)


def clone_file_des(db_iface, old_proc_node, new_proc_node):
    '''Clones the file descriptors of old_proc_node to new_proc_node
    using the CoT mechanism.'''
    loc_node_link_list = traversal.get_locals_from_process(db_iface,
                                                           old_proc_node)
    for (loc_node, rel_link) in loc_node_link_list:
        if rel_link['state'] in [storage.LinkState.CLOSED,
                                 storage.LinkState.CLOEXEC]:
            continue
        new_loc_node = pvm.get_l(db_iface, new_proc_node, loc_node['name'])

        if old_proc_node['status'] == storage.PROCESS_STATE.DEAD:
            loc_node = actions.close_action_helper(db_iface, loc_node)

        # Find the newest valid version of the global object
        glob_node = traversal.get_glob_latest_version(db_iface, loc_node)
        if glob_node is not None:
            # If in OPUS lite mode, copy over link state from parent
            old_state = None
            if old_proc_node.has_key('opus_lite') and old_proc_node['opus_lite']:
                glob_loc_rel = traversal.get_rel_to_dest(db_iface,
                                                glob_node.LOC_OBJ.outgoing,
                                                loc_node)
                if glob_loc_rel is not None:
                    old_state = glob_loc_rel['state']

            new_glob_node = pvm.version_global(db_iface, glob_node)
            pvm.bind(db_iface, new_loc_node, new_glob_node, old_state)



class ProcStateController(object):
    '''The ProcStateController handles process life cycles.'''
    proc_states = common_utils.enum(FORK=0,
                                    NORMAL=1,
                                    EXECED=2)

    proc_map = {}
    PIDMAP = {}
    pid_proc_nodes_map = {} # PID -> [proc_node.id list]

    @classmethod
    def proc_fork(cls, db_iface, p_node, pid, timestamp):
        '''Handle a process 'p_node' forking a child with pid 'pid' at time
        'timestamp'. Returns True if this is successful and False if this
        violates the state system.'''
        if pid not in cls.proc_map:
            cls.proc_map[pid] = cls.proc_states.FORK
            new_proc_node = create_proc(db_iface, pid, timestamp)
            cls.__add_proc_node(pid, new_proc_node)
            db_iface.create_relationship(new_proc_node, p_node,
                                         storage.RelType.PROC_PARENT)
            clone_file_des(db_iface, p_node, new_proc_node)
            cls.PIDMAP[pid] = new_proc_node.id
            return True
        else:
            logging.warning("Process %d received invalid request to fork while"
                            " already in the %s state.",
                            pid,
                            cls.proc_states.enum_str(cls.proc_map[pid]))
            return False

    @classmethod
    def __add_proc_node(cls, pid, proc_node):
        '''Maintains a list of process nodes for each pid'''
        if pid in cls.pid_proc_nodes_map:
            cls.pid_proc_nodes_map[pid].append(proc_node.id)
        else:
            cls.pid_proc_nodes_map[pid] = [proc_node.id]

    @classmethod
    def __is_forked_process(cls, pid):
        return (pid in cls.proc_map and
                cls.proc_map[pid] == cls.proc_states.FORK)

    @classmethod
    def __is_vforked_process(cls, cpid, ppid):
        return (cpid not in cls.proc_map and ppid in cls.proc_map)

    @classmethod
    def __handle_normal_process(cls, db_iface, hdr, pay, opus_lite):
        cls.proc_map[hdr.pid] = cls.proc_states.NORMAL

        proc_node = create_proc(db_iface, hdr.pid, hdr.timestamp)
        cls.__add_proc_node(hdr.pid, proc_node)
        expand_proc(db_iface, proc_node, pay, opus_lite)

        for i in range(3):
            pvm.get_l(db_iface, proc_node, str(i))
        cls.PIDMAP[hdr.pid] = proc_node.id

    @classmethod
    def __handle_forked_process(cls, db_iface, hdr, pay, opus_lite):
        cls.proc_map[hdr.pid] = cls.proc_states.NORMAL
        proc_node = db_iface.get_node_by_id(cls.PIDMAP[hdr.pid])
        expand_proc(db_iface, proc_node, pay, opus_lite)
        cls.PIDMAP[hdr.pid] = proc_node.id

    @classmethod
    def __handle_vforked_process(cls, db_iface, hdr, pay, opus_lite):
        cls.proc_map[hdr.pid] = cls.proc_states.NORMAL
        proc_node = create_proc(db_iface, hdr.pid, hdr.timestamp)
        cls.__add_proc_node(hdr.pid, proc_node)
        expand_proc(db_iface, proc_node, pay, opus_lite)

        parent_proc_node_id = cls.PIDMAP[pay.ppid]
        parent_proc_node = db_iface.get_node_by_id(parent_proc_node_id)
        db_iface.create_relationship(proc_node, parent_proc_node,
                                    storage.RelType.PROC_PARENT)
        clone_file_des(db_iface, parent_proc_node, proc_node)
        cls.PIDMAP[hdr.pid] = proc_node.id

    @classmethod
    def __handle_execed_process(cls, db_iface, hdr, pay, opus_lite):
        cls.proc_map[hdr.pid] = cls.proc_states.NORMAL
        proc_node = create_proc(db_iface, hdr.pid, hdr.timestamp)
        cls.__add_proc_node(hdr.pid, proc_node)
        expand_proc(db_iface, proc_node, pay, opus_lite)

        old_proc_node_id = cls.PIDMAP[hdr.pid]
        old_proc_node = db_iface.get_node_by_id(old_proc_node_id)

        # Set the old process node state to dead
        old_proc_node['status'] = storage.PROCESS_STATE.DEAD

        db_iface.create_relationship(proc_node, old_proc_node,
                                    storage.RelType.PROC_OBJ_PREV)
        clone_file_des(db_iface, old_proc_node, proc_node)
        cls.PIDMAP[hdr.pid] = proc_node.id

        # Clear the previous process object cache
        cls.__clear_process_cache(db_iface, old_proc_node)

        # Remove the previous process node from pid_proc_nodes_map
        if old_proc_node_id in cls.pid_proc_nodes_map[hdr.pid]:
            cls.pid_proc_nodes_map[hdr.pid].remove(old_proc_node_id)


    @classmethod
    def proc_startup(cls, db_iface, hdr, pay, opus_lite):
        '''Handles a process startup message arriving.'''

        if (hdr.pid not in cls.proc_map) and (pay.ppid not in cls.proc_map):
            cls.__handle_normal_process(db_iface, hdr, pay, opus_lite)
        else:
            if cls.__is_forked_process(hdr.pid):
                cls.__handle_forked_process(db_iface, hdr, pay, opus_lite)
            elif cls.__is_vforked_process(hdr.pid, pay.ppid):
                cls.__handle_vforked_process(db_iface, hdr, pay, opus_lite)
            else: # exec
                cls.__handle_execed_process(db_iface, hdr, pay, opus_lite)
        return True

    @classmethod
    def proc_exec(cls, pid):
        '''Handles a process with pid 'pid' executing an exec function.
        Returns True if this succeeds and returns False if this violates
        the state system.'''

        if pid in cls.proc_map:
            if cls.proc_map[pid] == cls.proc_states.NORMAL:
                cls.proc_map[pid] = cls.proc_states.EXECED
                return True
            else:
                logging.warning("Process %d received invalid request to "
                                "exec while already in the %s state.",
                                pid,
                                cls.proc_states.enum_str(cls.proc_map[pid]))
                return False
        else:
            logging.warning("Unknown process %d attempted to exec.",
                            pid)
            return False

    @classmethod
    def __clear_process_cache(cls, db_iface, proc_node):
        for tmp_rel in proc_node.PROC_OBJ.incoming:
            tmp_loc = tmp_rel.start

            # Invalidate all caches
            db_iface.cache_man.invalidate(
                storage.CACHE_NAMES.IO_EVENT_CHAIN,
                (proc_node.id, tmp_loc['name']))

            db_iface.cache_man.invalidate(
                storage.CACHE_NAMES.VALID_LOCAL,
                (proc_node.id, tmp_loc['name']))

            db_iface.cache_man.invalidate(
                storage.CACHE_NAMES.LOCAL_GLOBAL,
                tmp_loc.id)

            db_iface.cache_man.invalidate(
                storage.CACHE_NAMES.LAST_EVENT,
                tmp_loc.id)

            db_iface.cache_man.invalidate(
                storage.CACHE_NAMES.LAST_EVENT,
                proc_node.id)

        # Invalidate the NODE_BY_ID cache
        db_iface.cache_man.invalidate(
            storage.CACHE_NAMES.NODE_BY_ID,
            proc_node['node_id'])


    @classmethod
    def __clear_caches(cls, db_iface, pid):
        if pid not in cls.pid_proc_nodes_map:
            return

        for proc_node_id in cls.pid_proc_nodes_map[pid]:
            proc_node = db_iface.get_node_by_id(proc_node_id)
            cls.__clear_process_cache(db_iface, proc_node)
            proc_node['status'] = storage.PROCESS_STATE.DEAD


    @classmethod
    def __close_all_open_fds(cls, db_iface, pid):
        '''Closes all open file descriptors during process exit
        and applies the relevant PVM operations'''
        if pid not in cls.pid_proc_nodes_map:
            return

        for proc_node_id in cls.pid_proc_nodes_map[pid]:
            proc_node = db_iface.get_node_by_id(proc_node_id)
            if proc_node['status'] == storage.PROCESS_STATE.ALIVE:
                continue

            loc_node_link_list = traversal.get_locals_from_process(db_iface,
                                                                proc_node)
            for (loc_node, rel_link) in loc_node_link_list:
                if rel_link['state'] in [storage.LinkState.CLOSED,
                                        storage.LinkState.CLOEXEC]:
                    continue
                loc_node = actions.close_action_helper(db_iface, loc_node)


    @classmethod
    def proc_discon(cls, db_iface, pid):
        '''Handles a process with pid 'pid' disconnecting from the backend.
        Returns True unless the process is unknown to the system, in which
        case it returns False.'''

        if pid in cls.proc_map:
            if cls.proc_map[pid] == cls.proc_states.EXECED:
                cls.proc_map[pid] = cls.proc_states.NORMAL
                return True
            else:
                cls.__close_all_open_fds(db_iface, pid)
                cls.__clear_caches(db_iface, pid)
                del cls.pid_proc_nodes_map[pid]
                del cls.PIDMAP[pid]
                del cls.proc_map[pid]
        else:
            logging.warning("Unknown process %d disconnected.",
                            pid)
            return False

    @classmethod
    def resolve_process(cls, pid):
        '''Attempts to resolve an ID for a process with pid 'pid'. Logs an
        error and returns None in the event that the pid supplied is
        unknown.'''
        if pid in cls.PIDMAP:
            return cls.PIDMAP[pid]
        else:
            logging.error("Attempt to reffer to process %d which is not "
                          "present in the system.", pid)
            return None

    @classmethod
    def dump_state(cls, file_name):
        '''Writes all class data structures to file'''
        try:
            with open(file_name, "wb") as fh:
                pickle.dump(cls.proc_map, fh)
                pickle.dump(cls.PIDMAP, fh)
                pickle.dump(cls.pid_proc_nodes_map, fh)
        except IOError as exc:
            logging.error("Error: %d, Message: %s", exc.errno, exc.strerror)
            raise exception.OPUSException("OPUS file open error, %s", file_name)

    @classmethod
    def load_state(cls, file_name):
        '''Loads all class data structures from file'''
        if not os.path.isfile(file_name):
            return

        try:
            with open(file_name, "rb") as fh:
                cls.proc_map = pickle.load(fh)
                cls.PIDMAP = pickle.load(fh)
                cls.pid_proc_nodes_map = pickle.load(fh)
        except IOError as exc:
            logging.error("Error: %d, Message: %s", exc.errno, exc.strerror)
            raise exception.OPUSException("OPUS file open error, %s", file_name)

        os.unlink(file_name)


    @classmethod
    def clear(cls):
        '''Clears up the classes data structures.'''
        cls.PIDMAP = {}
        cls.proc_map = {}
