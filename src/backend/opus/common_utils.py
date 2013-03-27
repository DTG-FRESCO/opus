'''
Contains common classes and functions that can
be used by multiple modules in the OPUS backend
'''
import copy
import threading
import functools
import uds_msg_pb2


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


class FixedDict(object):
    '''Ensures keys are fixed in the dictionary'''
    def __init__(self, dictionary):
        '''Take a copy of the dictionary'''
        super(FixedDict, self).__init__()
        self._dictionary = copy.deepcopy(dictionary)
    def __setitem__(self, key, item):
        '''Sets a value for a valid key'''
        if key not in self._dictionary:
            raise KeyError("The key {} is not defined.".format(key))
        self._dictionary[key] = item
    def __getitem__(self, key):
        '''Returns the value for a valid key'''
        if key not in self._dictionary:
            raise KeyError("The key {} is not defined.".format(key))
        return self._dictionary[key]

def meta_factory(base, tag, *args, **kwargs):
    '''Return an instance of the class 
    derived from base with the name "tag"'''
    def compute_subs(cls):
        '''Compute the transitive colsure of
        the subclass relation on the given class'''
        sub_classes = [cls]
        for sub_class in cls.__subclasses__():
            sub_classes += compute_subs(sub_class)
        return sub_classes

    sub_classes = compute_subs(base)
    for sub_class in sub_classes:
        if sub_class.__name__ == tag:
            return sub_class(*args, **kwargs)
    raise InvalidTagException(tag)

def enum(**enums):
    '''Returns an enum class object'''
    return type('Enum', (), enums)


def analyser_lock(func):
    '''Decorator method for accessing analyser object'''
    if not hasattr(analyser_lock, "mutex"):
        analyser_lock.mutex = threading.Lock()
    @functools.wraps(func)
    def deco(self, *args, **kwargs):
        '''Wraps function call with lock acquire and release'''
        with analyser_lock.mutex:
            return func(self, *args, **kwargs)
    return deco


def header_size():
    '''Creates a header object and returns the object size'''
    if hasattr(header_size, "size"):
        return header_size.size
    header = uds_msg_pb2.Header()
    header.timestamp = 0
    header.pid = 0
    header.start_msg_len = 0
    header.lib_msg_len = 0
    header.func_msg_len = 0
    header_size.size = header.ByteSize()
    return header_size.size


def get_payload_type(header):
    '''Returns the paylod size and appropriate payload object'''
    if header.start_msg_len > 0:
        return header.start_msg_len, uds_msg_pb2.StartupMessage()
    if header.lib_msg_len > 0:
        return header.lib_msg_len, uds_msg_pb2.LibInfoMessage()
    if header.func_msg_len > 0:
        return header.func_msg_len, uds_msg_pb2.FuncInfoMessage()
