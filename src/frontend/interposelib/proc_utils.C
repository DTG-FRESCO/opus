#include "proc_utils.h"

#include <errno.h>
#include <fcntl.h>
#include <grp.h>
#include <libgen.h>
#include <link.h>
#include <linux/un.h>
#include <openssl/md5.h>
#include <pwd.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>
#include <sys/syscall.h>
#include <cstdint>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <map>
#include "log.h"
#include "uds_client.h"
#include "message_util.h"
#include "messaging.h"

#define STRINGIFY(value) #value

using std::pair;
using std::string;
using std::vector;

/** Thread local storage */
__thread bool ProcUtils::in_func_flag = true;
__thread UDSCommClient *ProcUtils::comm_obj = NULL;
__thread uint32_t ProcUtils::conn_ref_count = 0;
__thread FuncInfoMessage *ProcUtils::func_msg_obj = NULL;
__thread GenericMessage *ProcUtils::gen_msg_obj = NULL;
__thread FuncInfoMessage *ProcUtils::__alt_func_msg_ptr = NULL;
__thread GenericMessage *ProcUtils::__alt_gen_msg_ptr = NULL;

/** process ID */
pid_t ProcUtils::opus_pid = -1;

/** glibc function name to symbol map */
std::map<string, void*> *ProcUtils::libc_func_map = NULL;

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
                        ProcUtils::get_error(errno).c_str());
            return -1;
        }

        string md5_sum;
        ProcUtils::get_md5_sum(real_path, &md5_sum);

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
                        ProcUtils::get_error(errno).c_str());
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
                    ProcUtils::get_error(errno).c_str());
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
        if (i > 0) cmd_line_str += " ";
        cmd_line_str +=  argv[i];
    }

    start_msg->set_cmd_line_args(cmd_line_str);
}

/**
 * Given an environment variable key
 * this function returns its value
 */
char* ProcUtils::get_env_val(const string& env_key)
{
    char* val = getenv(env_key.c_str());
    if (!val)
    {
        string err_desc = "Could not read environment variable " + env_key;
        throw std::runtime_error(err_desc);
    }

    return val;
}

/**
 * Retrieves the value of LD_PRELOAD_PATH environment variable.
 */
void ProcUtils::get_preload_path(string* ld_preload_path)
{
    try
    {
        char *preload_path = get_env_val("LD_PRELOAD");

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
 * Returns the raw monotonic clock time of the system
 */
uint64_t ProcUtils::get_time()
{
    struct timespec tp;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &tp) < 0)
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    ProcUtils::get_error(errno).c_str());

    uint64_t nsecs = (uint64_t)tp.tv_sec * 1000000000UL + (uint64_t)tp.tv_nsec;

    return nsecs;
}

/**
 * Retrieves current time and date in a specific format
 */
void ProcUtils::get_formatted_time(string* date_time)
{
    time_t unix_time;
    struct tm timeinfo;
    char buffer[128];

    memset(buffer, 0, sizeof(buffer));

    unix_time = time(NULL);
    localtime_r(&unix_time, &timeinfo);

    if (strftime(buffer, sizeof(buffer), "%Y-%m-%d %T", &timeinfo) == 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: strftime returned zero bytes\n",
                        __FILE__, __LINE__);
        return;
    }
    *date_time = buffer;
}

/**
 * Serializes the header and payload data
 * and sends this data to the OPUS backend.
 */
bool ProcUtils::serialise_and_send_data(const struct Header& header_obj,
                                        const Message& payload_obj)
{
    bool ret = true;

    if (!comm_obj)
    {
        ret = false;
        return ret;
    }

    char *buf = NULL;

    int hdr_size = sizeof(header_obj);
    int pay_size = payload_obj.ByteSize();
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
bool ProcUtils::test_and_set_flag(const bool value)
{
    bool ret = in_func_flag & value;

    if (value && in_func_flag) return ret;

    in_func_flag = value;
    return ret;
}

/**
 * Reads the UDS path from the environment
 */
void ProcUtils::get_uds_path(string* uds_path_str)
{
    try
    {
        char* uds_path = get_env_val("OPUS_UDS_PATH");
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
 * Given a user ID, the user name string is returned
 */
const string ProcUtils::get_user_name(const uid_t user_id)
{
    struct passwd pwd;
    struct passwd *result;
    char *buf = NULL;
    size_t bufsize = -1;
    string user_name_str = "";

    bufsize = sysconf(_SC_GETPW_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    try
    {
        buf = new char[bufsize];

        int ret = getpwuid_r(user_id, &pwd, buf, bufsize, &result);
        if (result == NULL)
        {
            if (ret == 0) throw std::runtime_error("User not found");
            else throw std::runtime_error(ProcUtils::get_error(errno));
        }

        user_name_str = pwd.pw_name;
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    delete[] buf;
    return user_name_str;
}

/**
 * Given a group ID, the group name string is returned
 */
const string ProcUtils::get_group_name(const gid_t group_id)
{
    struct group grp;
    struct group *result;
    char *buf = NULL;
    size_t bufsize = -1;
    string group_name_str = "";

    bufsize = sysconf(_SC_GETGR_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    try
    {
        buf = new char[bufsize];

        int ret = getgrgid_r(group_id, &grp, buf, bufsize, &result);
        if (result == NULL)
        {
            if (ret == 0) throw std::runtime_error("Group not found");
            else throw std::runtime_error(ProcUtils::get_error(errno));
        }

        group_name_str = grp.gr_name;
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    delete[] buf;
    return group_name_str;
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
    start_msg.set_user_name(ProcUtils::get_user_name(getuid()));
    start_msg.set_group_name(ProcUtils::get_group_name(getgid()));
    start_msg.set_ppid(getppid());

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
 * Obtains the md5 checksum when given a valid file path
 */
void ProcUtils::get_md5_sum(const string& real_path, string *md5_sum)
{
    int fd = -1;

    try
    {
        struct stat buf;

        fd = open(real_path.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error(ProcUtils::get_error(errno));

        if (fstat(fd, &buf) < 0)
            throw std::runtime_error(ProcUtils::get_error(errno));

        size_t file_size = buf.st_size;
        void *data = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);
        if (data == MAP_FAILED)
            throw std::runtime_error(ProcUtils::get_error(errno));

        unsigned char result[MD5_DIGEST_LENGTH] = "";
        if (MD5(reinterpret_cast<unsigned char*>(data),
                file_size, result) != NULL)
        {
            std::stringstream sstr;
            for (int i = 0; i < MD5_DIGEST_LENGTH; i++)
            {
                sstr << std::setfill('0') << std::setw(2)
                    << std::hex << (uint16_t)result[i];
            }
            *md5_sum = sstr.str();
        }

        if (munmap(data, file_size) < 0)
            throw std::runtime_error(ProcUtils::get_error(errno));
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    if (fd != -1) close(fd);
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
                    ProcUtils::get_error(errno).c_str());

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
            throw std::runtime_error(ProcUtils::get_error(errno));

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
    if (!libc_func_map)
        libc_func_map = new std::map<string, void*>();

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

    if (!libc_func_map)
        libc_func_map = new std::map<string, void*>();

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
        std::string uds_path_str;
        get_uds_path(&uds_path_str);

        if (uds_path_str.empty())
            throw std::runtime_error("Cannot connect!! UDS path is empty");

        // Connect to the backend
        comm_obj = new UDSCommClient(uds_path_str);
    }
    catch(const std::exception& e)
    {
        ret = false;
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
    }
}

/**
 * Canonicalises a given pathname
 */
const char* ProcUtils::canonicalise_path(const char *path, char *actual_path)
{
    char *real_path = realpath(path, actual_path);
    if (!real_path)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
        return path;
    }

    return real_path;
}

/**
 * Finds the absolute path of a given path
 */
const char* ProcUtils::abs_path(const char *path, char *abs_path)
{
    // strdupa uses alloca
    char *dir = strdupa(path);
    char *base = strdupa(path);

    char *path_head = dirname(dir);
    char *path_tail = basename(base);

    char *real_path = realpath(path_head, abs_path);
    if (!real_path)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
        return path;
    }

    strcat(real_path, "/");
    strcat(real_path, path_tail);

    return real_path;
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
 * Given an errno value, this method uses a
 * thread safe implementation of strerror to
 * retrieve the error description.
 */
const string ProcUtils::get_error(const int err_num)
{
    char err_buf[256] = "";

    char *err_str = strerror_r(err_num, err_buf, sizeof(err_buf));
    if (!err_str)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: strerror_r error: %d\n",
                    __FILE__, __LINE__, errno);
        return "";
    }

    return err_str;
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
