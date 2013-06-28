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


void opus_init(int argc, char** argv, char** envp)
{
    ProcUtils::test_and_set_flag(true);

    opus_init_libc_funcs();

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
    SignalUtils::init_signal_capture();
#endif
    ProcUtils::send_startup_message(argc, argv, envp);
    ProcUtils::send_loaded_libraries();

    ProcUtils::test_and_set_flag(false);
}

void opus_fini()
{
    ProcUtils::test_and_set_flag(true);

    DEBUG_LOG("[%s:%d]: PID: %d, TID: %d inside opus_fini\n",
                __FILE__, __LINE__, getpid(), ProcUtils::gettid());

    ProcUtils::disconnect();
    ProcUtils::test_and_set_flag(false);
}
