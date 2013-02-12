import dbus.service
import threading


def meta_factory(base, tag):
    '''Return an instance of the class derived from base with the name "tag"'''
    pass


class CommunicationManager(object):
    '''A communication manager binds a UDS socket, then accepts connections and
    messages from the socket producing lists of messages for the rest of the
    system.'''
    def __init__(self):
        super(CommunicationManager, self).__init__()
        self.fd_set = []
        self.sock_fd = None
        self.select_timeout = 0

    def close(self):
        '''Close the comms manager, closing the listening socket and any
        active connections.'''
        pass

    def do_poll(self):
        '''Select over the fd_set, accept any new connections and return a list
        of any messages received.'''
        pass


class UDSCommunicationManager(CommunicationManager):
    '''Setup UDS specific connection in the init method'''
    def __init__(self):
        super(UDSCommunicationManager, self).__init__()


class TCPCommunicationManager(CommunicationManager):
    '''Setup TCP specific connection in the init method'''
    def __init__(self):
        super(TCPCommunicationManager, self).__init__()
        pass


class PersistantQueue(object):
    def __init__(self):
        super(PersistantQueue, self).__init__()


class Relay(object):
    def __init__(self):
        super(Relay, self).__init__()


class PVMAnalyser(object):
    '''The PVM analyser class implements the core of the PVM model, including
    the significant operations and their interactions with the underlying
    storage system.'''
    def __init__(self):
        super(PVMAnalyser, self).__init__()
        self.storage_interface = StorageIFace()

    def close(self):
        '''Close the storage interface.'''
        pass

    def process(self):
        '''Process a single front end message, applying it's effects to the
        database.'''
        pass

    def pvm_get_l(self):
        pass

    def pvm_get_g(self):
        pass

    def pvm_drop_l(self):
        pass

    def pvm_drop_g(self):
        pass

    def pvm_bind(self):
        pass

    def pvm_unbind(self):
        pass

    def pvm_eadd(self):
        pass

    def pvm_erem(self):
        pass


class POSIXPVMAnalyser(PVMAnalyser):
    '''The POSIX PVM analyser implements the operations of the POSIX system in
    terms of the PVM calls that are inherited from it's parent class.'''
    def __init__(self):
        super(POSIXPVMAnalyser, self).__init__()

    def process(self):
        pass


class StorageIFace(object):
    '''A storage interface instance allows for access to a provenance database
    collection using a series of operations. It encapsulates the type of
    database and it's method of access.'''
    def __init__(self):
        super(StorageIFace, self).__init__()
        self.obj_db = None
        self.time_index = None
        self.name_index = None

    def close(self):
        '''Close all active database connections.'''
        pass

    def put(self, db_id, obj):
        '''Insert obj into the database with key db_id.'''
        pass

    def create(self, obj_type):
        '''Create an object of type obj_type in the database, return a tuple
        of the object and its id.'''
        pass

    def get(self, db_id):
        '''Return the object matching the given db_id.'''
        pass

    def get_id_list_from_name(self, ename):
        '''Return the list of db_ids that match the given entity name in the
        index.'''
        pass

    def get_id_list_from_time_range(self, start, finish):
        '''Return a list of all db_ids within the given time range.'''
        pass


class Producer(threading.Thread):
    def __init__(self):
        super(Producer, self).__init__()
        self.analyser = Analyser()  # TODO: Gift from constructor.

    def run(self):
        pass

    def do_shutdown(self):
        '''Shutdown the thread gracefully.'''
        pass


class SocketProducer(Producer):
    def __init__(self):
        super(SocketProducer, self).__init__()
        self.comms_manager = CommunicationManager()


class BatchProducer(Producer):
    def __init__(self):
        super(BatchProducer, self).__init__()
        self.persistant_queue = PersistantQueue()


class Analyser(threading.Thread):
    def __init__(self):
        super(Analyser, self).__init__()

    def run(self):
        pass

    def do_shutdown(self):
        '''Shutdown the thread gracefully.'''
        pass


class LoggingAnalyser(Analyser):
    def __init__(self):
        super(LoggingAnalyser, self).__init__()
        self.persistant_queue = PersistantQueue()


class ProcessingAnalyser(Analyser):
    def __init__(self):
        super(ProcessingAnalyser, self).__init__()
        self.persistant_queue = PersistantQueue()
        self.pvm_analyser = PVMAnalyser()

class RelayingAnalyser(Analyser):
    def __init__(self):
        super(RelayingAnalyser, self).__init__()
        self.persistanht_queue = PersistantQueue()
        self.relay = Relay()

class DaemonManager(dbus.service.Object):
    '''The daemon manager is created to launch the back-end. It creates and
    starts the two working threads then listens for commands via DBUS.'''
    def __init__(self):
        dbus.service.Object.__init__(self)
        self.config = None
        self.producer = Producer()
        self.analyser = Analyser()

    def dbus_start_analyser(self):
        '''Handle a dbus message signalling for an analyser start.'''
        pass

    def dbus_stop_analyser(self):
        '''Handle a sbud message signalling for an analyser stop.'''
        pass

    def dbus_is_analyser_on(self):
        '''Return the status of the analyser thread.'''
        pass

    def dbus_stop_service(self):
        '''Cause the daemon to shutdown gracefully.'''
        pass

