import dbus.service
import threading


class CommunicationManager(object):
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
    def __init__(self):
        self.max_log_size = 0
        self.rolling_log_limit = 0
        self.log_path = ""
        self.current_log = None
        self.session_index = SessionIndex()

    def __del__(self):
        pass

    def put(self):
        '''Put a message into the persistant log.'''
        pass

    def clear(self):
        '''Explicatly clear a log file.'''
        pass


class SessionIndex(object):
    def __init__(self):
        self.indexes_list = []
        self.index_file_name = ""

    def __del__(self):
        pass

    def get(self):
        '''Get a filename and position that corresponds to session number.'''
        pass

    def remove_file(self):
        '''Remove all entries for a specific filename.'''
        pass


class EventOrderer(object):
    def __init__(self):
        self.priority_queue = None
        self.window_size = 0

    def __del__(self):
        pass

    def push(self):
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


class Messageable():
    def __init__(self):
        super(Messageable, self).__init__()
        self.mailbox = None

    def put_msg(self):
        pass

    def get_msg(self):
        pass


class MessageableThread(threading.Thread, Messageable):
    def __init__(self):
        super(MessageableThread, self).__init__()
        pass


class ProducerThread(MessageableThread):
    def __init__(self):
        super(ProducerThread, self).__init__()
        self.comm_manager = CommunicationManager()
        self.persistant_log = PersistantLog()
        self.event_orderer = EventOrderer()  # TODO:Replace with common reference
        self.mailman = Mailman()

    def run(self):
        pass


class AnalyserThread(MessageableThread):
    def __init__(self):
        super(AnalyserThread, self).__init__()
        self.provenance_analyser = POSIXPVMAnalyser()
        self.event_orderer = EventOrderer()  # TODO:Replace with common reference
        self.mailman = Mailman()

    def run(self):
        pass


class DaemonManager(dbus.service.Object, Messageable):
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


class Mailman(object):
    address_map = {}

    def __init__(self):
        pass

    def register(self, identifier, obj):
        pass

    def send_msg(self, identifier, msg):
        pass


class EventMsg(object):
    def __init__(self):
        self.type = ""
        self.payload = None


class RequestMsg(EventMsg):
    def __init__(self):
        super(RequestMsg, self).__init__()
        pass


class ResponseMsg(EventMsg):
    def __init__(self):
        super(ResponseMsg, self).__init__()
        pass


