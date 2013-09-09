#include "opus_vfork.h"

#include <dlfcn.h>
#include <stdlib.h>
#include "log.h"
#include "proc_utils.h"

void* get_vfork_symbol(void)
{
    typedef pid_t (*VFORK_PTR)(void);
    static VFORK_PTR real_vfork = NULL;

    if (!real_vfork)
        real_vfork = (VFORK_PTR)ProcUtils::get_sym_addr("vfork");

    return reinterpret_cast<void*>(real_vfork);
}

void vfork_send_startup_message(void)
{
    if (ProcUtils::test_and_set_flag(true))
        return; // Interposition is turned off

    // Set the correct pid
    ProcUtils::setpid(ProcUtils::__getpid());

    ProcUtils::send_startup_message();
    ProcUtils::test_and_set_flag(false);
}
