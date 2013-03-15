'''
Contains common functions that may be used
by multiple modules in the OPUS backend
'''

import uds_msg_pb2

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
