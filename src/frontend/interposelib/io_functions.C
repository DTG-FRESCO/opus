#include <cstdint>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/limits.h>
#include <pwd.h>
#include <signal.h>
#include <stdarg.h>
#include <string>
#include "log.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "message_util.h"
#include "track_errno.h"


#define GET_MODE                    \
    mode_t mode = 0;                \
    if ((flags & O_CREAT) != 0)     \
    {                               \
        va_list arg;                \
        va_start(arg, flags);       \
        mode = va_arg(arg, mode_t); \
        va_end(arg);                \
    }

/**
 * Function template to merge open and open64
 */
template <typename T>
static int __open_internal(const char* pathname, int flags,
                        const char *func_name, T real_open, mode_t mode)
{
    TrackErrno err_obj(errno);

    if (!real_open)
        real_open = (T)ProcUtils::get_sym_addr(func_name);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real_open)(pathname, flags, mode);
        err_obj = errno;
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        errno = 0;
        int ret = (*real_open)(pathname, flags, mode);
        err_obj = errno;
        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real_open)(pathname, flags, mode);

    int errno_value = errno;
    err_obj = errno;
    uint64_t end_time = ProcUtils::get_time();

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg) return ret;

    KVPair* tmp_arg;
    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("pathname");
    if (pathname)
    {
        char pathname_buf[PATH_MAX + 1] = "";
        tmp_arg->set_value(ProcUtils::canonicalise_path(pathname, pathname_buf));
    }

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("flags");

    char flags_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(flags, flags_buf));

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("mode");

    char mode_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(mode, mode_buf));

    set_func_info_msg(func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    func_msg->Clear();

    return ret;
}

/**
 * Interposition function for open
 */
extern "C" int open(const char *pathname, int flags, ...)
{
    static OPEN_POINTER real_open = NULL;

    GET_MODE;
    return __open_internal(pathname, flags, "open", real_open, mode);
}

/**
 * Interposition function for open64
 */
extern "C" int open64(const char *pathname, int flags, ...)
{
    static OPEN64_POINTER real64_open = NULL;

    GET_MODE;
    return __open_internal(pathname, flags, "open64", real64_open, mode);
}
