'''
This module contains the implementation of
various types of producer classes. It also
contains the implementation of the communication
classes the OPUS backend uses to receive provenance
data from connected clients.
'''

import os
import sys
import struct
import time
import threading
import socket
import select
import uds_msg_pb2
import common_utils
import analysis
from socket import SOL_SOCKET


def create_close_conn_obj(sock_fd):
    '''Returns objects to mark a client connection close'''
    return None, None


def get_credentials(client_fd):
    '''Reads the peer credentials from a UDS descriptor'''
    if not hasattr(get_credentials, "SO_PEERCRED"):
        get_credentials.SO_PEERCRED = 17
    credentials = client_fd.getsockopt(SOL_SOCKET, \
            get_credentials.SO_PEERCRED, struct.calcsize('3i'))
    pid, uid, gid = struct.unpack('3i', credentials)
    return pid, uid, gid


def receive(sock_fd, size):
    '''Received data for a given size from a socket'''
    buf = ''
    while size > 0:
        data = sock_fd.recv(size)
        if data == '':
            break
        buf += data
        size -= len(data)
    return buf


def read_data(sock_fd):
    '''Receives data from a socket object and
    returns a header and payload pair in bytes'''
    # Read the header
    hdr_buf = receive(sock_fd, common_utils.header_size())
    if hdr_buf == '':
        return None, None

    header = uds_msg_pb2.Header()
    header.ParseFromString(hdr_buf)
    print "Header:", header.__str__()

    # Get the payload size and type
    payload_size, payload = common_utils.get_payload_type(header)

    # Receive payload
    payload_buf = receive(sock_fd, payload_size)
    if payload_buf == '':
        return hdr_buf, None

    # Conversion to object only for debugging purposes
    payload.ParseFromString(payload_buf)
    print "Payload:", payload.__str__()

    return hdr_buf, payload_buf


def check_mailbox():
    '''Check for local messages'''
    pass


def unlink(path):
    '''Remove UDS link'''
    if(os.path.exists(path)):
        os.unlink(path)


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
    def __init__(self, path, max_conn=10, timeout=5.0):
        '''Initialize the class members'''
        super(UDSCommunicationManager, self).__init__()
        unlink(path)
        self.input_fds = []
        self.uds_path = path # Configurable
        self.max_server_conn = max_conn # Configurable
        self.select_timeout = timeout # Configurable
        self.server_socket = None

        try:
            self.server_socket = \
                    socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.server_socket.bind(self.uds_path)
            self.server_socket.listen(self.max_server_conn)
        except socket.error as (err, msg):
            if self.server_socket:
                self.server_socket.close()
            print "Error:", err, "Message:", msg
            sys.exit(1)
        self.server_socket.setblocking(0) # Make the socket non-blocking
        self.input_fds = [self.server_socket]

    def do_poll(self):
        '''Returns a list of tuples for all ready file descriptors'''
        ret_list = [] # List of tuples of form (header, payload)

        try:
            input_ready, output_ready, except_ready = \
                select.select(self.input_fds, [], [], self.select_timeout)
        except (select.error, socket.error) as (err, msg):
            print "Error:", err, "Message:", msg
            return ret_list

        if not input_ready:
            print "select timed out"
            return ret_list

        for sock_fd in input_ready:
            if sock_fd == self.server_socket:
                client_fd, address = self.server_socket.accept()
                pid, uid, gid = get_credentials(client_fd)
                print 'Got a new connection from pid: \
                    %d, uid: %d, gid: %d' % (pid, uid, gid)
                client_fd.setblocking(0) # Make the socket non-blocking
                self.input_fds.append(client_fd) # Add it to the input fd list
            else:
                header, payload = read_data(sock_fd)
                if header or payload:
                    print "Got data"
                    ret_list.append((header, payload))
                else:
                    header, payload = create_close_conn_obj(sock_fd)
                    print 'closing socket:', sock_fd.fileno()
                    if sock_fd in self.input_fds:
                        self.input_fds.remove(sock_fd)
                    sock_fd.close()
        return ret_list

    def close(self):
        '''Close all connections and cleanup'''
        self.server_socket.close()
        for sock_fd in self.input_fds:
            sock_fd.close()
        unlink(self.uds_path)


class Producer(threading.Thread):
    '''Base class for the producer thread'''
    def __init__(self):
        '''Initialize class data members'''
        super(Producer, self).__init__()
        self.analyser = None
        self.stop_event = threading.Event()

    def run(self):
        '''Override in the derived class'''
        pass

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        self.analyser.do_shutdown()
        print "Shutting down thread...."
        self.stop_event.set()


class SocketProducer(Producer):
    '''Implementation of a socket producer class'''
    def __init__(self, analyser_obj, comm_type):
        '''Initialize the class data members'''
        super(SocketProducer, self).__init__()
        self.comm_type = comm_type
        #TODO: Change this to get from meta_factory
        self.comm_manager = UDSCommunicationManager("./demo_socket", 5)
        self.analyser = analyser_obj

    def run(self):
        '''Spin until thread stop event is set'''
        while not self.stop_event.isSet():
            msg_list = self.comm_manager.do_poll()
            if not msg_list:
                print "No message to be logged"
            else:
                print "Calling put_msg on analyser"
                self.analyser.put_msg(msg_list)
            check_mailbox()
        self.comm_manager.close()

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        super(SocketProducer, self).do_shutdown()
        #self.comm_manager.close()

# Uncomment for testing purposes
#if __name__ == "__main__":
#    analyser_object = analysis.LoggingAnalyser("prov_log.dat")
#    producer_object = SocketProducer(analyser_object, "UDSCommunicationManager")
#    producer_object.start()
#    time.sleep(20)
#    producer_object.do_shutdown()
#    producer_object.join()
#    print "Exiting master thread"
