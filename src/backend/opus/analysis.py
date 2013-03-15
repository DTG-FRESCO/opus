'''
This module performs the analysis of incoming
provenance data sent by the producer. Various
types of analysers have been defined in this file.
'''

import os
import sys
import threading

class Analyser(threading.Thread):
    '''Base class for the analyser'''
    def __init__(self):
        '''Initialize class members'''
        super(Analyser, self).__init__()
        self.stop_event = threading.Event()

    def run(self):
        '''Should be overridden in the derived class'''
        pass

    def put_msg(self, msg_data):
        '''Should be overridden in the derived class'''
        pass

    def do_shutdown(self):
        '''Shutdown the thread gracefully'''
        self.stop_event.set()


class LoggingAnalyser(Analyser):
    '''Implementation of a logging analyser'''
    def __init__(self, path):
        '''Initialize class members'''
        super(LoggingAnalyser, self).__init__()
        self.file_object = None
        self.logfile_path = path

        try:
            self.file_object = open(self.logfile_path, "ab+")
        except IOError as (err, msg):
            print "Error:", err, "Message:", msg
            sys.exit(1)
        print "Opened file", self.logfile_path


    def put_msg(self, msg_list):
        '''Takes a list of tuples (header, payload)
        and writes them to a file'''
        for msg in msg_list:
            if msg[0]: # Write header
                self.file_object.write(msg[0])
            if msg[1]: # Write payload
                self.file_object.write(msg[1])
        self.file_object.flush()

    def do_shutdown(self):
        '''Flush all pending writes to disk
        and close the file object'''
        os.fsync(self.file_object.fileno())
        self.file_object.close()
