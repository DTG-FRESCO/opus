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


extern "C" int open(const char *pathname, int flags, ...)
{
    std::string func_name = "open";
    static OPEN_POINTER real_open = NULL;

    if (!real_open)
        real_open = (OPEN_POINTER)ProcUtils::get_sym_addr(func_name);

    mode_t mode;

    if ((flags & O_CREAT) != 0)
    {
        va_list arg;
        va_start(arg, flags);
        mode = va_arg(arg, mode_t);
        va_end(arg);
    }

    if (ProcUtils::test_and_set_flag(true))
    {
        if ((flags & O_CREAT) != 0)
        {
            return (*real_open)(pathname, flags, mode);
        }
        else
        {
            return (*real_open)(pathname, flags);
        }
    }

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret;
    if ((flags & O_CREAT) != 0)
    {
        ret = (*real_open)(pathname, flags, mode);
    }
    else
    {
        ret = (*real_open)(pathname, flags);
    }
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    FuncInfoMessage func_msg;

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("pathname");
    std::string pathname_value;
    if (pathname) pathname_value = pathname;
    pathname_value = ProcUtils::canonicalise_path(pathname_value);
    tmp_arg->set_value(pathname_value);

    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("flags");
    tmp_arg->set_value(std::to_string(flags));

    if ((flags & O_CREAT) != 0)
    {
        tmp_arg = func_msg.add_args();
        tmp_arg->set_key("mode");
        tmp_arg->set_value(std::to_string(mode));
    }

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int open64(const char *pathname, int flags, ...)
{
    std::string func_name = "open64";
    static OPEN64_POINTER real_open64 = NULL;

    if (!real_open64)
        real_open64 = (OPEN64_POINTER)ProcUtils::get_sym_addr(func_name);

    mode_t mode;

    if ((flags & O_CREAT) != 0)
    {
        va_list arg;
        va_start(arg, flags);
        mode = va_arg(arg, mode_t);
        va_end(arg);
    }

    if (ProcUtils::test_and_set_flag(true))
    {
        if ((flags & O_CREAT) != 0)
        {
            return (*real_open64)(pathname, flags, mode);
        }
        else
        {
            return (*real_open64)(pathname, flags);
        }
    }

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret;
    if ((flags & O_CREAT) != 0)
    {
        ret = (*real_open64)(pathname, flags, mode);
    }
    else
    {
        ret = (*real_open64)(pathname, flags);
    }
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    FuncInfoMessage func_msg;

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("pathname");
    std::string pathname_value;
    if (pathname) pathname_value = pathname;
    pathname_value = ProcUtils::canonicalise_path(pathname_value);
    tmp_arg->set_value(pathname_value);

    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("flags");
    tmp_arg->set_value(std::to_string(flags));

    if ((flags & O_CREAT) != 0)
    {
        tmp_arg = func_msg.add_args();
        tmp_arg->set_key("mode");
        tmp_arg->set_value(std::to_string(mode));
    }

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int printf(const char *format, ...)
{
    static VPRINTF_POINTER real_vprintf = NULL;

    if (!real_vprintf)
        real_vprintf = (VPRINTF_POINTER)ProcUtils::get_sym_addr("vprintf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real_vprintf)(format, args);
        va_end(args);
        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret = (*real_vprintf)(format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "printf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int scanf(const char *format, ...)
{
    static VSCANF_POINTER real_vscanf = NULL;

    if (!real_vscanf)
        real_vscanf = (VSCANF_POINTER)ProcUtils::get_sym_addr("vscanf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real_vscanf)(format, args);
        va_end(args);
        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret = (*real_vscanf)(format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "scanf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int fprintf(FILE *stream, const char *format, ...)
{
    static VFPRINTF_POINTER real_vfprintf = NULL;

    if (!real_vfprintf)
        real_vfprintf = (VFPRINTF_POINTER)ProcUtils::get_sym_addr("vfprintf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real_vfprintf)(stream, format, args);
        va_end(args);
        return ret;
    }

    int stream_fd = -1;
    if (stream) stream_fd = fileno(stream);

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret = (*real_vfprintf)(stream, format, args);
    int errno_value = errno;

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
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int fscanf(FILE *stream, const char *format, ...)
{
    static VFSCANF_POINTER real_vfscanf = NULL;

    if (!real_vfscanf)
        real_vfscanf = (VFSCANF_POINTER)ProcUtils::get_sym_addr("vfscanf");

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real_vfscanf)(stream, format, args);
        va_end(args);
        return ret;
    }

    int stream_fd = -1;
    if (stream) stream_fd = fileno(stream);

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret = (*real_vfscanf)(stream, format, args);
    int errno_value = errno;

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
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int __isoc99_scanf(const char *format, ...)
{
    static __ISOC99_VSCANF_POINTER real___isoc99_vscanf = NULL;

    if (!real___isoc99_vscanf)
    {
        real___isoc99_vscanf =
            (__ISOC99_VSCANF_POINTER)ProcUtils::get_sym_addr("__isoc99_vscanf");
    }

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real___isoc99_vscanf)(format, args);
        va_end(args);
        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret = (*real___isoc99_vscanf)(format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "scanf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int __isoc99_fscanf(FILE *stream, const char *format, ...)
{
    static __ISOC99_VFSCANF_POINTER real___isoc99_vfscanf = NULL;

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
        int ret = (*real___isoc99_vfscanf)(stream, format, args);
        va_end(args);
        return ret;
    }

    int stream_fd = -1;
    if (stream) stream_fd = fileno(stream);

    uint64_t start_time = ProcUtils::get_time();
    
    errno = 0;
    int ret = (*real___isoc99_vfscanf)(stream, format, args);
    int errno_value = errno;

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
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}
