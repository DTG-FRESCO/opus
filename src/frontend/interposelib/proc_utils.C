#include "proc_utils.h"

#include <errno.h>
#include <string.h>
#include <time.h>
#include <cstdint>
#include <string>

#include "log.h"
#include "uds_client.h"


bool ProcUtils::in_func_flag = false;

uint64_t ProcUtils::get_time()
{
    struct timespec tp;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &tp) < 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));

    uint64_t nsecs = (uint64_t)tp.tv_sec * 1000000000UL + (uint64_t)tp.tv_nsec;

    return nsecs;
}

void ProcUtils::serialise_and_send_data(const Message& msg_obj)
{
  int size = msg_obj.ByteSize();

  void* buf = malloc(size);
  if (buf == NULL)
  {
    DEBUG_LOG("[%s:%d]: Failed to allocate buffer\n", __FILE__, __LINE__);
    return;
  }

  msg_obj.SerializeToArray(buf, size);

  if (!UDSCommClient::get_instance()->send_data(buf, size))
  {
    DEBUG_LOG("[%s:%d]: Sending data failed\n", __FILE__, __LINE__);
    free(buf);
    return;
  }

  free(buf);
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
