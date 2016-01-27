#include "main.h"

#include <unistd.h>
#include <string>
#include <stdexcept>

#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"
#include "signal_utils.h"
#include "functions.h"
#include "common_enums.h"
#include "sys_util.h"

__attribute__((section(".init_array")))
    typeof(opus_init) *__opus_init = opus_init;

__attribute__((section(".fini_array")))
    typeof(opus_fini) *__opus_fini = opus_fini;


static OPUS::OPUSMode check_env_opus_interpose_mode()
{
    // Default to OPUS_ON
    OPUS::OPUSMode opus_mode = OPUS::OPUSMode::OPUS_ON;

    try
    {
        char *mode_str = SysUtil::get_env_val("OPUS_INTERPOSE_MODE");

        if (mode_str) opus_mode = static_cast<OPUS::OPUSMode>(atoi(mode_str));

        ProcUtils::set_opus_ipose_mode(opus_mode);
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_DEBUG, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return opus_mode;
}

/**
 * Initializes datastructures and functionalities
 * within OPUS. Also sends the process startup
 * message along with the environent information
 * to the backend.
 */
void opus_init(int argc, char** argv, char** envp)
{
    ProcUtils::inside_opus(true);

    Logging::init_logging();
    opus_init_libc_funcs();

    // Set the correct pid
    ProcUtils::setpid(getpid());

    // Set message aggregation flag
    ProcUtils::set_msg_aggr_flag();

    if (check_env_opus_interpose_mode() == OPUS::OPUSMode::OPUS_OFF)
    {
        LOG_MSG(LOG_DEBUG, "[%s:%d]: Interposition is turned OFF\n",
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
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        return; // Interposition is turned off
    }

#ifdef CAPTURE_SIGNALS
    if (!SignalUtils::init_signal_capture())
        return;
#endif
    ProcUtils::send_startup_message(argc, argv, envp);
    ProcUtils::send_loaded_libraries();

    ProcUtils::inside_opus(false);
}

/**
 * Called when a process terminates. The connection
 * to the backend is closed gracefully.
 */
void opus_fini()
{
    ProcUtils::inside_opus(true);

    LOG_MSG(LOG_DEBUG, "[%s:%d]: PID: %d, TID: %d inside opus_fini\n",
                __FILE__, __LINE__, ProcUtils::getpid(), ProcUtils::gettid());

    ProcUtils::flush_buffered_data();

    ProcUtils::disconnect();
    ProcUtils::inside_opus(false);
}
