#include "proc_utils.h"

#include <errno.h>
#include <string.h>
#include <time.h>
#include <grp.h>
#include <pwd.h>
#include <linux/un.h>
#include <unistd.h>
#include <link.h>
#include <openssl/md5.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <cstdint>
#include <string>
#include <stdexcept>
#include <sstream>
#include <iomanip>

#include "log.h"
#include "uds_client.h"

using std::pair;
using std::string;
using std::vector;
using ::google::protobuf::Message;
using ::fresco::opus::IPCMessage::KVPair;
using ::fresco::opus::IPCMessage::Header;
using ::fresco::opus::IPCMessage::GenMsgType;
using ::fresco::opus::IPCMessage::StartupMessage;
using ::fresco::opus::IPCMessage::LibInfoMessage;
using ::fresco::opus::IPCMessage::GenericMessage;
using ::fresco::opus::IPCMessage::FuncInfoMessage;
using ::fresco::opus::IPCMessage::PayloadType;

#include "message_util.h"

/* Initialize class static members */
bool ProcUtils::in_func_flag = true;
string ProcUtils::ld_preload_path = "";


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
        delete real_path;
    }

    return 0;
}

void inline set_command_line(StartupMessage* start_msg,
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

const string& ProcUtils::get_preload_path()
{
    if (!ld_preload_path.empty())
        return ld_preload_path;

    try
    {
        char* preload_path = getenv("LD_PRELOAD");
        if (!preload_path)
            throw std::runtime_error("Could not read LD_PRELOAD path");

        DEBUG_LOG("[%s:%d]: LD_PRELOAD path: %s\n",
                    __FILE__, __LINE__, preload_path);

        ld_preload_path = preload_path;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
    }

    return ld_preload_path;
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

        if (!UDSCommClient::get_instance()->send_data(buf, total_size))
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
