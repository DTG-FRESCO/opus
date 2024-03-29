#include "proc_utils.h"

#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <link.h>
#include <linux/un.h>
#include <string.h>
#include <sys/resource.h>
#include <sys/utsname.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <linux/limits.h>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <map>

#include "log.h"
#include "comm_client.h"
#include "messaging.h"
#include "signal_utils.h"
#include "common_enums.h"
#include "file_hash.h"
#include "sys_util.h"
#include "message_util.h"

#define STRINGIFY(value) #value

using std::pair;
using std::string;
using std::vector;

/** Thread local storage */
__thread bool ProcUtils::in_opus_flag = true;
__thread CommClient *ProcUtils::comm_obj = NULL;
__thread uint32_t ProcUtils::conn_ref_count = 0;
__thread FuncInfoMessage *ProcUtils::func_msg_obj = NULL;
__thread GenericMessage *ProcUtils::gen_msg_obj = NULL;
__thread FuncInfoMessage *ProcUtils::__alt_func_msg_ptr = NULL;
__thread GenericMessage *ProcUtils::__alt_gen_msg_ptr = NULL;
__thread AggrMsg *ProcUtils::aggr_msg_obj = NULL;

/** process ID */
pid_t ProcUtils::opus_pid = -1;

/** global interposition mode flag */
sig_atomic_t ProcUtils::opus_interpose_mode = OPUS::OPUSMode::OPUS_ON;

/** glibc function name to symbol map */
std::map<string, void*> *ProcUtils::libc_func_map = NULL;

/** Aggregation flag */
bool ProcUtils::aggr_on_flag = false;

/**
 * Callback function passed to dl_iterate_phdr.
 * Adds the loaded library to the passed vector.
 */
static int get_loaded_libs(struct dl_phdr_info *info,
                        size_t size, void *ret_vec)
{
    string lib_name;
    vector<pair<string, string> > *lib_vec =
                static_cast<vector<pair<string, string> > *>(ret_vec);

    if (info->dlpi_name)
        lib_name = info->dlpi_name;

    if (!lib_name.empty())
    {
        char *real_path = realpath(info->dlpi_name, NULL);
        if (!real_path)
        {
            LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                        SysUtil::get_error(errno).c_str());
            return -1;
        }

        string md5_sum;
        FileHash::get_md5_sum(real_path, &md5_sum);

        lib_vec->push_back(make_pair(real_path, md5_sum));
        free(real_path);
    }

    return 0;
}


/**
 * Splits a string of type key=value
 * using = as the delimiter and creates
 * an std::pair object.
 */
static bool split_key_values(const string& env_str,
                    pair<string, string>* kv_pair)
{
    int64_t pos = env_str.find_first_of("=");
    if (pos == (int64_t)string::npos)
        return false;

    kv_pair->first = env_str.substr(0, pos);
    kv_pair->second = env_str.substr(pos+1);

    return true;
}

/**
 * Retrieves the process resource limits and
 * populates the startup message with this data.
 */
static inline void set_rlimit_info(StartupMessage* start_msg)
{
    static pair<string, int> limits[] = {
                            { STRINGIFY(RLIMIT_AS), RLIMIT_AS },
                            { STRINGIFY(RLIMIT_CORE), RLIMIT_CORE },
                            { STRINGIFY(RLIMIT_CPU), RLIMIT_CPU },
                            { STRINGIFY(RLIMIT_DATA), RLIMIT_DATA },
                            { STRINGIFY(RLIMIT_FSIZE), RLIMIT_FSIZE },
                            { STRINGIFY(RLIMIT_LOCKS), RLIMIT_LOCKS },
                            { STRINGIFY(RLIMIT_FSIZE), RLIMIT_FSIZE },
                            { STRINGIFY(RLIMIT_LOCKS), RLIMIT_LOCKS },
                            { STRINGIFY(RLIMIT_MEMLOCK), RLIMIT_MEMLOCK },
                            { STRINGIFY(RLIMIT_MSGQUEUE), RLIMIT_MSGQUEUE },
                            { STRINGIFY(RLIMIT_NICE), RLIMIT_NICE },
                            { STRINGIFY(RLIMIT_NOFILE), RLIMIT_NOFILE },
                            { STRINGIFY(RLIMIT_NPROC), RLIMIT_NPROC },
                            { STRINGIFY(RLIMIT_RSS), RLIMIT_RSS },
                            { STRINGIFY(RLIMIT_RTPRIO), RLIMIT_RTPRIO },
                            { STRINGIFY(RLIMIT_RTTIME), RLIMIT_RTTIME },
                            { STRINGIFY(RLIMIT_SIGPENDING), RLIMIT_SIGPENDING },
                            { STRINGIFY(RLIMIT_STACK), RLIMIT_STACK }
                        };

    vector<pair<string, int> > limits_vec(limits,
                    limits + sizeof(limits) / sizeof(pair<string, int>));

    KVPair* res_limit;
    vector<pair<string, int> >::const_iterator citer;
    for (citer = limits_vec.begin(); citer != limits_vec.end(); ++citer)
    {
        struct rlimit rlim;
        if (getrlimit((*citer).second, &rlim) < 0)
        {
            LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                        SysUtil::get_error(errno).c_str());
            continue;
        }

        res_limit = start_msg->add_resource_limit();
        res_limit->set_key((*citer).first);
        res_limit->set_value(std::to_string(rlim.rlim_cur));
    }
}

/**
 * Retrieves the system information using uname
 * and populates the startup message with this data.
 */
static inline void set_system_info(StartupMessage* start_msg)
{
    struct utsname buf;

    if (uname(&buf) < 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    SysUtil::get_error(errno).c_str());
        return;
    }

    KVPair* sys_data;
    sys_data = start_msg->add_system_info();
    sys_data->set_key("sysname");
    sys_data->set_value(buf.sysname);

    sys_data = start_msg->add_system_info();
    sys_data->set_key("nodename");
    sys_data->set_value(buf.nodename);

    sys_data = start_msg->add_system_info();
    sys_data->set_key("release");
    sys_data->set_value(buf.release);

    sys_data = start_msg->add_system_info();
    sys_data->set_key("version");
    sys_data->set_value(buf.version);

    sys_data = start_msg->add_system_info();
    sys_data->set_key("machine");
    sys_data->set_value(buf.machine);
}

/**
 * Reads all the environment variables inherited
 * by the process and populates this infromation
 * as part of the process startup message.
 */
static inline void set_env_vars(StartupMessage* start_msg, char** envp)
{
    KVPair* env_args;

    char* env_str = NULL;
    while ((env_str = *envp) != NULL)
    {
        pair<string, string> kv_pair;

        if (!split_key_values(string(env_str), &kv_pair))
            continue;

        env_args = start_msg->add_environment();
        env_args->set_key(kv_pair.first);
        env_args->set_value(kv_pair.second);
        ++envp;
    }
}

/**
 * Reads the command line parameters passed to the process
 * binary and populates the startup message with this data.
 */
static inline void set_command_line(StartupMessage* start_msg,
                            const int argc, char** argv)
{
    string cmd_line_str;

    for (int i = 0; i < argc; i++)
    {
        if (i > 0)
        {
            cmd_line_str += " ";
            cmd_line_str +=  argv[i];
        }
        else
        {
            char can_path[PATH_MAX + 1] = "";
            cmd_line_str += SysUtil::canonicalise_path(argv[i], can_path);
        }
    }

    start_msg->set_cmd_line_args(cmd_line_str);
}

/**
 * Retrieves the value of LD_PRELOAD_PATH environment variable.
 */
void ProcUtils::get_preload_path(string* ld_preload_path)
{
    try
    {
        char* preload_path = SysUtil::get_env_val("LD_PRELOAD");

        LOG_MSG(LOG_DEBUG, "[%s:%d]: LD_PRELOAD path: %s\n",
                    __FILE__, __LINE__, preload_path);

        *ld_preload_path = preload_path;
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Returns current value for message aggregation flag
 */
bool ProcUtils::get_msg_aggr_flag()
{
    return aggr_on_flag;
}

/**
 * Sets the aggregation flag to the supplied value
 */
void ProcUtils::set_msg_aggr_flag(const bool flag)
{
    aggr_on_flag = flag;
}

/**
 * Reads message aggregation flag from environment
 * and stores the value within the ProcUtils class
 */
void ProcUtils::set_msg_aggr_flag()
{
    try
    {
        char *msg_aggr = SysUtil::get_env_val("OPUS_MSG_AGGR");
        if (msg_aggr) aggr_on_flag = true;
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Flushes aggregated messages to the backend
 */
bool ProcUtils::flush_buffered_data()
{
    if (!comm_obj) return false;

    if (!aggr_msg_obj) return false;
    return aggr_msg_obj->flush();
}

/**
 * Deletes the aggregated message pointer
 */
void ProcUtils::discard_aggr_msgs()
{
    if (aggr_msg_obj)
    {
        delete aggr_msg_obj;
        aggr_msg_obj = NULL;
    }
}



/**
 * Buffers FUNCINFO_MSG and sends the messages in a batch
 */
bool ProcUtils::buffer_and_send_data(const FuncInfoMessage& buf_func_info_msg)
{
    bool ret = true;
    if (!comm_obj) return false;

    if (!aggr_on_flag)
        return set_header_and_send(buf_func_info_msg,
                            PayloadType::FUNCINFO_MSG);

    try
    {
        if (!aggr_msg_obj) aggr_msg_obj = new AggrMsg();

        if (!aggr_msg_obj->add_msg(buf_func_info_msg))
            throw std::runtime_error("add_msg() failed!!");
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        disconnect(); // Close the socket with the OPUS backend
        interpose_off(e.what());
        ret = false;
    }

    return ret;
}

/**
 * Serializes the header and payload data
 * and sends this data to the OPUS backend.
 */
bool ProcUtils::serialise_and_send_data(const struct Header& header_obj,
                                        const Message& payload_obj)
{
    bool ret = true;

    if (!comm_obj) return false;

    char *buf = NULL;

    int hdr_size = sizeof(header_obj);
    int pay_size = header_obj.payload_len;
    int total_size = hdr_size + pay_size;

    try
    {
        buf = new char[total_size];

        /* Serialize the header data and store it */
        if (!memcpy(buf, &header_obj, hdr_size))
            throw std::runtime_error("Failed to serialise header");

        /* Serialize the payload data and store it */
        if (!payload_obj.SerializeToArray(buf + hdr_size, pay_size))
            throw std::runtime_error("Failed to serialise payload");

        if (!comm_obj->send_data(buf, total_size))
            throw std::runtime_error("Sending data failed");
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        disconnect(); // Close the socket with the OPUS backend
        interpose_off(e.what());
        ret = false;
    }

    delete[] buf;
    return ret;
}

/**
 * Sets a global flag which can be used to
 * indicate that a glibc call was made by
 * code within the OPUS front-end. This can
 * also be used to toggle off provenance
 * capture in the frontend.
 */
bool ProcUtils::inside_opus(const bool value)
{
    bool ret = in_opus_flag & value;

    if (value && in_opus_flag) return ret;

    in_opus_flag = value;
    return ret;
}

/**
 * Reads the UDS path from the environment
 */
void ProcUtils::get_uds_path(string* uds_path_str)
{
    try
    {
        char* uds_path = SysUtil::get_env_val("OPUS_UDS_PATH");
        if (strlen(uds_path) > UNIX_PATH_MAX)
        {
            string err_desc = "UDS path length exceeds max allowed value "
                                    + std::to_string(UNIX_PATH_MAX);
            throw std::runtime_error(err_desc);
        }

        *uds_path_str = uds_path;

        LOG_MSG(LOG_DEBUG, "[%s:%d]: OPUS UDS path: %s\n", __FILE__, __LINE__, uds_path);
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Reads the TCP address and port from the environment
 */
void ProcUtils::get_tcp_address(string* address, int* port)
{
    try
    {
        char* tcp_addr = SysUtil::get_env_val("OPUS_TCP_ADDRESS");
        char* tcp_port = SysUtil::get_env_val("OPUS_TCP_PORT");

        *address = tcp_addr;
        *port = std::stoi(tcp_port);

    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Sends a process startup message to the OPUS backend.
 * As part of the message, the following data is populated,
 *      - command line params
 *      - environment variables
 *      - system info
 *      - resource limits
 */
void ProcUtils::send_startup_message(const int argc, char** argv, char** envp)
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    incr_conn_ref_count();
    StartupMessage start_msg;

    char exe[1024] = "";

    if (readlink("/proc/self/exe", exe , sizeof(exe)) >= 0)
    {
        start_msg.set_exec_name(exe);
    }

    char *cwd = NULL;
    if ((cwd = getcwd(NULL, 0)) != NULL)
    {
        start_msg.set_cwd(cwd);
    }

    start_msg.set_cmd_line_args("");
    start_msg.set_user_name(SysUtil::get_user_name(getuid()));
    start_msg.set_group_name(SysUtil::get_group_name(getgid()));
    start_msg.set_ppid(getppid());
    start_msg.set_start_time(SysUtil::get_time());

    set_command_line(&start_msg, argc, argv);
    if (envp) set_env_vars(&start_msg, envp);

    set_system_info(&start_msg);
    set_rlimit_info(&start_msg);
    set_header_and_send(start_msg, PayloadType::STARTUP_MSG);
    free(cwd);
}

/**
 * Calls send_startup_message without command line params
 */
void ProcUtils::send_startup_message()
{
    ProcUtils::send_startup_message(0, NULL, NULL);
}

/**
 * Sends a message to the OPUS backend with the paths
 * and md5 sum of all libraries loaded by the process.
 */
void ProcUtils::send_libinfo_message(const vector<pair<string,
                                        string> >& lib_vec)
{
    LibInfoMessage lib_info_msg;
    KVPair *kv_args;

    vector<pair<string, string> >::const_iterator citer;
    for (citer = lib_vec.begin(); citer != lib_vec.end(); citer++)
    {
        const string& lib_path = (*citer).first;
        const string& md5_sum = (*citer).second;

        kv_args = lib_info_msg.add_library();
        kv_args->set_key(lib_path);
        kv_args->set_value(md5_sum);
    }

    set_header_and_send(lib_info_msg, PayloadType::LIBINFO_MSG);
}

/**
 * Invokes callback function and send_libinfo_message
 */
void ProcUtils::send_loaded_libraries()
{
    vector<pair<string, string> > lib_vec;
    dl_iterate_phdr(get_loaded_libs, &lib_vec);
    ProcUtils::send_libinfo_message(lib_vec);
}

/**
 * Returns the thread ID of
 * the calling thread
 */
pid_t ProcUtils::gettid()
{
    pid_t tid = -1;

    if ((tid = syscall(__NR_gettid)) < 0)
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    SysUtil::get_error(errno).c_str());

    return tid;
}

/**
 * Caches the pid supplied
 */
void ProcUtils::setpid(const pid_t pid)
{
    opus_pid = pid;
}

/**
 * Reads the process ID from /proc as in case
 * of vfork, the glibc getpid function returns
 * the incorrect pid.
 */
pid_t ProcUtils::__getpid()
{
    pid_t pid = -1;
    char *proc_pid_path = NULL;

    try
    {
        proc_pid_path = realpath("/proc/self", NULL);
        if (!proc_pid_path)
            throw std::runtime_error(SysUtil::get_error(errno));

        string pid_path(proc_pid_path);

        int64_t found_pos = pid_path.rfind("/");
        if (found_pos == (int64_t)string::npos)
            throw std::runtime_error("Could not find pid from /proc/self");

        string pid_str = pid_path.substr(found_pos + 1);
        pid = atoi(pid_str.c_str());
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        pid = ::getpid(); // use glibc's getpid
    }

    if (proc_pid_path) free(proc_pid_path);

    return pid;
}

/**
 * Returns the cached pid
 */
pid_t ProcUtils::getpid()
{
    return opus_pid;
}

/**
 * Given a symbol (glibc function name), this method
 * returns the address of the symbol if found.
 */
void* ProcUtils::get_sym_addr(const string& symbol)
{
    /*
        The libc function pointer map should get populated
        at process startup. The only case when a symbol will
        not be found is when a libc function is invoked from 
        a processes .preinit_array method.
    */
    try
    {
        if (!libc_func_map)
            libc_func_map = new std::map<string, void*>();
    }
    catch(const std::bad_alloc& e)
    {
        // No point turning off interposition we will crash anyway.
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    std::map<string, void*>::iterator miter = libc_func_map->find(symbol);
    if (miter != libc_func_map->end())
        return miter->second;

    // Allow lazy loading of the symbol
    return ProcUtils::add_sym_addr(symbol);
}

/*
    Allows lazy loading of glibc function symbols. This
    can happen if an application calls a glibc function
    in its .preinit_array section. Will break if multiple
    threads are created in the .preinit_array section.
*/
void* ProcUtils::add_sym_addr(const string& symbol)
{
    void *func_ptr = NULL;
    char *sym_error = NULL;

    try
    {
        if (!libc_func_map)
            libc_func_map = new std::map<string, void*>();
    }
    catch(const std::bad_alloc& e)
    {
        // No point turning off interposition we will crash anyway.
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    dlerror();
    func_ptr = dlsym(RTLD_NEXT, symbol.c_str());
    if (func_ptr == NULL)
    {
        if ((sym_error = dlerror()) != NULL)
            LOG_MSG(LOG_ERROR, "[%s:%d]: Critical error!! %s\n",
                        __FILE__, __LINE__, sym_error);

        exit(EXIT_FAILURE);
    }

    (*libc_func_map)[symbol] = func_ptr;
    return func_ptr;
}

/**
 * Wrapper to instantiate the
 * thread local connection object.
 */
bool ProcUtils::connect()
{
    bool ret = true;

    try
    {
        std::string comm_mode = SysUtil::get_env_val("OPUS_PROV_COMM_MODE");

        if (comm_mode == "unix")
        {
            std::string uds_path_str;
            get_uds_path(&uds_path_str);

            if (uds_path_str.empty())
                throw std::runtime_error("Cannot connect!! UDS path is empty");

            comm_obj = new UDSCommClient(uds_path_str);
        }
        else if (comm_mode == "tcp")
        {
            std::string address;
            int port;
            get_tcp_address(&address, &port);

            if(address.empty())
                throw std::runtime_error("Cannot connect! Address is empty");

            comm_obj = new TCPCommClient(address, port);
        }
        else throw std::runtime_error("Invalid provenance comm mode");
    }
    catch(const std::exception& e)
    {
        ret = false;
        interpose_off(e.what());
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

/**
 * Wrapper to destroy the
 * thread local connection object.
 */
void ProcUtils::disconnect()
{
    if (comm_obj)
    {
        delete comm_obj;
        comm_obj = NULL;
        conn_ref_count = 0;
    }
}

/**
 * Converts a 32-bit signed integer to string
 */
char* ProcUtils::opus_itoa(const int32_t val, char *str)
{
    if (snprintf(str, MAX_INT32_LEN, "%d", val) < 0)
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));

    return str;
}

/**
 * Returns a protobuf object when passed an obj type
 */
Message* ProcUtils::get_proto_msg(const PayloadType msg_type)
{
    try
    {
        switch (msg_type)
        {
            case PayloadType::FUNCINFO_MSG:

                if (__alt_func_msg_ptr) return __alt_func_msg_ptr;

                if (!func_msg_obj) func_msg_obj = new FuncInfoMessage();
                return func_msg_obj;

            case PayloadType::GENERIC_MSG:

                if (__alt_gen_msg_ptr) return __alt_gen_msg_ptr;

                if (!gen_msg_obj) gen_msg_obj = new GenericMessage();
                return gen_msg_obj;

            default:
                throw std::runtime_error("LOG_ERROR!! Invalid message type");
        }
    }
    catch(const std::bad_alloc& e)
    {
        interpose_off(e.what());
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return NULL;
}

/**
 * Clears TLS protobuf objects
 */
void ProcUtils::clear_proto_objects()
{
    if (func_msg_obj) func_msg_obj->Clear();
    if (gen_msg_obj) gen_msg_obj->Clear();
}


/**
 * Store alternate protobuf message location
 */
void ProcUtils::use_alt_proto_msg(FuncInfoMessage *__func_obj,
                                    GenericMessage *__gen_obj)
{
    __alt_func_msg_ptr = __func_obj;
    __alt_gen_msg_ptr = __gen_obj;
}

/**
 * NULLs TLS pointers to alternate protobuf objects
 */
void ProcUtils::restore_proto_tls()
{
    __alt_func_msg_ptr = NULL;
    __alt_gen_msg_ptr = NULL;
}

void ProcUtils::incr_conn_ref_count()
{
    ++conn_ref_count;
}

uint32_t ProcUtils::decr_conn_ref_count()
{
    return --conn_ref_count;
}

/**
 * Check if interposition has been turned off
 */
bool ProcUtils::is_interpose_off()
{
    if (opus_interpose_mode == OPUS::OPUSMode::OPUS_OFF)
        return true;
    return false;
}

/**
 * Used to report a severe error such as resource
 * allocation error. Will turn interposition off
 * on all threads in the process.
 */
void ProcUtils::interpose_off(const string& desc)
{
    ProcUtils::inside_opus(true);

#ifdef CAPTURE_SIGNALS
    if (opus_interpose_mode == OPUS::OPUSMode::OPUS_OFF)
        SignalUtils::restore_all_signal_states();
#endif

    const size_t env_buff_len = 32;
    char env_buff[env_buff_len] = "";

    snprintf(env_buff, env_buff_len,
            "OPUS_INTERPOSE_MODE=%d", OPUS::OPUSMode::OPUS_OFF);

    if (putenv(env_buff) != 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    SysUtil::get_error(errno).c_str());
    }

    LOG_MSG(LOG_DEBUG, "[%s:%d]: %s\n", __FILE__, __LINE__, desc.c_str());

    if (comm_obj)
    {
        send_telemetry_msg(FrontendTelemetry::SEVERE, desc.c_str());
        disconnect();
    }

    // Set global OPUS interpose mode to OFF
    opus_interpose_mode = OPUS::OPUSMode::OPUS_OFF;
}

const bool ProcUtils::is_opus_fd(const int fd){
    if (!comm_obj) return false;
    return comm_obj->is_opus_fd(fd);
}

const bool ProcUtils::is_opus_fd(FILE* fp){
    int fd = fileno(fp);
    return fd >= 0 && is_opus_fd(fd);
}

void ProcUtils::set_opus_ipose_mode(const int _mode)
{
    opus_interpose_mode = _mode;
}

const int ProcUtils::get_opus_ipose_mode()
{
    return opus_interpose_mode;
}
