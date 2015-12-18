# -*- coding: utf-8 -*-
'''
PVM core operations implementations.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

from .. import storage, traversal, common_utils

def cache_new_local(db_iface, loc_node, proc_node, loc_proc_rel):
    '''Updates the IO_EVENT_CHAIN and VALID_LOCAL
    cache with the new local'''
    if proc_node['status'] == storage.PROCESS_STATE.DEAD:
        return

    # Update VALID_LOCAL cache
    db_iface.cache_man.update(storage.CACHE_NAMES.VALID_LOCAL,
                                (proc_node.id, loc_node['name']),
                                (loc_node, loc_proc_rel))


    # Update IO_EVENT_CHAIN cache
    idx_list = db_iface.cache_man.get(storage.CACHE_NAMES.IO_EVENT_CHAIN,
                                        (proc_node.id, loc_node['name']))
    if idx_list is None:
        idx_list = common_utils.IndexList(lambda x: int(x.local['mono_time']))

    fd_chain = storage.FdChain()
    fd_chain.local = loc_node
    idx_list.append(fd_chain)
    db_iface.cache_man.update(storage.CACHE_NAMES.IO_EVENT_CHAIN,
                    (proc_node.id, loc_node['name']), idx_list)


def version_local(db_iface, old_loc_node, glob_node, glob_loc_rel):
    '''Versions the local object identified by loc_node and associates the
    new local object version with the global object identified by glob_node'''
    # Create a new local object node
    new_loc_node = db_iface.create_node(storage.NodeType.LOCAL)

    # Create link from global obj to new local obj
    new_glob_loc_rel = db_iface.create_relationship(glob_node, new_loc_node,
                                                storage.RelType.LOC_OBJ)

    # Copy over the local name and ref_count
    new_loc_node['name'] = old_loc_node['name']
    new_loc_node['ref_count'] = old_loc_node['ref_count']

    # Create link from new local object to previous local object
    db_iface.create_relationship(new_loc_node, old_loc_node,
                                 storage.RelType.LOC_OBJ_PREV)

    # Get process and link from old local
    proc_node, rel_link = traversal.get_process_from_local(db_iface,
                                                           old_loc_node)

    # Copy over state from previous global->local link if mode is OPUS lite
    if (proc_node.has_key('opus_lite') and proc_node['opus_lite']
        and glob_loc_rel.has_key('state')):
        new_glob_loc_rel['state'] = glob_loc_rel['state']

    # Create link from local to process
    new_rel = db_iface.create_relationship(new_loc_node, proc_node,
                                 storage.RelType.PROC_OBJ)

    db_iface.cache_man.invalidate(storage.CACHE_NAMES.VALID_LOCAL,
                                  (proc_node.id, old_loc_node['name']))

    # Add the new local object node to the IO_EVENT_CHAIN cache
    cache_new_local(db_iface, new_loc_node, proc_node, new_rel)

    # Change local->process link status to INACTIVE
    rel_link['state'] = storage.LinkState.INACTIVE

    return new_loc_node


def version_global(db_iface, old_glob_node):
    '''Versions the global object identified by old_glob_node.'''
    new_glob_node = db_iface.create_node(storage.NodeType.GLOBAL)

    if old_glob_node.has_key('name'):
        # Copy over name list from previous old global object
        name_list = old_glob_node['name']
        new_glob_node['name'] = list(name_list)
        for name in name_list:
            # Update file index
            db_iface.update_index(storage.DBInterface.FILE_INDEX,
                                  'name', name, new_glob_node)
        # Update time index
        db_iface.update_time_index(storage.DBInterface.FILE_INDEX,
                                   new_glob_node['sys_time'],
                                   new_glob_node)

    if old_glob_node.has_key('githash'):
        new_glob_node['githash'] = old_glob_node['githash']

    db_iface.create_relationship(new_glob_node, old_glob_node,
                                 storage.RelType.GLOB_OBJ_PREV)

    # Create new versions of all local objects associated with
    # the old global object and link them to the new global object
    loc_node_link_list = traversal.get_locals_from_global(db_iface,
                                                          old_glob_node)
    for (loc_node, glob_loc_rel) in loc_node_link_list:
        version_local(db_iface, loc_node, new_glob_node, glob_loc_rel)

    return new_glob_node

def get_l(db_iface, proc_node, loc_name):
    '''Performs a PVM get on the local object named 'loc_name' of the process
    identified by proc_node.'''

    # Invalidate the VALID_LOCAL cache
    db_iface.cache_man.invalidate(storage.CACHE_NAMES.VALID_LOCAL,
                                  (proc_node.id, loc_name))

    loc_node = db_iface.create_node(storage.NodeType.LOCAL)
    loc_node['name'] = loc_name

    # Create a relation from local--->process node
    loc_proc_rel = db_iface.create_relationship(loc_node, proc_node,
                                 storage.RelType.PROC_OBJ)

    # Add the new local object node to the IO_EVENT_CHAIN cache
    cache_new_local(db_iface, loc_node, proc_node, loc_proc_rel)

    return loc_node


def get_g(db_iface, loc_node, glob_name, githash=None):
    '''Performs a PVM get on the global object identified by glob_name and
    binds it to loc_node.'''

    old_glob_node = traversal.get_latest_glob_version(db_iface, glob_name)
    new_glob_node = None

    if old_glob_node is None:
        new_glob_node = db_iface.create_node(storage.NodeType.GLOBAL)

        # Add name as type array property
        new_glob_node['name'] = [glob_name]

        # Update file index
        db_iface.update_index(storage.DBInterface.FILE_INDEX,
                              'name', glob_name, new_glob_node)

        # Update time index
        db_iface.update_time_index(storage.DBInterface.FILE_INDEX,
                                   new_glob_node['sys_time'],
                                   new_glob_node)
    else:
        new_glob_node = version_global(db_iface, old_glob_node)

    if githash is not None:
        new_glob_node['githash'] = githash

    bind(db_iface, loc_node, new_glob_node)
    return new_glob_node


def drop_l(db_iface, loc_node):
    '''PVM drop on loc_node.'''
    # Set the link between the local object and
    # process object to LinkState.CLOSED
    proc_node, rel_link = traversal.get_process_from_local(db_iface, loc_node)
    rel_link['state'] = storage.LinkState.CLOSED

    db_iface.cache_man.invalidate(storage.CACHE_NAMES.VALID_LOCAL,
                                  (proc_node.id, loc_node['name']))


def drop_g(db_iface, loc_node, glob_node, githash=None):
    '''PVM drop on glob_node and disassociated fron loc_node.'''
    new_glob_node = version_global(db_iface, glob_node)
    if githash is not None:
        new_glob_node['githash'] = githash

    new_loc_node = traversal.get_next_local_version(db_iface, loc_node)
    unbind(db_iface, new_loc_node, new_glob_node)
    return new_glob_node, new_loc_node


def bind(db_iface, loc_node, glob_node, link_state=None):
    '''PVM bind between loc_node and glob_node.'''
    db_iface.create_relationship(glob_node, loc_node,
                                 storage.RelType.LOC_OBJ, link_state)
    db_iface.cache_man.invalidate(storage.CACHE_NAMES.LOCAL_GLOBAL,
                                  loc_node.id)
    ref_count = 0
    if glob_node.has_key('name'):
        ref_count = len(glob_node['name'])
    loc_node['ref_count'] = ref_count


def unbind(db_iface, loc_node, glob_node):
    '''PVM unbind between loc_node and glob_node.'''
    db_iface.find_and_del_rel(glob_node, loc_node)
    loc_node['ref_count'] = 0

    db_iface.cache_man.invalidate(storage.CACHE_NAMES.LOCAL_GLOBAL,
                                  loc_node.id)
