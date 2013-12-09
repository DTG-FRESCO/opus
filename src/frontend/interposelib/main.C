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

/**
 * Initializes datastructures and functionalities
 * within OPUS. Also sends the process startup
 * message along with the environent information
 * to the backend.
 */
void opus_init(int argc, char** argv, char** envp)
{
    ProcUtils::test_and_set_flag(true);

    Logging::init_logging();
    opus_init_libc_funcs();

    // Set the correct pid
    ProcUtils::setpid(getpid());

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
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        return; // Interposition is turned off
    }

#ifdef CAPTURE_SIGNALS
    SignalUtils::init_signal_capture();
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

    LOG_MSG(LOG_DEBUG, "[%s:%d]: PID: %d, TID: %d inside opus_fini\n",
                __FILE__, __LINE__, ProcUtils::getpid(), ProcUtils::gettid());

    ProcUtils::disconnect();
    ProcUtils::test_and_set_flag(false);
}
