#include <limits.h>
#include <stdlib.h>
#include <link.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <unistd.h>
#include <cstdint>
#include <vector>
#include <stdexcept>
#include "log.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "message_util.h"
#include "track_errno.h"
#include "signal_utils.h"

#define CALL_MEM_FUNC(libc_func, ...)                               \
    sigset_t old_set;                                               \
    SignalUtils::block_all_signals(&old_set);                       \
                                                                    \
    errno = 0;                                                      \
    void* ret = libc_func(__VA_ARGS__);                             \
    err_obj = errno;                                                \
                                                                    \
    SignalUtils::restore_signal_mask(&old_set);


#define MEM_FUNC_MACRO(libc_func, ...)                              \
    TrackErrno err_obj(errno);                                      \
                                                                    \
    if (ProcUtils::test_and_set_flag(true))                         \
    {                                                               \
        CALL_MEM_FUNC(libc_func, __VA_ARGS__);                      \
        return ret;                                                 \
    }                                                               \
                                                                    \
    CALL_MEM_FUNC(libc_func, __VA_ARGS__);                          \
    ProcUtils::test_and_set_flag(false);                            \
    return ret;


extern "C" void* __libc_malloc(size_t size);
extern "C" void* __libc_calloc(size_t nmemb, size_t size);
extern "C" void* __libc_realloc(void *ptr, size_t size);
extern "C" void __libc_free(void *ptr);

extern "C" void* malloc(size_t size)
{
    MEM_FUNC_MACRO(__libc_malloc, size);
}

extern "C" void* calloc(size_t nmemb, size_t size)
{
    MEM_FUNC_MACRO(__libc_calloc, nmemb, size);
}

extern "C" void* realloc(void* ptr, size_t size)
{
    MEM_FUNC_MACRO(__libc_realloc, ptr, size);
}

extern "C" void free(void* ptr)
{
    TrackErrno err_obj(errno);

    if (ProcUtils::test_and_set_flag(true))
    {
        sigset_t old_set;
        SignalUtils::block_all_signals(&old_set);

        errno = 0;
        __libc_free(ptr);
        err_obj = errno;

        SignalUtils::restore_signal_mask(&old_set);
        return;
    }

    sigset_t old_set;
    SignalUtils::block_all_signals(&old_set);

    errno = 0;
    __libc_free(ptr);
    err_obj = errno;

    SignalUtils::restore_signal_mask(&old_set);
    ProcUtils::test_and_set_flag(false);
}

