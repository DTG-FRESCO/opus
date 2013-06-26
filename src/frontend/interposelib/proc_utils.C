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

#define STRINGIFY(value) #value

using std::pair;
using std::string;
using std::vector;

/* Initialize class static members */
__thread bool ProcUtils::in_func_flag = true; // TLS
__thread UDSCommClient *ProcUtils::comm_obj = NULL; // TLS
std::map<string, void*> *ProcUtils::libc_func_map = NULL;

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
            DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
            return -1;
        }

        string md5_sum;
        ProcUtils::get_md5_sum(real_path, &md5_sum);

        lib_vec->push_back(make_pair(real_path, md5_sum));
        free(real_path);
    }

    return 0;
}

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
            DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
            continue;
        }

        res_limit = start_msg->add_resource_limit();
        res_limit->set_key((*citer).first);
        res_limit->set_value(std::to_string(rlim.rlim_cur));
    }
}

static inline void set_system_info(StartupMessage* start_msg)
{
    struct utsname buf;

    if (uname(&buf) < 0)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
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

void ProcUtils::get_preload_path(string* ld_preload_path)
{
    try
    {
        char* preload_path = getenv("LD_PRELOAD");
        if (!preload_path)
            throw std::runtime_error("Could not read LD_PRELOAD path");

        DEBUG_LOG("[%s:%d]: LD_PRELOAD path: %s\n",
                    __FILE__, __LINE__, preload_path);

        *ld_preload_path = preload_path;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }
}

uint64_t ProcUtils::get_time()
{
    struct timespec tp;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &tp) < 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));

    uint64_t nsecs = (uint64_t)tp.tv_sec * 1000000000UL + (uint64_t)tp.tv_nsec;

    return nsecs;
}


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
        DEBUG_LOG("[%s:%d]: strftime returned zero bytes\n",
                        __FILE__, __LINE__);
        return;
    }
    *date_time = buffer;
}


void ProcUtils::serialise_and_send_data(const Header& header_obj,
                                        const Message& payload_obj)
{
    if (!comm_obj) return;

    char* buf = NULL;

    int hdr_size = header_obj.ByteSize();
    int pay_size = payload_obj.ByteSize();
    int total_size = hdr_size + pay_size;

    try
    {
        buf = new char[total_size];

        /* Serialize the header data and store it */
        if (!header_obj.SerializeToArray(buf, hdr_size))
            throw std::runtime_error("Failed to serialise header");

        /* Serialize the payload data and store it */
        if (!payload_obj.SerializeToArray(buf+hdr_size, pay_size))
            throw std::runtime_error("Failed to serialise payload");

        if (!comm_obj->send_data(buf, total_size))
            throw std::runtime_error("Sending data failed");
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }

    if (buf) delete buf;
}

/*
   Returns true if we are already 
   inside an overridden libc function
*/
bool ProcUtils::test_and_set_flag(const bool value)
{
    bool ret = in_func_flag & value;

    if (value && in_func_flag) return ret;

    in_func_flag = value;
    return ret;
}

void ProcUtils::get_uds_path(string* uds_path_str)
{
    try
    {
        char* uds_path = getenv("OPUS_UDS_PATH");
        if (!uds_path)
            throw std::runtime_error
                ("Could not read OPUS UDS path from environment");

        if (strlen(uds_path) > UNIX_PATH_MAX)
        {
            string err_desc = "UDS path length exceeds max allowed value "
                                    + std::to_string(UNIX_PATH_MAX);
            throw std::runtime_error(err_desc);
        }

        *uds_path_str = uds_path;

        DEBUG_LOG("[%s:%d]: OPUS UDS path: %s\n", __FILE__, __LINE__, uds_path);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }
}

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
            else throw std::runtime_error(strerror(errno));
        }

        user_name_str = pwd.pw_name;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }

    if (buf) delete buf;
    return user_name_str;
}

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
            else throw std::runtime_error(strerror(errno));
        }

        group_name_str = grp.gr_name;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }

    if (buf) delete buf;
    return group_name_str;
}

void ProcUtils::send_startup_message(const int argc, char** argv, char** envp)
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    StartupMessage start_msg;

    char link[1024] = "";
    char exe[1024] = "";

    snprintf(link, sizeof(link), "/proc/%d/exe", getpid());
    if (readlink(link, exe , sizeof(exe)) >= 0)
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

void ProcUtils::send_startup_message()
{
    ProcUtils::send_startup_message(0, NULL, NULL);
}

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

void ProcUtils::send_loaded_libraries()
{
    vector<pair<string, string> > lib_vec;
    dl_iterate_phdr(get_loaded_libs, &lib_vec);
    ProcUtils::send_libinfo_message(lib_vec);
}

void ProcUtils::get_md5_sum(const string& real_path, string *md5_sum)
{
    int fd = -1;

    try
    {
        struct stat buf;

        fd = open(real_path.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error(strerror(errno));

        if (fstat(fd, &buf) < 0)
            throw std::runtime_error(strerror(errno));

        size_t file_size = buf.st_size;
        void *data = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);
        if (data == MAP_FAILED)
            throw std::runtime_error(strerror(errno));

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
            throw std::runtime_error(strerror(errno));
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    if (fd != -1) close(fd);
}

pid_t ProcUtils::gettid()
{
    pid_t tid = -1;

    if ((tid = syscall(__NR_gettid)) < 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));

    return tid;
}

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
    This function will not be called from multiple
    threads simultaneously as the OPUS library
    loads the libc function map at startup
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
            DEBUG_LOG("[%s:%d]: Critical error!! %s\n",
                        __FILE__, __LINE__, sym_error);

        exit(EXIT_FAILURE);
    }

    (*libc_func_map)[symbol] = func_ptr;
    return func_ptr;
}

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
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

void ProcUtils::disconnect()
{
    if (comm_obj)
    {
        delete comm_obj;
        comm_obj = NULL;
    }
}

const string ProcUtils::canonicalise_path(string path)
{
    string pathname;
    char* real_path = NULL;
    real_path = realpath(path.c_str(), real_path);
    if (real_path)
    { 
        pathname = real_path;
        free(real_path);
        return pathname;
    }
    else
    {
        return path;
    }
}

const string ProcUtils::abs_path(string path)
{
    string path_tail;
    string path_head;
    path_head = dirname(const_cast<char*>(path.c_str()));
    path_tail = basename(const_cast<char*>(path.c_str()));
    char* real_path = NULL;
    real_path = realpath(path_head.c_str(), NULL);
    if (!real_path)
    {
        return path;
    }
    else
    {
        path_head = real_path;
        path_head.append("/");
        path_head.append(path_tail);
        return path_head;
    }
}

