#include <cstdint>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/limits.h>
#include <pwd.h>
#include <signal.h>
#include <stdarg.h>
#include <sys/socket.h>
#include <string>

#include "log.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "track_errno.h"
#include "common_macros.h"
#include "sys_util.h"
#include "file_hash.h"
#include "message_util.h"


#define GET_MODE                    \
    mode_t mode = 0;                \
    if ((flags & O_CREAT) != 0)     \
    {                               \
        va_list arg;                \
        va_start(arg, flags);       \
        mode = va_arg(arg, mode_t); \
        va_end(arg);                \
    }

enum fcntl_arg_fmt_t {NO_ARG, INT_ARG, FLOCK_ARG, OWN_EX_ARG};

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

    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(int, ret, real_open, pathname, flags, mode);
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(int, ret, real_open, pathname, flags, mode);
        return ret;
    }

    uint64_t start_time = SysUtil::get_time();

    CALL_FUNC(int, ret, real_open, pathname, flags, mode);

    int errno_value = errno;
    uint64_t end_time = SysUtil::get_time();

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
        tmp_arg->set_value(SysUtil::canonicalise_path(pathname, pathname_buf));
    }

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("flags");

    char flags_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(flags, flags_buf));

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("mode");

    char mode_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(mode, mode_buf));

#ifdef COMPUTE_GIT_HASH
    if (ret >= 0)
    {
        char git_hash[64] = "";
        if (FileHash::get_git_hash(ret, git_hash))
            func_msg->set_git_hash(git_hash);
    }
#endif

    set_func_info_msg(func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::inside_opus(!comm_ret);
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

template <typename T>
static int __openat_internal(int dirfd, const char* pathname, int flags,
                        const char *func_name, T real_openat, mode_t mode)
{
    TrackErrno err_obj(errno);

    if (!real_openat)
        real_openat = (T)ProcUtils::get_sym_addr(func_name);

    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(int, ret, real_openat, dirfd, pathname, flags, mode);
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(int, ret, real_openat, dirfd, pathname, flags, mode);
        return ret;
    }

    uint64_t start_time = SysUtil::get_time();

    CALL_FUNC(int, ret, real_openat, dirfd, pathname, flags, mode);

    int errno_value = errno;
    uint64_t end_time = SysUtil::get_time();

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg) return ret;

    KVPair* tmp_arg;

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("dirfd");
    char dirfd_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(dirfd, dirfd_buf));

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("pathname");
    if (pathname)
    {
        char pathname_buf[PATH_MAX + 1] = "";
        tmp_arg->set_value(SysUtil::canonicalise_path(pathname, pathname_buf));
    }

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("flags");

    char flags_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(flags, flags_buf));

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("mode");

    char mode_buf[MAX_INT32_LEN] = "";
    tmp_arg->set_value(ProcUtils::opus_itoa(mode, mode_buf));


    /* Get the file path from the new file descriptor */
    if (ret >= 0)
    {
        char file_path[PATH_MAX + 1] = "";
        if (SysUtil::get_path_from_fd(ret, file_path))
        {
            tmp_arg = func_msg->add_args();
            tmp_arg->set_key("file_path");
            tmp_arg->set_value(file_path);
        }
    }

#ifdef COMPUTE_GIT_HASH
    if (ret >=0)
    {
        char git_hash[64] = "";
        if (FileHash::get_git_hash(ret, git_hash))
            func_msg->set_git_hash(git_hash);
    }
#endif

    set_func_info_msg(func_msg, func_name, ret,
                        start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::inside_opus(!comm_ret);
    func_msg->Clear();

    return ret;
}

extern "C" int openat(int dirfd, const char *pathname, int flags, ...)
{
    static OPENAT_POINTER real_openat = NULL;

    GET_MODE;
    return __openat_internal(dirfd, pathname, flags, "openat", real_openat, mode);
}


extern "C" int openat64(int dirfd, const char *pathname, int flags, ...)
{
    static OPENAT64_POINTER real_openat64 = NULL;

    GET_MODE;
    return __openat_internal(dirfd, pathname, flags, "openat64", real_openat64, mode);
}

/**
 *  Macro to call real fcntl with different
 *  arguments based in argument format
 */
#define FCNTL_CALL_FUNC                                               \
    errno = 0;                                                        \
    if (argfmt == NO_ARG) {                                           \
        ret = real_fcntl(filedes, cmd);                               \
    } else if (argfmt == INT_ARG) {                                   \
        ret = real_fcntl(filedes, cmd, int_arg);                      \
    } else if (argfmt == FLOCK_ARG) {                                 \
        ret = real_fcntl(filedes, cmd, flock_arg);                    \
    } else if (argfmt == OWN_EX_ARG) {                                \
        ret = real_fcntl(filedes, cmd, own_ex_arg);                   \
    }                                                                 \
    err_obj = errno;


static int inner_fcntl(int filedes, int cmd, va_list arg, fcntl_arg_fmt_t argfmt)
{
    static FCNTL_POINTER real_fcntl = NULL;
    int int_arg = 0;
    struct flock *flock_arg = NULL;
    struct f_owner_ex *own_ex_arg = NULL;
    int ret = -1;
    TrackErrno err_obj(errno);

    if (!real_fcntl)
        real_fcntl = (FCNTL_POINTER)ProcUtils::get_sym_addr("fcntl");

    if (argfmt == INT_ARG) {
        int_arg = va_arg(arg, int);
    } else if (argfmt == FLOCK_ARG) {
        flock_arg = va_arg(arg, struct flock*);
    } else if (argfmt == OWN_EX_ARG) {
        own_ex_arg = va_arg(arg, struct f_owner_ex*);
    }
    va_end(arg);

    if (ProcUtils::inside_opus(true))
    {
        FCNTL_CALL_FUNC
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        FCNTL_CALL_FUNC
        return ret;
    }

    uint64_t start_time = SysUtil::get_time();

    FCNTL_CALL_FUNC

    int errno_value = errno;
    uint64_t end_time = SysUtil::get_time();

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg) return ret;

    KVPair *tmp_arg;
    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("filedes");

    char filedes_buf[MAX_INT32_LEN];
    tmp_arg->set_value(ProcUtils::opus_itoa(filedes, filedes_buf));

    tmp_arg = func_msg->add_args();
    tmp_arg->set_key("cmd");

    char cmd_buf[MAX_INT32_LEN];
    tmp_arg->set_value(ProcUtils::opus_itoa(cmd, cmd_buf));

    if(argfmt == INT_ARG){
        tmp_arg = func_msg->add_args();
        tmp_arg->set_key("arg");

        char arg_buf[MAX_INT32_LEN];
        tmp_arg->set_value(ProcUtils::opus_itoa(int_arg, arg_buf));
    }

    set_func_info_msg(func_msg, "fcntl", ret,
                      start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::inside_opus(!comm_ret);
    func_msg->Clear();

    return ret;
}

extern "C" int fcntl(int filedes, int cmd, ...)
{
    va_list args;
    va_start(args, cmd);
    switch(cmd){
        case F_DUPFD:
        case F_DUPFD_CLOEXEC:
        case F_SETFD:
        case F_SETFL:
        case F_SETOWN:
        case F_SETSIG:
        case F_SETLEASE:
        case F_NOTIFY:
        case F_SETPIPE_SZ:
            return inner_fcntl(filedes, cmd, args, INT_ARG);

        case F_GETFD:
        case F_GETFL:
        case F_GETOWN:
        case F_GETSIG:
        case F_GETLEASE:
        case F_GETPIPE_SZ:
            return inner_fcntl(filedes, cmd, args, NO_ARG);

        case F_GETLK:
        case F_SETLK:
        case F_SETLKW:
            return inner_fcntl(filedes, cmd, args, FLOCK_ARG);

        case F_GETOWN_EX:
        case F_SETOWN_EX:
            return inner_fcntl(filedes, cmd, args, OWN_EX_ARG);

        default:
            errno = -EINVAL;
            return -1;
    }

}
