typedef int (*OPEN_PTR)(const char*, int, ...);
typedef int (*VPRINTF_PTR)(const char*, va_list);
typedef int (*VFPRINTF_PTR)(FILE *, const char*, va_list);
typedef int (*VSCANF_PTR)(const char*, va_list);
typedef int (*VFSCANF_PTR)(FILE *, const char*, va_list);


static OPEN_PTR real_open = NULL;
static OPEN_PTR real_open64 = NULL;


extern "C" int open(const char *pathname, int flags, ...)
{
    char *error = NULL;
    dlerror();

    if (!real_open)
    {
        DLSYM_CHECK(real_open = (OPEN_PTR)dlsym(RTLD_NEXT, "open"));
    }

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
    std::string func_name = "open";

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("pathname");
    tmp_arg->set_value(pathname);

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
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int open64(const char *pathname, int flags, ...)
{
    char *error = NULL;
    dlerror();

    if (!real_open64)
    {
        DLSYM_CHECK(real_open64 = (OPEN_PTR)dlsym(RTLD_NEXT, "open64"));
    }

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
    std::string func_name = "open64";

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("pathname");
    tmp_arg->set_value(pathname);

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
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int printf(const char *format, ...)
{
    char *error = NULL;
    dlerror();

    if (!real_vprintf)
    {
        DLSYM_CHECK(real_vprintf = (VPRINTF_PTR)dlsym(RTLD_NEXT, "vprintf"));
    }

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real_vprintf)(format, args);
        va_end(args);
        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();

    int ret = (*real_vprintf)(format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "printf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int scanf(const char *format, ...)
{
    char *error = NULL;
    dlerror();

    if (!real_vscanf)
    {
        DLSYM_CHECK(real_vscanf = (VSCANF_PTR)dlsym(RTLD_NEXT, "vscanf"));
    }

    va_list args;
    va_start(args, format);

    if (ProcUtils::test_and_set_flag(true))
    {
        int ret = (*real_vscanf)(format, args);
        va_end(args);
        return ret;
    }

    uint64_t start_time = ProcUtils::get_time();

    int ret = (*real_vscanf)(format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "scanf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int fprintf(FILE *stream, const char *format, ...)
{
    char *error = NULL;
    dlerror();

    if (!real_vfprintf)
    {
        DLSYM_CHECK(real_vfprintf = (VFPRINTF_PTR)dlsym(RTLD_NEXT, "vfprintf"));
    }

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
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int fscanf(FILE *stream, const char *format, ...)
{
    char *error = NULL;
    dlerror();

    if (!real_vfscanf)
    {
        DLSYM_CHECK(real_vfscanf = (VFSCANF_PTR)dlsym(RTLD_NEXT, "vfscanf"));
    }

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

    int ret = (*real_vfscanf)(stream, format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    FuncInfoMessage func_msg;
    std::string func_name = "fscanf";

    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("stream");
    tmp_arg->set_value(std::to_string(stream_fd));

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int __isoc99_scanf(const char *format, ...)
{
    char *error = NULL;
    dlerror();

    if (!real___isoc99_vscanf)
    {
        DLSYM_CHECK(real___isoc99_vscanf =
                (VSCANF_PTR)dlsym(RTLD_NEXT, "__isoc99_vscanf"));
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

    int ret = (*real___isoc99_vscanf)(format, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    va_end(args);

    std::string func_name = "scanf";
    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, ret,
                        start_time, end_time, errno_value);
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" int __isoc99_fscanf(FILE *stream, const char *format, ...)
{
    char *error = NULL;
    dlerror();

    if (!real___isoc99_vfscanf)
    {
        DLSYM_CHECK(real___isoc99_vfscanf =
                (VFSCANF_PTR)dlsym(RTLD_NEXT, "__isoc99_vfscanf"));
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
    send_func_info_msg(func_msg);

    ProcUtils::test_and_set_flag(false);
    return ret;
}
