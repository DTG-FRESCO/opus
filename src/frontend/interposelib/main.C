#include "main.h"

#include <unistd.h>
#include <string>
#include <stdexcept>

#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"
#include "signal_utils.h"
#include "comm_thread.h"

__attribute__((section(".init_array")))
    typeof(opus_init) *__opus_init = opus_init;

__attribute__((section(".fini_array")))
    typeof(opus_fini) *__opus_fini = opus_fini;


void opus_init(int argc, char** argv, char** envp)
{
    ProcUtils::test_and_set_flag(true);

    try
    {
        if (!SignalUtils::initialize_lock())
            throw std::runtime_error("SignalUtils::initialize_lock failed!!");

        if (!ProcUtils::init_libc_interposition())
            throw std::runtime_error("Init libc interposition failed!!");

        /* Should only be called in one thread during startup */
        ProcUtils::comm_thread_obj = CommThread::get_instance();
        if (!ProcUtils::comm_thread_obj)
            throw std::runtime_error("Could not create comm thread object");
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        return; // Interposition is turned off
    }

    SignalUtils::init_signal_capture();
    ProcUtils::send_startup_message(argc, argv, envp);
    ProcUtils::send_loaded_libraries();

    ProcUtils::test_and_set_flag(false);
}

void opus_fini()
{
    ProcUtils::test_and_set_flag(true);

    DEBUG_LOG("[%s:%d]: PID: %d, TID: %d inside opus_fini\n",
                __FILE__, __LINE__, getpid(), ProcUtils::gettid());

    if (ProcUtils::comm_thread_obj)
        ProcUtils::comm_thread_obj->shutdown_thread();

    ProcUtils::test_and_set_flag(false);
}
