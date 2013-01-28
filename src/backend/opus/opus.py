import dbus.service
import threading


class CommunicationManager(object):
    '''A communication manager binds a UDS socket, then accepts connections and
    messages from the socket producing lists of messages for the rest of the
    system.'''
    def __init__(self):
        self.fd_set = []
        self.uds_socket_path = ""
        self.socket_timeout = 0

    def __del__(self):
        pass

    def do_poll(self):
        '''Select over the fd_set, accept any new connections and return a list
        of any messages received.'''
        pass


class PersistantLog(object):
    '''A persistant log stores a stream of messages in a series of rolling
    files, it uses a SessionIndex to track sessions of messages in the output.
    Messages from the log can be retrieved using the get command.'''
    def __init__(self):
        self.max_log_size = 0
        self.rolling_log_limit = 0
        self.log_path = ""
        self.current_log = None
        self.session_index = SessionIndex()

    def __del__(self):
        pass

    def put(self, msg):
        '''Put a message into the persistant log.'''
        pass

    def get(self, start):
        '''Return all of the messages in the log since the given start time.'''
        pass

    def clear(self, file_name):
        '''Clear a log file.'''
        pass

    def clear_all(self):
        '''Clear all log files.'''
        pass


class SessionIndex(object):
    '''A session index stores a mapping between session number and the file
    name and file position the session starts at.'''
    def __init__(self):
        self.indexes_list = []
        self.index_file_name = ""

    def __del__(self):
        pass

    def get(self, session_number):
        '''Get a filename and position that corresponds to session number.'''
        pass

    def add(self, session_number, file_name, file_pos):
        '''Add a mapping of session number to file name and position.'''
        pass

    def remove_file(self, file_name):
        '''Remove all entries for a specific filename.'''
        pass


class EventOrderer(object):
    '''An event orderer accepts messages being placed into it and returns
    messages in timestamp order, with a window based delay to allow for
    message delays.'''
    def __init__(self):
        self.priority_queue = None
        self.window_size = 0

    def __del__(self):
        pass

    def push(self, msg):
        '''Push a new message onto the ordering queue.'''
        pass

    def pop(self):
        '''Pop a message from the ordering queue.'''
        pass

    def is_empty(self):
        '''Check if the ordering queue is empty.'''
        pass

    def clear(self):
        '''Clear the ordering queue.'''
        pass


class PVMAnalyser(object):
    '''The PVM analyser class implements the core of the PVM model, including 
    the significant operations and their interactions with the underlying 
    storage system.'''
    def __init__(self):
        self.storage_interface = StorageIFace()

    def __del__(self):
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


class StorageIFace(object):
    '''A storage interface instance allows for access to a provenance database
    collection using a series of operations. It encapsulates the type of 
    database and it's method of access.'''
    def __init__(self):
        self.obj_db = None
        self.index_db = None

    def __del__(self):
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


class Messageable(object):
    '''A messageable class is one that holds an internal mailbox and accepts
    messages being given to it to place in the mailbox. The class can then
    retrieve these messages at its leisure.'''
    def __init__(self):
        super(Messageable, self).__init__()
        self.mailbox = None

    def put_msg(self, msg):
        '''Place the given message into the internal mailbox.'''
        pass

    def get_msg(self):
        '''Return the oldest message in the mailbox.'''
        pass


class MessageableThread(threading.Thread, Messageable):
    '''A messageable thread is a thread that has the messageable
    interface mixed in.'''
    def __init__(self):
        threading.Thread.__init__(self)
        Messageable.__init__(self)


class ProducerThread(MessageableThread):
    '''The producer thread handles the interactions between the communication
    manager, persistant log and the event orderer. It is messageable to allow
    it to reveive commands.'''
    def __init__(self):
        super(ProducerThread, self).__init__()
        self.comm_manager = CommunicationManager()
        self.persistant_log = PersistantLog()
        self.event_orderer = EventOrderer()  # TODO:Replace with argument
        self.mailman = Mailman()

    def run(self):
        pass
    
    def do_shutdown(self):
        '''Shutdown the thread gracefully.'''
        pass
    
    def do_start_event_orderer(self):
        '''Start sending messages to the event orderer from a given message 
        id.'''
        pass
    
    def do_stop_event_orderer(self):
        '''Cease sending messages to the event orderer.'''
        pass


class AnalyserThread(MessageableThread):
    '''The analyser thread handles the interaction between the provenance
    analyser and the event orderer. It is messageable to allow it to
    receive commands.'''
    def __init__(self):
        super(AnalyserThread, self).__init__()
        self.provenance_analyser = POSIXPVMAnalyser()
        self.event_orderer = EventOrderer()  # TODO:Replace with argument
        self.mailman = Mailman()

    def run(self):
        pass
    
    def do_shutdown(self):
        '''Shutdown the thread gracefully.'''
        pass


class DaemonManager(dbus.service.Object, Messageable):
    '''The daemon manager is created to launch the back-end. It creates and
    starts the two working threads then listens for commands via DBUS.'''
    def __init__(self):
        dbus.service.Object.__init__(self)
        Messageable.__init__(self)
        self.config = None
        self.mailman = Mailman()
        self.event_orderer = EventOrderer()

    def __del__(self):
        pass

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

    def check_messages(self):
        '''Check the messages of the internal mailman and respond
        appropriatly.'''
        pass


class Mailman(object):
    '''A mailman allows messageable objects to communicate with each other by
    registering them under a given identifier then routing messages for them
    between the different identifiers.'''
    address_map = {}

    def __init__(self):
        pass

    def register(self, identifier, obj):
        '''Register the given object under the given identifier in the
        address_map.'''
        pass

    def send_msg(self, identifier, msg):
        '''Send a message to the given identifier.'''
        pass


class EventMsg(object):
    '''EventMsg objects encapsulate a message between two threads, allowing
    for identification of message type and source.'''
    def __init__(self):
        self.type = ""
        self.payload = None
        self.source = None

