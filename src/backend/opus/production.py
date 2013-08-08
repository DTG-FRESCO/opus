'''
This module contains the implementation of
various types of producer classes. It also
contains the implementation of the communication
classes the OPUS backend uses to receive provenance
data from connected clients.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)


import datetime
import errno
import logging
import os
import select
import socket
import struct
import threading
import time

from opus import (common_utils, uds_msg_pb2)


def unlink_uds_path(path):
    '''Remove UDS link'''
    if(os.path.exists(path)):
        os.unlink(path)

def get_credentials(client_fd):
    '''Reads the peer credentials from a UDS descriptor'''
    if not hasattr(get_credentials, "SO_PEERCRED"):
        get_credentials.SO_PEERCRED = 17
    credentials = client_fd.getsockopt (socket.SOL_SOCKET,
                                        get_credentials.SO_PEERCRED,
                                        struct.calcsize(str('3i')))
    pid, uid, gid = struct.unpack('3i', credentials)
    return pid, uid, gid

def mono_time_in_nanosecs():
    '''Returns a monotonic time if 
    available, else returns 0'''
    ret_time = 0

    if hasattr(time, 'clock_gettime'):
        try:
            ret_time = int(time.clock_gettime(time.CLOCK_MONOTONIC_RAW) * 1e+9)
        except OSError as (_errno, err_msg):
            logging.error("Error: %d, Message: %s", _errno, err_msg)

    return ret_time

def create_close_conn_obj(sock_fd):
    '''Returns objects to mark a client connection close'''
    logging.debug("Creating close message for %d", sock_fd.fileno())
    pid, _, _ = get_credentials(sock_fd)

    gen_msg = uds_msg_pb2.GenericMessage()
    gen_msg.msg_type = uds_msg_pb2.DISCON
    gen_msg.msg_desc = "Client socket: %d disconnected" % (sock_fd.fileno())
    gen_msg.sys_time = str(datetime.datetime.now())

    header = uds_msg_pb2.Header()
    header.timestamp = mono_time_in_nanosecs()
    header.pid = pid
    header.tid = pid  # We dont have the tid
    header.payload_type = uds_msg_pb2.GENERIC_MSG
    header.payload_len = gen_msg.ByteSize()

    return header.SerializeToString(), gen_msg.SerializeToString()

def check_mailbox():
    '''Check for local messages'''
    pass


class CommunicationManager(object):
    '''Base class for the communication manager class'''
    def __init__(self):
        '''Initialize data members'''
        super(CommunicationManager, self).__init__()

    def close(self):
        '''Override this in the derived class'''
        pass

    def do_poll(self):
        '''Override this in the derived class'''
        pass


class UDSCommunicationManager(CommunicationManager):
    '''UDS specific server implementation'''
    StatusCode = common_utils.enum(success=0, 
                                close_connection=100, 
                                try_again_later=101)

    def __init__(self, uds_path, max_conn=10, 
                select_timeout=5.0, *args, **kwargs):
        '''Initialize the class members'''
        super(UDSCommunicationManager, self).__init__(*args, **kwargs)
        unlink_uds_path(uds_path)
        self.input_client_map = {} # fileno to sock object map
        self.uds_path = uds_path # Configurable
        self.max_server_conn = max_conn # Configurable
        self.select_timeout = select_timeout # Configurable
        self.server_socket = None

        try:
            self.server_socket = socket.socket(socket.AF_UNIX, 
                                                socket.SOCK_STREAM)
            self.server_socket.bind(self.uds_path)
            self.server_socket.listen(self.max_server_conn)
        except socket.error as err:
            if self.server_socket:
                self.server_socket.close()
            logging.error("Error: %s", str(err))
            raise common_utils.OPUSException("socket error")
        self.server_socket.setblocking(0) # Make the socket non-blocking
        self.epoll = select.epoll()
        self.epoll.register(self.server_socket.fileno(),
                        select.EPOLLIN | select.EPOLLERR)

    def do_poll(self):
        '''Returns a list of tuples for all ready file descriptors'''
        ret_list = [] # List of tuples of form (header, payload)

        try:
            event_list = self.epoll.poll(self.select_timeout)
        except IOError as err:
            logging.error("Error: %s", str(err))
            return ret_list

        if not event_list:
            logging.debug("epoll timed out")
            return ret_list

        for fileno, event in event_list:
            if fileno == self.server_socket.fileno():
                self.__handle_new_connection()
            elif event & select.EPOLLIN:
                self.__handle_client(self.input_client_map[fileno], ret_list)
            elif event & select.EPOLLHUP:
                logging.debug("Got an EPOLLHUP event")
                self.__handle_close_connection(self.input_client_map[fileno],
                                                ret_list)
        return ret_list

    def __handle_client(self, sock_fd, ret_list):
        '''Receives data from client or closes the client connection'''
        status_code, header_buf, payload_buf = self.__read_data(sock_fd)

        if status_code == UDSCommunicationManager.StatusCode.success:
            logging.debug("Got valid data")
            ret_list += [(header_buf, payload_buf)]
        elif status_code == UDSCommunicationManager.StatusCode.close_connection:
            self.__handle_close_connection(sock_fd, ret_list)
        elif status_code == UDSCommunicationManager.StatusCode.try_again_later:
            logging.debug("Will try again later")

    def __handle_close_connection(self, sock_fd, ret_list):
        '''Handles close event or hang up event on the client socket'''
        self.epoll.unregister(sock_fd.fileno())
        ret_list.append(tuple(create_close_conn_obj(sock_fd)))
        if sock_fd in self.input_client_map:
            del self.input_client_map[sock_fd.fileno()]
        logging.debug('closing socket: %d', sock_fd.fileno())
        sock_fd.close()

    def __handle_new_connection(self):
        '''Accepts and adds the new connection to the fd list'''
        client_fd, _ = self.server_socket.accept()
        pid, uid, gid = get_credentials(client_fd)
        logging.debug("Got a new connection from pid: %d, uid: %d, gid: %d",
                        pid, uid, gid)
        client_fd.setblocking(0) # Make the socket non-blocking
        self.epoll.register(client_fd.fileno(),
                        select.EPOLLIN | select.EPOLLERR | select.EPOLLHUP)
        self.input_client_map[client_fd.fileno()] = client_fd

    def __receive(self, sock_fd, size):
        '''Receives data for a given size from a socket'''
        buf = b''
        status_code = UDSCommunicationManager.StatusCode.success
        while size > 0:
            try:
                data = sock_fd.recv(size)
                if data == b'':
                    status_code = \
                        UDSCommunicationManager.StatusCode.close_connection
                    break
            except socket.error as (err, msg):
                if err == errno.EAGAIN or err == errno.EWOULDBLOCK:
                    status_code = \
                        UDSCommunicationManager.StatusCode.try_again_later
                elif err == errno.EINTR:
                    logging.error("Error: %d, Message: %s", err, msg)
                    continue
                else:
                    logging.error("Error: %d, Message: %s", err, msg)
                    status_code = \
                        UDSCommunicationManager.StatusCode.close_connection
                break
            buf += data
            size -= len(data)
        return buf, status_code

    def __read_data(self, sock_fd):
        '''Receives data from a socket object and
        returns a header and payload pair in bytes'''

        # Read header data and obtain the payload len
        hdr_buf, status_code = self.__receive(sock_fd,
                                common_utils.header_size())
        if status_code != UDSCommunicationManager.StatusCode.success:
            return status_code, None, None
        header = uds_msg_pb2.Header()
        header.ParseFromString(hdr_buf)
        logging.debug("Header: %s", header.__str__())

        # Find out the payload length and type
        payload_buf, status_code = self.__receive(sock_fd, header.payload_len)
        if status_code != UDSCommunicationManager.StatusCode.success:
            return status_code, None, None

        # Deserialization only needed for debuggin during development
        if logging.getLogger('').isEnabledFor(logging.DEBUG):
            payload = common_utils.get_payload_type(header)
            payload.ParseFromString(payload_buf)
            logging.debug("Payload: %s", payload.__str__())
        return status_code, hdr_buf, payload_buf

    def close(self):
        '''Close all connections and cleanup'''
        self.epoll.unregister(self.server_socket.fileno())
        self.server_socket.close()
        for fileno in self.input_client_map:
            self.epoll.unregister(fileno)
            self.input_client_map[fileno].close()
        unlink_uds_path(self.uds_path)


class Producer(threading.Thread):
    '''Base class for the producer thread'''
    def __init__(self, analyser_obj):
        '''Initialize class data members'''
        super(Producer, self).__init__()
        self.analyser = analyser_obj
        self.stop_event = threading.Event()

    def run(self):
        '''Override in the derived class'''
        pass

    @common_utils.analyser_lock
    def _send_data_to_analyser(self, msg_list):
        '''Calls the analyser object method by obtaining a lock'''
        self.analyser.put_msg(msg_list)

    @common_utils.analyser_lock
    def switch_analyser(self, new_analyser):
        '''Takes a new analyser object and returns the old one'''
        old_analyser = self.analyser
        self.analyser = new_analyser
        return old_analyser

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        logging.debug("Shutting down thread....")
        self.stop_event.set()
        try:
            self.join(common_utils.THREAD_JOIN_SLACK)
        except RuntimeError as exc:
            logging.error("Failed to shutdown thread sucessfully.")
            logging.error(exc)
            return False
        return not self.isAlive()


class SocketProducer(Producer):
    '''Implementation of a socket producer class'''
    def __init__(self, comm_mgr_type, comm_mgr_args, *args, **kwargs):
        '''Initialize the class data members'''
        super(SocketProducer, self).__init__(*args, **kwargs)
        self.comm_mgr_type = comm_mgr_type

        try:
            self.comm_manager = common_utils.meta_factory(CommunicationManager, 
                                        self.comm_mgr_type, **comm_mgr_args)
        except common_utils.InvalidTagException as err_msg:
            raise common_utils.OPUSException(err_msg.msg)

    def run(self):
        '''Spin until thread stop event is set'''
        while not self.stop_event.isSet():
            msg_list = self.comm_manager.do_poll()
            if not msg_list:
                logging.debug("No message to be logged")
            else:
                logging.debug("Calling put_msg on analyser")
                self._send_data_to_analyser(msg_list)
            check_mailbox()
        self.comm_manager.close()

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        super(SocketProducer, self).do_shutdown()
