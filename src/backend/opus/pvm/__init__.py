# -*- coding: utf-8 -*-
'''
PVM core operations implementations.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


from opus import prov_db_pb2 as prov_db
from opus import storage


def version_local(storage_iface, old_loc_node, glob_node):
    '''Versions the local object identified by loc_node and associates the
    new local object version with the global object identified by glob_node'''
    # Create a new local object node
    new_loc_node = storage_iface.create_node(storage.NodeType.LOCAL)

    # Create link from global obj to new local obj
    glob_to_loc_rel = storage_iface.create_relationship(glob_node,
                                    new_loc_node, storage.RelType.LOC_OBJ)
    # NOTE: Should we copy over state (nb466)?

    # Copy over the local name and ref_count
    new_loc_node['name'] = old_loc_node['name']
    new_loc_node['ref_count'] = old_loc_node['ref_count']

    # Create link from new local object to previous local object
    storage_iface.create_relationship(new_loc_node, old_loc_node,
                                    storage.RelType.LOC_OBJ_PREV)

    # Create link from local object to process object
    proc_node, rel_link = storage_iface.get_process_from_local(old_loc_node)
    storage_iface.create_relationship(new_loc_node, proc_node,
                                    storage.RelType.PROC_OBJ)

    # Delete the previous link from local to process
    storage_iface.delete_relationship(rel_link)

    return new_loc_node


def version_global(storage_iface, old_glob_node):
    '''Versions the global object identified by old_glob_node.'''
    new_glob_node = storage_iface.create_node(storage.NodeType.GLOBAL)

    # Copy over name list from previous old global object
    name_list = old_glob_node['name']
    new_glob_node['name'] = list(name_list)
    for name in name_list:
        # Update file index
        storage_iface.update_index(storage.Neo4JInterface.FILE_INDEX,
                                    'name', name, new_glob_node)
        # Update time index
        storage_iface.update_time_index(storage.Neo4JInterface.FILE_INDEX,
                                        new_glob_node['sys_time'],
                                        new_glob_node)

    storage_iface.create_relationship(new_glob_node, old_glob_node,
                                    storage.RelType.GLOB_OBJ_PREV)

    # Create new versions of all local objects associated with
    # the old global object and link them to the new global object
    loc_node_link_list = storage_iface.get_locals_from_global(old_glob_node)
    for (loc_node, rel_link) in loc_node_link_list:
        new_loc_node = version_local(storage_iface, loc_node, new_glob_node)

    return new_glob_node


def get_l(storage_iface, proc_node, loc_name):
    '''Performs a PVM get on the local object named 'loc_name' of the process
    identified by proc_node.'''
    loc_node = storage_iface.create_node(storage.NodeType.LOCAL)
    loc_node['name'] = loc_name

    # Create a relation from local--->process node
    storage_iface.create_relationship(loc_node, proc_node,
                                    storage.RelType.PROC_OBJ)
    return loc_node


def get_g(storage_iface, loc_node, glob_name):
    '''Performs a PVM get on the global object identified by glob_name and
    binds it to loc_node.'''

    old_glob_node = storage_iface.get_latest_glob_version(glob_name)
    new_glob_node = None

    if old_glob_node is None:
        new_glob_node = storage_iface.create_node(storage.NodeType.GLOBAL)

        # Add name as type array property
        new_glob_node['name'] = [glob_name]

        # Update file index
        storage_iface.update_index(storage.Neo4JInterface.FILE_INDEX,
                                    'name', glob_name, new_glob_node)

        # Update time index
        storage_iface.update_time_index(storage.Neo4JInterface.FILE_INDEX,
                                        new_glob_node['sys_time'],
                                        new_glob_node)
    else:
        new_glob_node = version_global(storage_iface, old_glob_node)

    bind(storage_iface, loc_node, new_glob_node)
    return new_glob_node


def drop_l(storage_iface, loc_node):
    '''PVM drop on loc_node.'''
    # Set the link between the local object and
    # process object to LinkState.CLOSED
    proc_node, rel_link = storage_iface.get_process_from_local(loc_node)
    rel_link['state'] = storage.LinkState.CLOSED


def drop_g(storage_iface, loc_node, glob_node):
    '''PVM drop on glob_node and disassociated fron loc_node.'''
    new_glob_node = version_global(storage_iface, glob_node)
    new_loc_node = storage_iface.get_next_local_version(loc_node)
    unbind(storage_iface, new_loc_node, new_glob_node)
    return new_glob_node, new_loc_node


def bind(storage_iface, loc_node, glob_node):
    '''PVM bind between loc_node and glob_node.'''
    storage_iface.create_relationship(glob_node, loc_node,
                                storage.RelType.LOC_OBJ)
    name_list = glob_node['name']
    loc_node['ref_count'] = len(name_list)


def unbind(storage_iface, loc_node, glob_node):
    '''PVM unbind between loc_node and glob_node.'''
    storage_iface.find_and_del_rel(glob_node, loc_node,
                                storage.RelType.LOC_OBJ)
    loc_node['ref_count'] = 0
