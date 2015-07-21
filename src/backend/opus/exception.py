# -*- coding: utf-8 -*-
'''
Exception Definitions
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


class OPUSException(Exception):
    '''Simple exception handling class'''
    def __init__(self, msg):
        '''Initialize message'''
        super(OPUSException, self).__init__()
        self.msg = msg

    def __str__(self):
        '''Return message'''
        return self.msg


class InvalidTagException(OPUSException):
    '''Exception class to handle invalid tags'''
    def __init__(self, tag):
        '''Set the message in the base class'''
        super(InvalidTagException, self).__init__("Invalid tag: %s" % tag)


class InvalidNodeTypeException(OPUSException):
    '''exception for Invalid node types.'''
    def __init__(self, node_type):
        super(InvalidNodeTypeException, self).__init__(
            "Error: Tried to assign an event to a node of type %d, "
            "expected Local or Process." % node_type)


class NoMatchingLocalError(OPUSException):
    '''Failed to find a local object matching the supplied name.'''
    def __init__(self, proc_node, name):
        super(NoMatchingLocalError, self).__init__(
            "Error: Failed to find local %s in process %d" % (name,
                                                              proc_node.id)
        )


class MissingMappingError(OPUSException):
    '''Failed to find a mapping for a given function.'''
    def __init__(self):
        super(MissingMappingError, self).__init__(
            "Error: Failed to find a function mapping."
        )


class CommandInterfaceStartupError(OPUSException):
    '''Exception indicating that the command interface has failed to
    initialise.'''
    def __init__(self, *args, **kwargs):
        super(CommandInterfaceStartupError, self).__init__(*args, **kwargs)


class InvalidConfigFileException(OPUSException):
    '''Error in the formatting or content of the systems config file.'''
    def __init__(self):
        super(InvalidConfigFileException, self).__init__(
            "Error: Failed to load config file."
        )


class UniqueIDException(OPUSException):
    '''Exception when unique ID cannot be generated'''
    def __init__(self):
        super(UniqueIDException, self).__init__(
            "Error: Unique ID generation error"
        )


class InvalidCacheException(OPUSException):
    '''Exception when unique ID cannot be generated'''
    def __init__(self, cache):
        super(InvalidCacheException, self).__init__(
            "Error: Attempted to access cache {0} but it did not "
            "exist.".format(cache)
        )


class InvalidQueryException(OPUSException):
    '''Exception when unique ID cannot be generated'''
    def __init__(self):
        super(InvalidQueryException, self).__init__(
            "Error: Invalid Query"
        )


class QueueClearingException(OPUSException):
    '''Exception raised when attempting to put an item into a queue that is
    being cleared.'''
    def __init__(self):
        super(QueueClearingException, self).__init__(
            "Cannot insert message, queue clearing."
        )


class BackendConnectionError(OPUSException):
    '''Exception class for a failure of a script to make communication with
    the backend.'''
    def __init__(self, msg):
        super(BackendConnectionError, self).__init__(msg)
