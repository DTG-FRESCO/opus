#include "main.h"

#include <unistd.h>
#include <string>

#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"

__attribute__((section(".init_array")))
    typeof(opus_init) *__opus_init = opus_init;

__attribute__((section(".fini_array")))
    typeof(opus_fini) *__opus_fini = opus_fini;


void opus_init(int argc, char** argv, char** envp)
{
    ProcUtils::test_and_set_flag(true);

    std::string uds_path_str;
    ProcUtils::get_uds_path(&uds_path_str);

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

    ProcUtils::send_startup_message(argc, argv, envp);
    ProcUtils::test_and_set_flag(false);
}

void opus_fini()
{
    ProcUtils::test_and_set_flag(true);
    UDSCommClient::get_instance()->shutdown();
    ProcUtils::test_and_set_flag(false);
}
