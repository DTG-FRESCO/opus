#include "main.h"

#include <grp.h>
#include <pwd.h>
#include <unistd.h>

#include "functions.h"
#include "proc_utils.h"
#include "uds_client.h"

void send_startup_message(){
    StartupMessage start_msg;

    char link[1024];
    char exe[1024];

    memset(link, 0, sizeof(link));
    memset(exe, 0, sizeof(exe));

    snprintf(link,sizeof(link),"/proc/%d/exe",getpid());
    if (readlink(link,exe,sizeof(exe)) >= 0) {
        start_msg.set_exec_name(exe);
    }

    char *cwd = NULL;
    if ((cwd = getcwd(NULL,0)) != NULL) {
        start_msg.set_cwd(cwd);
    }

    start_msg.set_cmd_line_args("");
    start_msg.set_user_name(getpwuid(getuid())->pw_name);
    start_msg.set_group_name(getgrgid(getgid())->gr_name);
    start_msg.set_ppid(getppid());

    const uint64_t msg_size = start_msg.ByteSize();

    //Note: Should we store header message globally
    //and avoid reconstructing it each time?
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

void deinitialise(){
    ProcUtils::test_and_set_flag(true);
    UDSCommClient::get_instance()->shutdown();
    ProcUtils::test_and_set_flag(false);
}

void initialise(){
    ProcUtils::test_and_set_flag(true);

    if (UDSCommClient::get_instance()->connect("./demo_socket")){
        send_startup_message();
        ProcUtils::test_and_set_flag(false);
    }
}
