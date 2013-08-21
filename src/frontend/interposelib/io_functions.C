#include <cstdint>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pwd.h>
#include <signal.h>
#include <stdarg.h>
#include <string>
#include "log.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "message_util.h"
#include "track_errno.h"


#define GET_MODE \
    mode_t mode = 0; \
    if ((flags & O_CREAT) != 0) \
    {                           \
        va_list arg; \
        va_start(arg, flags); \
        mode = va_arg(arg, mode_t); \
        va_end(arg); \
    }               \

/**
 * Function template to merge open and open64
 */
template <typename T>
static int __open_internal(const char* pathname, int flags,
                        std::string func_name, T real_open, mode_t mode)
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

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real_open)(pathname, flags, mode);

    int errno_value = errno;
    err_obj = errno;
    uint64_t end_time = ProcUtils::get_time();

    FuncInfoMessage func_msg;
    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("pathname");
    if (pathname)
    {
        std::string pathname_value(pathname);
        ProcUtils::canonicalise_path(&pathname_value);
        tmp_arg->set_value(pathname_value);
    }

    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("flags");
    tmp_arg->set_value(std::to_string(flags));

    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("mode");
    tmp_arg->set_value(std::to_string(mode));

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
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

/**
 * Interposition function for printf
 */
extern "C" int printf(const char *format, ...)
{
    static VPRINTF_POINTER real_vprintf = NULL;
    TrackErrno err_obj(errno);

    if (!real_vprintf)
        real_vprintf = (VPRINTF_POINTER)ProcUtils::get_sym_addr("vprintf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real_vprintf)(format, args);

        err_obj = errno;
        va_end(args);


        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real_vprintf)(format, args);
    int errno_value = errno;

    err_obj = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "printf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(!comm_ret);
    return ret;
}

/**
 * Interposition function for scanf
 */
extern "C" int scanf(const char *format, ...)
{
    static VSCANF_POINTER real_vscanf = NULL;
    TrackErrno err_obj(errno);

    if (!real_vscanf)
        real_vscanf = (VSCANF_POINTER)ProcUtils::get_sym_addr("vscanf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real_vscanf)(format, args);

        err_obj = errno;
        va_end(args);

        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real_vscanf)(format, args);
    int errno_value = errno;
    err_obj = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "scanf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    return ret;
}

/**
 * Interposition function for fprintf
 */
extern "C" int fprintf(FILE *stream, const char *format, ...)
{
    static VFPRINTF_POINTER real_vfprintf = NULL;
    TrackErrno err_obj(errno);

    if (!real_vfprintf)
        real_vfprintf = (VFPRINTF_POINTER)ProcUtils::get_sym_addr("vfprintf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real_vfprintf)(stream, format, args);

        err_obj = errno;
        va_end(args);

        return ret;
    }

    int stream_fd = -1;
    if (stream) stream_fd = fileno(stream);

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real_vfprintf)(stream, format, args);
    int errno_value = errno;
    err_obj = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "fprintf";
    FuncInfoMessage func_msg;

    KVPair* tmp_arg;

    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("stream");
    tmp_arg->set_value(std::to_string(stream_fd));

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    return ret;
}

/**
 * Interposition function for fscanf
 */
extern "C" int fscanf(FILE *stream, const char *format, ...)
{
    static VFSCANF_POINTER real_vfscanf = NULL;
    TrackErrno err_obj(errno);

    if (!real_vfscanf)
        real_vfscanf = (VFSCANF_POINTER)ProcUtils::get_sym_addr("vfscanf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real_vfscanf)(stream, format, args);

        err_obj = errno;
        va_end(args);

        return ret;
    }

    int stream_fd = -1;
    if (stream) stream_fd = fileno(stream);

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real_vfscanf)(stream, format, args);
    int errno_value = errno;
    err_obj = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "fscanf";
    FuncInfoMessage func_msg;

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("stream");
    tmp_arg->set_value(std::to_string(stream_fd));

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    return ret;
}

/**
 * Interposition function for __isoc99_scanf
 */
extern "C" int __isoc99_scanf(const char *format, ...)
{
    static __ISOC99_VSCANF_POINTER real___isoc99_vscanf = NULL;
    TrackErrno err_obj(errno);

    if (!real___isoc99_vscanf)
    {
        real___isoc99_vscanf =
            (__ISOC99_VSCANF_POINTER)ProcUtils::get_sym_addr("__isoc99_vscanf");
    }

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real___isoc99_vscanf)(format, args);

        err_obj = errno;
        va_end(args);

        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real___isoc99_vscanf)(format, args);
    int errno_value = errno;
    err_obj = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "scanf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    return ret;
}

/**
 * Interposition function for __isoc99_fscanf
 */
extern "C" int __isoc99_fscanf(FILE *stream, const char *format, ...)
{
    static __ISOC99_VFSCANF_POINTER real___isoc99_vfscanf = NULL;
    TrackErrno err_obj(errno);

    if (!real___isoc99_vfscanf)
    {
        real___isoc99_vfscanf =
            (__ISOC99_VFSCANF_POINTER)ProcUtils::get_sym_addr(
                                            "__isoc99_vfscanf");
    }

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        errno = 0;
        int ret = (*real___isoc99_vfscanf)(stream, format, args);

        err_obj = errno;
        va_end(args);

        return ret;
    }

    int stream_fd = -1;
    if (stream) stream_fd = fileno(stream);

    uint64_t start_time = ProcUtils::get_time();

    errno = 0;
    int ret = (*real___isoc99_vfscanf)(stream, format, args);
    int errno_value = errno;
    err_obj = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "fscanf";
    FuncInfoMessage func_msg;

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("stream");
    tmp_arg->set_value(std::to_string(stream_fd));

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    return ret;
}
