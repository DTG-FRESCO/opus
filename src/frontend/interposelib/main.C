#include "main.h"

#include <unistd.h>
#include <string>
#include <stdexcept>

#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"
#include "signal_utils.h"
#include "functions.h"

__attribute__((section(".init_array")))
    typeof(opus_init) *__opus_init = opus_init;

__attribute__((section(".fini_array")))
    typeof(opus_fini) *__opus_fini = opus_fini;


static bool check_env_opus_interpose_off()
{
    try
    {
        char *ipose_off_value = ProcUtils::get_env_val("OPUS_INTERPOSE_OFF");

        // Return true if OPUS_INTERPOSE_OFF exists
        if (ipose_off_value) return true;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return false;
}

/**
 * Initializes datastructures and functionalities
 * within OPUS. Also sends the process startup
 * message along with the environent information
 * to the backend.
 */
void opus_init(int argc, char** argv, char** envp)
{
    ProcUtils::test_and_set_flag(true);

    opus_init_libc_funcs();

    // Set the correct pid
    ProcUtils::setpid(getpid());

    if (check_env_opus_interpose_off())
    {
        DEBUG_LOG("[%s:%d]: OPUS_INTERPOSE_OFF flag is enabled\n",
                    __FILE__, __LINE__);
        return;
    }

    try
    {
#ifdef CAPTURE_SIGNALS
        if (!SignalUtils::initialize())
            throw std::runtime_error("SignalUtils::initialize failed!!");
#endif

        if (!ProcUtils::connect())
            throw std::runtime_error("ProcUtils::connect failed!!");
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        return; // Interposition is turned off
    }

#ifdef CAPTURE_SIGNALS
    if (!SignalUtils::init_signal_capture())
        return;
#endif
    ProcUtils::send_startup_message(argc, argv, envp);
    ProcUtils::send_loaded_libraries();

    ProcUtils::test_and_set_flag(false);
}

/**
 * Called when a process terminates. The connection
 * to the backend is closed gracefully.
 */
void opus_fini()
{
    ProcUtils::test_and_set_flag(true);

    DEBUG_LOG("[%s:%d]: PID: %d, TID: %d inside opus_fini\n",
                __FILE__, __LINE__, ProcUtils::getpid(), ProcUtils::gettid());

    ProcUtils::disconnect();
    ProcUtils::test_and_set_flag(false);
}
