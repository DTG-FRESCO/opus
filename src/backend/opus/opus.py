import dbus.service


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


class PVCAnalyser(object):
    def __init__(self):
        self.storage_interface = StorageIFace()

    def __del__(self):
        pass

    def process(self):
        pass

    def get_l(self):
        pass

    def get_g(self):
        pass

    def drop_l(self):
        pass

    def drop_g(self):
        pass

    def bind(self):
        pass

    def unbind(self):
        pass

    def eadd(self):
        pass

    def erem(self):
        pass


class POSIXPVCAnalyser(PVCAnalyser):
    def __init__(self):
        super(self, POSIXPVCAnalyser).__init__()


class StorageIFace(object):
    def __init__(self):
        self.leveldb_connection = None

    def __del__(self):
        pass


class DaemonManager(dbus.service.Object):
    def __init__(self):
        self.config = None
        self.producer = None
        self.analyser = None
        self.producer_msg = None
        self.analyser_msg = None
        self.event_orderer = EventOrderer()

    def __del__(self):
        pass

    def do_thread_one(self):
        pass

    def do_thread_two(self):
        pass

    def do_dbus_msg(self):
        pass
