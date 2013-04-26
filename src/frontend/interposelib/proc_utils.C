#include "proc_utils.h"

#include <errno.h>
#include <string.h>
#include <time.h>
#include <grp.h>
#include <pwd.h>
#include <linux/un.h>
#include <unistd.h>
#include <cstdint>
#include <string>

#include "log.h"
#include "uds_client.h"


bool ProcUtils::in_func_flag = true;
std::string ProcUtils::ld_preload_path = "";

void ProcUtils::read_preload_path()
{
    char* preload_path = getenv("LD_PRELOAD");

    if (!preload_path) return;

    DEBUG_LOG("[%s:%d]: LD_PRELOAD path: %s\n",
                __FILE__, __LINE__, preload_path);

    ld_preload_path = preload_path;
}

const std::string& ProcUtils::get_preload_path()
{
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


void ProcUtils::get_formatted_time(std::string* date_time)
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


void ProcUtils::serialise_and_send_data(const Message& msg_obj)
{
    int size = msg_obj.ByteSize();

    void* buf = malloc(size);
    if (buf == NULL)
    {
        DEBUG_LOG("[%s:%d]: Failed to allocate buffer\n", __FILE__, __LINE__);
        return;
    }

    if (!msg_obj.SerializeToArray(buf, size))
    {
        DEBUG_LOG("[%s:%d]: Failed to serialise to buffer\n",
                        __FILE__, __LINE__);
        return;
    }

    if (!UDSCommClient::get_instance()->send_data(buf, size))
    {
        DEBUG_LOG("[%s:%d]: Sending data failed\n", __FILE__, __LINE__);
        free(buf);
        return;
    }

    free(buf);
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

void ProcUtils::get_uds_path(std::string* uds_path_str)
{
    char* uds_path = getenv("OPUS_UDS_PATH");
    if (!uds_path)
    {
        DEBUG_LOG("[%s:%d]: Could not read OPUS UDS path from environment\n",
                            __FILE__, __LINE__);
        return;
    }

    if (strlen(uds_path) > UNIX_PATH_MAX)
    {
        DEBUG_LOG("[%s:%d]: UDS path length exceeds max allowed value %d\n",
                        __FILE__, __LINE__, UNIX_PATH_MAX);
        return;
    }

    *uds_path_str = uds_path;
    DEBUG_LOG("[%s:%d]: OPUS UDS path: %s\n", __FILE__, __LINE__, uds_path);
}

const std::string ProcUtils::get_user_name(const uid_t user_id)
{
    struct passwd pwd;
    struct passwd *result;
    char *buf = NULL;
    size_t bufsize = -1;
    std::string user_name_str = "";

    bufsize = sysconf(_SC_GETPW_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    buf = reinterpret_cast<char*>(malloc(bufsize));
    if (buf == NULL)
    {
        DEBUG_LOG("[%s:%d]: malloc: %s\n", __FILE__, __LINE__, strerror(errno));
        return user_name_str;
    }

    int ret = getpwuid_r(user_id, &pwd, buf, bufsize, &result);
    if (result == NULL)
    {
        if (ret == 0)
        {
            DEBUG_LOG("[%s:%d]: User not found\n", __FILE__, __LINE__);
        }
        else
        {
            DEBUG_LOG("[%s:%d]: Error: %s\n",
                __FILE__, __LINE__, strerror(errno));
        }

        free(buf);
        return user_name_str;
    }

    user_name_str = pwd.pw_name;
    free(buf);

    return user_name_str;
}

const std::string ProcUtils::get_group_name(const gid_t group_id)
{
    struct group grp;
    struct group *result;
    char *buf = NULL;
    size_t bufsize = -1;
    std::string group_name_str = "";

    bufsize = sysconf(_SC_GETGR_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    buf = reinterpret_cast<char*>(malloc(bufsize));
    if (buf == NULL)
    {
        DEBUG_LOG("[%s:%d]: malloc: %s\n", __FILE__, __LINE__, strerror(errno));
        return group_name_str;
    }

    int ret = getgrgid_r(group_id, &grp, buf, bufsize, &result);
    if (result == NULL)
    {
        if (ret == 0)
        {
            DEBUG_LOG("[%s:%d]: Group not found\n", __FILE__, __LINE__);
        }
        else
        {
            DEBUG_LOG("[%s:%d]: Error: %s\n",
                    __FILE__, __LINE__, strerror(errno));
        }

        free(buf);
        return group_name_str;
    }

    group_name_str = grp.gr_name;
    free(buf);

    return group_name_str;
}

void ProcUtils::send_startup_message()
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    StartupMessage start_msg;

    char link[1024];
    char exe[1024];

    memset(link, 0, sizeof(link));
    memset(exe, 0, sizeof(exe));

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

    const uint64_t msg_size = start_msg.ByteSize();
    uint64_t current_time = ProcUtils::get_time();

    HeaderMessage hdr_msg;
    hdr_msg.set_timestamp(current_time);
    hdr_msg.set_pid((uint64_t)getpid());
    hdr_msg.set_payload_type(PayloadType::STARTUP_MSG);
    hdr_msg.set_payload_len(msg_size);

    ProcUtils::serialise_and_send_data(hdr_msg);
    ProcUtils::serialise_and_send_data(start_msg);

    free(cwd);
}
