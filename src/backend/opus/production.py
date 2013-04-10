'''
This module contains the implementation of
various types of producer classes. It also
contains the implementation of the communication
classes the OPUS backend uses to receive provenance
data from connected clients.
'''

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os
import struct
import errno
import threading
import socket
import select
import logging
import uds_msg_pb2
import common_utils

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

def stash_template():
    '''Returns a fixed dictionary template to stash messages'''
    if hasattr(stash_template, "stash_map"):
        return common_utils.FixedDict(stash_template.stash_map)
    stash_template.stash_map = {}
    stash_template.stash_map['header'] = None # Header in bytes
    stash_template.stash_map['header_object'] = None # Protobuf format
    stash_template.stash_map['payload_len'] = 0
    stash_template.stash_map['payload'] = None # Payload in bytes
    stash_template.stash_map['payload_object'] = None # Protobuf format
    return common_utils.FixedDict(stash_template.stash_map)

def reset_stash(stash_map):
    '''Resets the values for a given stash map'''
    stash_map['header'] = None
    stash_map['header_object'] = None
    stash_map['payload_len'] = 0
    stash_map['payload'] = None
    stash_map['payload_object'] = None


def create_close_conn_obj(sock_fd):
    '''Returns objects to mark a client connection close'''
    logging.debug("Creating close message for %d", sock_fd.fileno())
    return None, None


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
        self.input_fds = []
        self.uds_path = uds_path # Configurable
        self.max_server_conn = max_conn # Configurable
        self.select_timeout = select_timeout # Configurable
        self.server_socket = None
        self.msg_stash_map = {} # Map that holds a stash_info map per fd

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
        self.input_fds = [self.server_socket]

    def do_poll(self):
        '''Returns a list of tuples for all ready file descriptors'''
        ret_list = [] # List of tuples of form (header, payload)

        try:
            input_ready, _, _ = select.select(self.input_fds, [], [], 
                                                self.select_timeout)
        except (select.error, socket.error) as err:
            logging.error("Error: %s", str(err))
            return ret_list

        if not input_ready:
            logging.debug("select timed out")
            return ret_list

        for sock_fd in input_ready:
            if sock_fd == self.server_socket:
                self.__handle_new_connection()
            else:
                self.__handle_client(sock_fd, ret_list)

        return ret_list


    def __handle_client(self, sock_fd, ret_list):
        '''Receives data from client or closes the client connection'''
        status_code = self.__read_data(sock_fd)

        if status_code == UDSCommunicationManager.StatusCode.success:
            logging.debug("Got valid data")
            ret_list.append((self.msg_stash_map[sock_fd]['header'], 
                            self.msg_stash_map[sock_fd]['payload']))
            reset_stash(self.msg_stash_map[sock_fd])
        elif status_code == UDSCommunicationManager.StatusCode.close_connection:
            ret_list.append(tuple(create_close_conn_obj(sock_fd)))
            if sock_fd in self.input_fds:
                self.input_fds.remove(sock_fd)
            logging.debug('closing socket: %d', sock_fd.fileno())
            sock_fd.close()
            reset_stash(self.msg_stash_map[sock_fd])
        elif status_code == UDSCommunicationManager.StatusCode.try_again_later:
            logging.debug("Will try again later")

    def __handle_new_connection(self):
        '''Accepts and adds the new connection to the fd list'''
        client_fd, _ = self.server_socket.accept()
        pid, uid, gid = get_credentials(client_fd)
        logging.debug("Got a new connection from pid: %d, uid: %d, gid: %d",
                        pid, uid, gid)
        client_fd.setblocking(0) # Make the socket non-blocking
        self.input_fds.append(client_fd) # Add it to the input fd list
        self.msg_stash_map[client_fd] = stash_template()



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

    def __get_payload(self, sock_fd, stash_ref):
        '''Receives the payload and stashes it'''
        payload_buf, status_code = self.__receive(sock_fd, 
                                                stash_ref['payload_len'])
        if status_code != UDSCommunicationManager.StatusCode.success:
            return status_code

        payload = stash_ref['payload_object']
        payload.ParseFromString(payload_buf)
        logging.debug("Payload: %s", payload.__str__())
        stash_ref['payload'] = payload_buf
        stash_ref['payload_object'] = payload
        return status_code

    def __read_data(self, sock_fd):
        '''Receives data from a socket object and
        returns a header and payload pair in bytes'''
        stash_ref = self.msg_stash_map[sock_fd] # Take a ref

        # Read the header in not present
        if not stash_ref['header']:
            hdr_buf, status_code = self.__receive(sock_fd, 
                                        common_utils.header_size())
            if status_code != UDSCommunicationManager.StatusCode.success:
                return status_code
            stash_ref['header'] = hdr_buf
            header = uds_msg_pb2.Header()
            header.ParseFromString(hdr_buf)
            stash_ref['header_object'] = header
            logging.debug("Header: %s", header.__str__())

            # Find out the payload length and type
            payload_size, payload = common_utils.get_payload_type(header)
            stash_ref['payload_object'] = payload
            stash_ref['payload_len'] = payload_size
            return self.__get_payload(sock_fd, stash_ref)

        # We already have a header, now receive the payload
        return self.__get_payload(sock_fd, stash_ref)

    def close(self):
        '''Close all connections and cleanup'''
        self.server_socket.close()
        for sock_fd in self.input_fds:
            sock_fd.close()
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
        self.analyser.do_shutdown()
        logging.debug("Shutting down thread....")
        self.stop_event.set()


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

## Uncomment for testing purposes
#if __name__ == "__main__":
#    import sys
#    import time
#    import analysis
#    logging.basicConfig(format='%(asctime)s L%(lineno)d %(message)s', 
#                        datefmt='%m/%d/%Y %H:%M:%S', level=logging.DEBUG)
#    try:
#        args_to_analyser = {}
#        args_to_analyser["log_path"] = "prov_log.dat"
#        analyser_object = analysis.LoggingAnalyser(**(args_to_analyser))
#
#        socket_prod_args = {}
#        socket_prod_args["analyser_obj"] = analyser_object
#        socket_prod_args["comm_mgr_type"] = "UDSCommunicationManager"
#        socket_prod_args["comm_mgr_args"] = {"uds_path": "./demo_socket",
#                                             "max_conn": 50,
#                                             "select_timeout": 2}
#        producer_object = SocketProducer(**(socket_prod_args))
#    except common_utils.OPUSException as message:
#        logging.error(message)
#        sys.exit(1) # Depends on how the DaemonManager handles this
#    except TypeError as err:
#        logging.error(str(err))
#
#    producer_object.start()
#    time.sleep(20)
#    #new_analyser = analysis.DummyAnalyser()
#    #old_analyser = producer_object.switch_analyser(new_analyser)
#    #old_analyser.do_shutdown()
#    #time.sleep(10)
#    producer_object.do_shutdown()
#    producer_object.join()
#    logging.debug("Exiting master thread")
