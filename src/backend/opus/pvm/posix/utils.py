# -*- coding: utf-8 -*-
'''
Various utility methods that support the actions and functions of the PVM posix
analyser implementation.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import functools
import logging


from opus import prov_db_pb2 as prov_db
from opus import pvm, storage, common_utils


class PVMException(common_utils.OPUSException):
    '''Base exception for PVM related failures.'''
    def __init__(self, msg):
        super(PVMException, self).__init__(msg)


class NoMatchingLocalError(PVMException):
    '''Failed to find a local object matching the supplied name.'''
    def __init__(self, p_id, name):
        super(NoMatchingLocalError, self).__init__(
            "Error: Failed to find local %s in process %d" % (name, p_id)
        )


def parse_kvpair_list(args):
    '''Converts a list of KVPair messages to a dictionary.'''
    return {arg.key: arg.value for arg in args}


def check_message_error_num(func):
    '''Check the error_num of the message passed and if it is a fail add an
    event to the process object then abort. Otherwise process as ususal.'''
    @functools.wraps(func)
    def wrapper(tran, p_id, msg, *args, **kwargs):
        '''Should never be seen.'''
        if msg.error_num > 0:
            return p_id
        return func(tran, p_id, msg, *args, **kwargs)
    return wrapper


def process_from_startup(tran, (hdr, pay)):
    '''Given a hdr, pay pair for a startup message create a process object.'''
    (p_id, p_obj) = tran.create(prov_db.PROCESS)
    p_obj.pid = hdr.pid
    time_stamp = hdr.timestamp

    if pay.HasField('cwd'):
        cwd_id = new_meta(tran, "cwd", pay.cwd, time_stamp)
        p_obj.other_meta.add().id = cwd_id

    if pay.HasField('user_name'):
        uid_id = new_meta(tran, "uid", pay.user_name, time_stamp)
        p_obj.other_meta.add().id = uid_id

    if pay.HasField('group_name'):
        gid_id = new_meta(tran, "gid", pay.group_name, time_stamp)
        p_obj.other_meta.add().id = gid_id

    for pair in pay.environment:
        env_id = new_meta(tran, pair.key, pair.value, time_stamp)
        p_obj.env.add().id = env_id

    for pair in pay.system_info:
        sys_id = new_meta(tran, pair.key, pair.value, time_stamp)
        p_obj.other_meta.add().id = sys_id

    for pair in pay.resource_limit:
        res_id = new_meta(tran, pair.key, pair.value, time_stamp)
        p_obj.other_meta.add().id = res_id

    return p_id


def clone_file_des(tran, old_p_id, new_p_id):
    '''Clones the file descriptors of old_p_id to new_p_id using the CoT
    mechanism.'''
    new_p_obj = tran.get(new_p_id)
    old_p_obj = tran.get(old_p_id)
    for lnk in old_p_obj.local_object:
        if lnk.state == prov_db.CLOSED:
            continue
        new_lnk = new_p_obj.local_object.add()
        new_lnk.id = lnk.id
        new_lnk.state = prov_db.CoT


def new_meta(tran, name, val, time_stamp):
    '''Create a new meta object with the given name, value and timestamp.'''
    (m_id, m_obj) = tran.create(prov_db.META)
    m_obj.name = name
    if val is not None:
        m_obj.value = val
    m_obj.timestamp = time_stamp
    return m_id


def event_from_msg(tran, msg):
    '''Create an event object from the given function info message.'''
    (eo_id, eo_obj) = tran.create(prov_db.EVENT)
    eo_obj.fn = msg.func_name
    eo_obj.ret = msg.ret_val
    for obj in msg.args:
        add = eo_obj.additional.add()
        add.key = obj.key
        add.value = obj.value
    eo_obj.before_time = msg.begin_time
    eo_obj.after_time = msg.end_time
    return eo_id


def trace_latest_global_version(tran, g_id):
    '''From the object g_id trace through decendant relations avoiding
    deletions to find the newest version of the object that has not been
    deleted. Assumes that all global objects have either a single child that
    may be deleted or two children only one of which can be deleted.'''
    g_obj = tran.get(g_id)
    # If a g_id has no children then it must be the last.
    while len(g_obj.next_version) != 0:
        if len(g_obj.next_version) == 1:  # Single Child Case
            if g_obj.next_version[0].state == prov_db.DELETED:
                # If the child is deleted then the current g_id is the last.
                break
            else:
                # Otherwise make the child the current g_id and repeat.
                g_id = g_obj.next_version[0].id
                g_obj = tran.get(g_id)
        else:  # Double Child Case
            for lnk in g_obj.next_version:
                if lnk.state != prov_db.DELETED:
                    g_id = lnk.id
                    g_obj = tran.get(g_id)
                    break
    return g_id


def proc_get_local(tran, p_id, loc_name):
    '''Retrieves the local object that corrisponds with a given name from a
    process.'''
    p_obj = tran.get(p_id)
    for i in range(len(p_obj.local_object)):
        if p_obj.local_object[i].state == prov_db.CLOSED:
            # Ignore closed local objects.
            continue
        l_id = p_obj.local_object[i].id
        l_obj = tran.get(l_id)
        if l_obj.name == loc_name:  # Found local object with matching name.
            if p_obj.local_object[i].state == prov_db.CoT:
                # If the object is Copy on Touch
                del p_obj.local_object[i]
                new_l_id = pvm.get_l(tran, p_id, l_obj.name)
                if len(l_obj.file_object) > 0:
                    if len(l_obj.file_object) == 1:
                        g_id = trace_latest_global_version(tran,
                                                        l_obj.file_object[0].id
                                                           )
                        new_g_id = pvm.version_global(tran, g_id)
                        pvm.bind(tran, new_l_id, new_g_id)
                    else:
                        logging.error(
                            "Tracing latest global of invalid local."
                        )
                return new_l_id
            else:
                return l_id
    raise NoMatchingLocalError(p_id, loc_name)


def ins_local(tran, ev_id, l_id):
    '''Inserts an event ev_id into local object l_id.'''
    ev_obj = tran.get(ev_id)
    l_obj = tran.get(l_id)
    ev_obj.prev.id = l_obj.io_events.id
    l_obj.io_events.id = ev_id


def ins_proc(tran, ev_id, p_id):
    '''Inserts an event ev_id into process object p_id.'''
    ev_obj = tran.get(ev_id)
    p_obj = tran.get(p_id)
    ev_obj.prev.id = p_obj.process_events.id
    p_obj.process_events.id = ev_id


def update_proc_meta(tran, p_id, meta_name, new_val, timestamp):
    '''Updates the meta object meta_name for the process p_id with a new value
    and timestamp. Adds a new object if an existing one cannot be found.'''
    m_id = new_meta(tran, meta_name, new_val, timestamp)
    m_obj = tran.get(m_id)
    p_obj = tran.get(p_id)
    for meta in p_obj.other_meta:
        old_m_id = meta.id
        old_m_obj = tran.get(old_m_id)
        if old_m_obj.name == meta_name:
            # Object found and link updated.
            m_obj.prev_version.id = old_m_id
            meta.id = m_id
            return
    # Object not found, adding new object.
    p_obj.other_meta.add().id = m_id


def add_event(tran, o_id, msg):
    '''Adds an event to an object identified by o_id, automatically deriving
    the object type.'''
    ev_id = event_from_msg(tran, msg)
    o_type = storage.derv_type(o_id)
    if o_type == prov_db.LOCAL:
        ins_local(tran, ev_id, o_id)
    elif o_type == prov_db.PROCESS:
        ins_proc(tran, ev_id, o_id)


def proc_dup_fd(tran, p_id, fd_i, fd_o):
    '''Helper for duplicating file descriptors. Handles closing the old
    descriptor if needed and binding it to the new identifier.'''
    if fd_i == fd_o:
        return
    i_id = proc_get_local(tran, p_id, fd_i)
    o_id = proc_get_local(tran, p_id, fd_o)
    i_obj = tran.get(i_id)
    if o_id is not None:
        o_obj = tran.get(o_id)
        if len(o_obj.file_object) > 0:
            if len(o_obj.file_object) > 1:
                logging.error("Duping invalid local.")
            else:
                g_id = o_obj.file_object[0].id
                pvm.drop_g(tran, o_id, g_id)
                new_o_id = o_obj.next_version.id
                pvm.drop_l(tran, new_o_id)
        else:
            pvm.drop_l(tran, o_id)
    o_id = pvm.get_l(tran, p_id, fd_o)
    o_obj = tran.get(o_id)
    if len(i_obj.file_object) == 1:
        new_g_id = pvm.version_global(tran, i_obj.file_object[0].id)
        pvm.bind(tran, o_id, new_g_id)


def process_put_env(tran, p_id, env, overwrite):
    '''Helper for edit processes environment, attempts to put name, val, ts
    into the processes environment. Clears keys if val is None, only overwrites
    existing keys if overwrite is set and inserts if the key is not found and
    val is not None.'''
    p_obj = tran.get(p_id)
    found = False
    (name, val, time_stamp) = env
    for meta in p_obj.env:
        old_m_id = meta.id
        old_m_obj = tran.get(old_m_id)
        if old_m_obj.name == name:
            found = True
            if not overwrite:
                break
            m_id = new_meta(tran, name, val, time_stamp)
            m_obj = tran.get(m_id)
            m_obj.prev_version.id = old_m_id
            meta.id = m_id
    if not found and val is not None:
        m_id = new_meta(tran, name, val, time_stamp)
        m_obj = tran.get(m_id)
        p_obj.env.add().id = m_id


def set_rw_lnk(tran, l_id, state):
    '''Sets the link between l_id and the global it is connected to. The link
    is set to either state or the appropriate combination(if the link is
    already READ trying to set it to WRITE will result in RaW).'''
    l_obj = tran.get(l_id)
    if len(l_obj.file_object) == 1:
        g_id = l_obj.file_object[0].id
        g_obj = tran.get(g_id)
        if((state == prov_db.READ and
            l_obj.file_object[0].state == prov_db.WRITE) or
           (state == prov_db.WRITE and
            l_obj.file_object[0].state == prov_db.READ) or
           l_obj.file_object[0].state == prov_db.RaW):
            new_state = prov_db.RaW
        else:
            new_state = state

        l_obj.file_object[0].state = new_state
        for lnk in g_obj.process_object:
            if lnk.id == l_id:
                lnk.state = new_state
                break
