# -*- coding: utf-8 -*-
'''
PVM core operations implementations.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


from opus import prov_db_pb2 as prov_db


def version_local(tran, old_l_id, f_id):
    '''Versions the local object identified by old_l_id and associated the new
    version with the global ID specified as f_id.'''
    new_l_id, new_l_obj = tran.create(prov_db.LOCAL)
    old_l_obj = tran.get(old_l_id)
    par_id = old_l_obj.process_object.id
    par_obj = tran.get(par_id)
    for loc in par_obj.local_object:
        if loc.id == old_l_id:
            loc.id = new_l_id
    new_l_obj.process_object.id = par_id
    new_l_obj.prev_version.id = old_l_id
    old_l_obj.next_version.id = new_l_id
    new_l_obj.name = old_l_obj.name
    for lnk in old_l_obj.file_object:
        new_lnk = new_l_obj.file_object.add()
        new_lnk.id = f_id
        #new_lnk.state = lnk.state  # TODO(tb403) Possibly questionable
    new_l_obj.ref_count = old_l_obj.ref_count
    return new_l_id


def version_global(tran, old_g_id):
    '''Versions the global object identified by old_g_id.'''
    (new_g_id, new_g_obj) = tran.create(prov_db.GLOBAL)
    old_g_obj = tran.get(old_g_id)
    for name in old_g_obj.name:
        new_g_obj.name.append(name)
        tran.name_put(name, new_g_id)
    old_g_obj.next_version.add().id = new_g_id
    new_g_obj.prev_version.add().id = old_g_id

    for loc in old_g_obj.process_object:
        new_l_id = version_local(tran, loc.id, new_g_id)
        new_g_obj.process_object.add().id = new_l_id

    return new_g_id


def _remove_where(rep_cont, attr, val):
    '''Removes all objects from rep_cont where attr matches val.'''
    to_remove = []
    for i in range(len(rep_cont)):
        if attr is not None:
            if getattr(rep_cont[i], attr) == val:
                to_remove += [i]
        else:
            if rep_cont[i] == val:
                to_remove += [i]

    to_remove.sort()

    for i in range(len(to_remove)):
        #The deletions are from lowest index to highest index.
        #The -i compensates for the shift in index due to previous deletions.
        del rep_cont[to_remove[i]-i]

    return len(to_remove)


def get_l(tran, p_id, loc_name):
    '''Performs a PVM get on the local object named 'loc_name' of the process
    identified by p_id.'''
    (l_id, l_obj) = tran.create(prov_db.LOCAL)
    p_obj = tran.get(p_id)
    l_obj.name = loc_name
    l_obj.process_object.id = p_id
    p_obj.local_object.add().id = l_id
    return l_id


def get_g(tran, l_id, glob_name):
    '''Performs a PVM get on the global object identified by glob_name and
    binds it to l_id.'''
    old_g_id = tran.name_get(glob_name)
    if old_g_id is None:
        (new_g_id, new_g_obj) = tran.create(prov_db.GLOBAL)
        new_g_obj.name.append(glob_name)
        tran.name_put(glob_name, new_g_id)
    else:
        new_g_id = version_global(tran, old_g_id)
    bind(tran, l_id, new_g_id)
    return new_g_id


def drop_l(tran, l_id):
    '''PVM drop on l_id.'''
    l_obj = tran.get(l_id)
    p_id = l_obj.process_object.id
    p_obj = tran.get(p_id)
    l_obj.process_object.state = prov_db.CLOSED
    for lnk in p_obj.local_object:
        if lnk.id == l_id:
            lnk.state = prov_db.CLOSED


def drop_g(tran, l_id, g_id):
    '''PVM drop on g_id and disassociated fron l_id.'''
    new_g_id = version_global(tran, g_id)
    l_obj = tran.get(l_id)
    new_l_id = l_obj.next_version.id
    unbind(tran, new_l_id, new_g_id)
    return new_g_id


def bind(tran, l_id, g_id):
    '''PVM bind between l_id and g_id.'''
    l_obj = tran.get(l_id)
    g_obj = tran.get(g_id)
    l_obj.file_object.add().id = g_id
    l_obj.ref_count = len(g_obj.name)
    g_obj.process_object.add().id = l_id


def unbind(tran, l_id, g_id):
    '''PVM unbind between l_id and g_id.'''
    l_obj = tran.get(l_id)
    g_obj = tran.get(g_id)
    _remove_where(l_obj.file_object, 'id', g_id)
    l_obj.ref_count = 0
    _remove_where(g_obj.process_object, 'id', l_id)
