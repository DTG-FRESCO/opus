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
    def __init__(self):
        self.storage_interface = StorageIFace()

    def __del__(self):
        pass

    def process(self):
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
    def __init__(self):
        super(self, POSIXPVMAnalyser).__init__()


class StorageIFace(object):
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


class ProducerThread(threading.Thread):
    '''The producer thread handles the interactions between the communication
    manager, persistant log and the event orderer.'''
    def __init__(self):
        super(ProducerThread, self).__init__()
        self.comm_manager = CommunicationManager()
        self.persistant_log = PersistantLog()
        self.event_orderer = EventOrderer()  # TODO:Replace with argument
        self.mailman = Mailman()

    def run(self):
        pass


class AnalyserThread(threading.Thread):
    '''The analyser thread handles the interaction between the provenance
    analyser and the event orderer.'''
    def __init__(self):
        super(AnalyserThread, self).__init__()
        self.provenance_analyser = POSIXPVMAnalyser()
        self.event_orderer = EventOrderer()  # TODO:Replace with argument
        self.mailman = Mailman()

    def run(self):
        pass


class DaemonManager(dbus.service.Object):
    def __init__(self):
        self.config = None
        self.mailman = Mailman()

    def __del__(self):
        pass

    def dbus_change_config(self):
        pass

    def dbus_stop_service(self):
        pass

    def check_messages(self):
        pass


class Mailbox():
    def __init__(self, size):
        super(Mailbox, self).__init__()
        self.mailbox = None

    def put_msg(self, msg):
        '''Place the given message into the internal mailbox.'''
        pass

    def get_msg(self, timeout=0):
        '''Return the oldest message in the mailbox.'''
        pass


class Mailman(object):
    address_map = {}

    def __init__(self, identity):
        self.ident = identity
        self.req_mailbox = Mailbox()
        self.rsp_mailbox = Mailbox()
        self.rsp_tag = None
        self.rsp_lock = None

    def send(self, identifier, msg):
        '''Send msg to identifier, then wait for a response message. When the
        response if received return it. Optionally time out after the given
        period of time.'''
        pass

    def check_for_msg(self):
        '''Check the request mailbox for new messages. If there is a new
        message return it, otherwise return None.'''
        pass

    def reply(self, identifier, msg):
        '''Send a reply message to identifier.'''
        pass


class EventMsg(object):
    def __init__(self):
        self.type = ""
        self.payload = None
        self.source = None
        self.rsp_tag = None