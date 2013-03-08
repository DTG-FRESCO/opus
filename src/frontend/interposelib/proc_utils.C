#include "log.h"
#include "proc_utils.h"

#include <string.h>
#include <time.h>
#include <stdint.h>
#include <errno.h>

uint64_t ProcUtils::get_time()
{
    struct timespec tp;

    if(clock_gettime(CLOCK_MONOTONIC_RAW, &tp) < 0)
        DEBUG_LOG("[%s:%d]: %s\n",__FILE__,__LINE__,strerror(errno));

    uint64_t nsecs = (uint64_t)tp.tv_sec * 1000000000 + (uint64_t)tp.tv_nsec;

    return nsecs;
}
