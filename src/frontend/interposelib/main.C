#include "main.h"

#include <grp.h>
#include <pwd.h>
#include <unistd.h>
#include <linux/un.h>

#include "log.h"
#include "functions.h"
#include "proc_utils.h"
#include "uds_client.h"

static void get_uds_path(std::string& uds_path_str)
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

    uds_path_str = uds_path;
    DEBUG_LOG("[%s:%d]: OPUS UDS path: %s\n", __FILE__, __LINE__, uds_path);
}

void send_startup_message()
{
    DEBUG_LOG("[%s:%d]: Entering %s\n", 
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    StartupMessage start_msg;

    char link[1024];
    char exe[1024];

    memset(link, 0, sizeof(link));
    memset(exe, 0, sizeof(exe));

    snprintf(link,sizeof(link),"/proc/%d/exe",getpid());
    if (readlink(link,exe,sizeof(exe)) >= 0) 
    {
        start_msg.set_exec_name(exe);
    }

    char *cwd = NULL;
    if ((cwd = getcwd(NULL,0)) != NULL) 
    {
        start_msg.set_cwd(cwd);
    }

    start_msg.set_cmd_line_args("");
    start_msg.set_user_name(getpwuid(getuid())->pw_name);
    start_msg.set_group_name(getgrgid(getgid())->gr_name);
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

void deinitialise()
{
    ProcUtils::test_and_set_flag(true);
    UDSCommClient::get_instance()->shutdown();
    ProcUtils::test_and_set_flag(false);
}

void initialise()
{
    ProcUtils::test_and_set_flag(true);

    std::string uds_path_str;
    get_uds_path(uds_path_str);

    if (uds_path_str.empty())
    {
        DEBUG_LOG("[%s:%d]: Cannot connect!! UDS path is empty\n", 
                            __FILE__, __LINE__);
        return;
    }

    if (!UDSCommClient::get_instance()->connect(uds_path_str))
    {
        DEBUG_LOG("[%s:%d]: Connect failed\n", __FILE__, __LINE__);
        return;
    }

    send_startup_message();
    ProcUtils::test_and_set_flag(false);
}
