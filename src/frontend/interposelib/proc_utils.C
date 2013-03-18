#include <errno.h>
#include <string.h>
#include <time.h>
#include <cstdint>
#include "log.h"
#include "proc_utils.h"

bool ProcUtils::in_func_flag = false;

uint64_t ProcUtils::get_time()
{
    struct timespec tp;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &tp) < 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));

    uint64_t nsecs = (uint64_t)tp.tv_sec * 1000000000UL + (uint64_t)tp.tv_nsec;

    return nsecs;
}

/* 
    Returns true if we are already 
    inside an overridden libc function
*/
bool ProcUtils::test_and_set_flag(const bool value)
{
    bool ret = in_func_flag & value;

    if (value && in_func_flag) return ret;

    in_func_flag = value;
    return ret;
}
