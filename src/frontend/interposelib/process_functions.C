#include <limits.h>
#include <stdlib.h>
#include <link.h>
#include <vector>
#include <stdexcept>
#include "signal_utils.h"
#include "signal_handler.h"

typedef pid_t (*FORK_POINTER)(void);
typedef int (*EXECV_POINTER)(const char*, char *const[]);
typedef int (*EXECVP_POINTER)(const char*, char *const argv[]);
typedef int (*EXECVPE_POINTER)(const char*, char *const[], char *const[]);
typedef int (*EXECVE_POINTER)(const char*, char *const[], char *const[]);
typedef int (*FEXECVE_POINTER)(int, char *const[], char *const[]);
typedef void* (*DLOPEN_POINTER)(const char *, int);
typedef sighandler_t (*SIGNAL_POINTER)(int signum, sighandler_t handler);
typedef int (*SIGACTION_POINTER)(int signum, const struct sigaction *act,
                                struct sigaction *oldact);
typedef void (*EXIT_POINTER)(int);  // _exit and _Exit

/* Initialize function pointers */
static FORK_POINTER real_fork = NULL;
static EXECV_POINTER real_execv = NULL;
static EXECVP_POINTER real_execvp = NULL;
static EXECVPE_POINTER real_execvpe = NULL;
static EXECVE_POINTER real_execve = NULL;
static FEXECVE_POINTER real_fexecve = NULL;
static DLOPEN_POINTER real_dlopen = NULL;
static SIGNAL_POINTER real_signal = NULL;
static SIGACTION_POINTER real_sigaction = NULL;
static EXIT_POINTER real__exit = NULL;
static EXIT_POINTER real__Exit = NULL;


static void get_lib_real_path(void *handle, std::string* real_path)
{
    struct link_map *link;

    if (dlinfo(handle, RTLD_DI_LINKMAP, &link) < 0)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, dlerror());
        return;
    }

    char *path = realpath(link->l_name, NULL);
    if (!path)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
        return;
    }

    *real_path = path;
}

static inline void exit_program(EXIT_POINTER exit_ptr,
                const char *exit_str, const int status)
{
    char *error = NULL;
    dlerror();

    if (!exit_ptr)
    {
        DLSYM_CHECK(exit_ptr = (EXIT_POINTER)dlsym(RTLD_NEXT, exit_str));
    }

    if (ProcUtils::test_and_set_flag(true))
        (*exit_ptr)(status);

    FuncInfoMessage func_msg;
    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("status");
    tmp_arg->set_value(std::to_string(status));

    std::string func_name = exit_str;
    uint64_t start_time = ProcUtils::get_time();
    uint64_t end_time = 0;  // function does not return
    int errno_value = 0;

    set_func_info_msg(&func_msg, func_name, start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    UDSCommClient::get_instance()->shutdown();

    (*exit_ptr)(status);

    // Will never reach here
    ProcUtils::test_and_set_flag(false);
}


static inline void set_old_act_data(const SignalHandler* const prev,
                                    struct sigaction *oldact)
{
    void *prev_handler = prev->get_handler();

    if (oldact->sa_flags & SA_SIGINFO)
        oldact->sa_sigaction = reinterpret_cast<SA_SIGACTION_PTR>(prev_handler);
    else
        oldact->sa_handler = reinterpret_cast<sighandler_t>(prev_handler);
}

static void setup_new_uds_connection()
{
    ProcUtils::test_and_set_flag(true);

    DEBUG_LOG("[%s:%d]: Setting up new UDS connection\n", __FILE__, __LINE__);

    /* Close inherited connection */
    UDSCommClient::get_instance()->close_connection();

    /* Open a new connection */
    if (!UDSCommClient::get_instance()->reconnect())
    {
        DEBUG_LOG("[%s:%d]: Reconnect failed\n", __FILE__, __LINE__);
        return;
    }

    ProcUtils::send_startup_message();
    ProcUtils::test_and_set_flag(false);
}

/* Adds environment variables related to OPUS if missing */
static void copy_env_vars(char **envp, std::vector<char*>* env_vec_ptr)
{
    char *env = NULL;
    bool found_ld_preload = false;
    std::vector<char*>& env_vec = *env_vec_ptr;

    if (envp)
    {
        std::string env_str;
        std::string match_str = "LD_PRELOAD=";
        while ((env = *envp) != NULL)
        {
            env_vec.push_back(env);
            ++envp;

            env_str = env;
            int64_t found_pos = env_str.find(match_str);

            if (found_pos != (int64_t)std::string::npos)
            {
                found_ld_preload = true;
                break;
            }
        }
    }

    /* Add the LD_PRELOAD path if not already present */
    if (!found_ld_preload)
    {
        char ld_preload_buf[PATH_MAX];
        memset(ld_preload_buf, 0, sizeof(ld_preload_buf));

        std::string preload_path = ProcUtils::get_preload_path();
        std::string preload_str = "LD_PRELOAD=" + preload_path;

        DEBUG_LOG("[%s:%d]: Added LD_PRELOAD path: %s\n",
                    __FILE__, __LINE__, preload_str.c_str());

        env_vec.push_back(const_cast<char*>(preload_str.c_str()));
    }

    /* Add the UDS path for communcation with backend */
    std::string uds_path;
    ProcUtils::get_uds_path(&uds_path);

    std::string uds_str = "OPUS_UDS_PATH=" + uds_path;
    env_vec.push_back(const_cast<char*>(uds_str.c_str()));

    DEBUG_LOG("[%s:%d]: Added OPUS_UDS_PATH: %s\n",
                __FILE__, __LINE__, uds_str.c_str());
}

extern "C" int execl(const char *path, const char *arg, ...)
{
    va_list lst;
    char *error = NULL;
    std::vector<char*> arg_vec;

    /* Read the argument list */
    arg_vec.push_back(const_cast<char*>(arg));
    va_start(lst, arg);

    char *val = NULL;
    while ((val = va_arg(lst, char*)) != 0)
        arg_vec.push_back(val);

    arg_vec.push_back(NULL);
    va_end(lst);

    /* Get the symbol address and store it */
    dlerror();
    if (!real_execv)
        DLSYM_CHECK(real_execv = (EXECV_POINTER)dlsym(RTLD_NEXT, "execv"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execv)(path, &arg_vec[0]);

    /* Send pre function call generic message */
    std::string desc = "execl";
    send_pre_func_generic_msg(desc);

    /* Call the original execv */
    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execv)(path, &arg_vec[0]);

    /* This part will execute only if exec fails */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("path");
    arg_kv->set_value(path);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int execlp(const char *file, const char *arg, ...)
{
    va_list lst;
    char *error = NULL;
    std::vector<char*> arg_vec;

    /* Read the argument list */
    arg_vec.push_back(const_cast<char*>(arg));
    va_start(lst, arg);

    char *val = NULL;
    while ((val = va_arg(lst, char*)) != 0)
        arg_vec.push_back(val);

    arg_vec.push_back(NULL);
    va_end(lst);

    /* Get the symbol address and store it */
    dlerror();
    if (!real_execvp)
        DLSYM_CHECK(real_execvp = (EXECVP_POINTER)dlsym(RTLD_NEXT, "execvp"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execvp)(file, &arg_vec[0]);

    /* Send pre function call generic message */
    std::string desc = "execlp";
    send_pre_func_generic_msg(desc);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execvp)(file, &arg_vec[0]);

    /* This part will execute only if exec fails */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(file);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int execle(const char *path, const char *arg,
                            .../*, char *const envp[]*/)
{
    va_list lst;
    char *error = NULL;
    std::vector<char*> arg_vec;

    /* Read the argument list */
    arg_vec.push_back(const_cast<char*>(arg));
    va_start(lst, arg);

    char *val = NULL;
    while ((val = va_arg(lst, char*)) != 0)
        arg_vec.push_back(val);

    arg_vec.push_back(NULL);

    std::vector<char*> env_vec;
    char **envp = va_arg(lst, char**);
    va_end(lst);

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(envp, &env_vec);
    env_vec.push_back(NULL);

    /* Get the symbol address and store it */
    dlerror();
    if (!real_execvpe)
        DLSYM_CHECK(real_execvpe = \
                    (EXECVPE_POINTER)dlsym(RTLD_NEXT, "execvpe"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execvpe)(path, &arg_vec[0], &env_vec[0]);

    /* Send pre function call generic message */
    std::string desc = "execle";
    send_pre_func_generic_msg(desc);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execvpe)(path, &arg_vec[0], &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("path");
    arg_kv->set_value(path);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int execv(const char *path, char *const argv[])
{
    char *error = NULL;
    dlerror();

    /* Get the symbol address and store it */
    if (!real_execv)
        DLSYM_CHECK(real_execv = (EXECV_POINTER)dlsym(RTLD_NEXT, "execv"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execv)(path, argv);

    /* Send pre function call generic message */
    std::string desc = "execv";
    send_pre_func_generic_msg(desc);

    /* Call the original execv */
    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execv)(path, argv);

    /* This part will execute only if exec fails */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("path");
    arg_kv->set_value(path);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int execvp(const char *file, char *const argv[])
{
    char *error = NULL;
    dlerror();

    /* Get the symbol address and store it */
    if (!real_execvp)
        DLSYM_CHECK(real_execvp = (EXECVP_POINTER)dlsym(RTLD_NEXT, "execvp"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execvp)(file, argv);

    /* Send pre function call generic message */
    std::string desc = "execvp";
    send_pre_func_generic_msg(desc);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execvp)(file, argv);

    /* This part will execute only if exec fails */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(file);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int execvpe(const char *file, char *const argv[], char *const envp[])
{
    char *error = NULL;
    std::vector<char*> env_vec;

    dlerror();

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    /* Get the symbol address and store it */
    if (!real_execvpe)
        DLSYM_CHECK(real_execvpe = \
                (EXECVPE_POINTER)dlsym(RTLD_NEXT, "execvpe"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execvpe)(file, argv, &env_vec[0]);

    /* Send pre function call generic message */
    std::string desc = "execvpe";
    send_pre_func_generic_msg(desc);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execvpe)(file, argv, &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(file);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int execve(const char *filename,
                        char *const argv[],
                        char *const envp[])
{
    char *error = NULL;
    std::vector<char*> env_vec;

    dlerror();

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    /* Get the symbol address and store it */
    if (!real_execvpe)
        DLSYM_CHECK(real_execve = \
                (EXECVE_POINTER)dlsym(RTLD_NEXT, "execve"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execve)(filename, argv, &env_vec[0]);

    /* Send pre function call generic message */
    std::string desc = "execve";
    send_pre_func_generic_msg(desc);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execve)(filename, argv, &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(filename);

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}

extern "C" int fexecve(int fd, char *const argv[], char *const envp[])
{
    char *error = NULL;
    std::vector<char*> env_vec;

    dlerror();

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    /* Get the symbol address and store it */
    if (!real_fexecve)
        DLSYM_CHECK(real_fexecve = \
                    (FEXECVE_POINTER)dlsym(RTLD_NEXT, "fexecve"));

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_fexecve)(fd, argv, &env_vec[0]);

    /* Send pre function call generic message */
    std::string desc = "fexecve";
    send_pre_func_generic_msg(desc);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_fexecve)(fd, argv, &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("fd");
    arg_kv->set_value(std::to_string(fd));

    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(false);

    return ret;
}


extern "C" pid_t fork(void)
{
    char *error = NULL;
    dlerror();

    /* Get the symbol address and store it */
    if (!real_fork)
        DLSYM_CHECK(real_fork = (FORK_POINTER)dlsym(RTLD_NEXT, "fork"));

    if (ProcUtils::test_and_set_flag(true))
        return (*real_fork)();

    std::string func_name = "fork";
    uint64_t start_time = ProcUtils::get_time();

    pid_t pid = (*real_fork)();
    if (pid == 0)
    {
        /* Child process */
        setup_new_uds_connection();
        return pid;
    }

    /* Parent process */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;

    set_func_info_msg(&func_msg, func_name, pid,
                start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);

    return pid;
}

extern "C" void* dlopen(const char * filename, int flag)
{
    char *error = NULL;
    dlerror();

    if (!real_dlopen)
        DLSYM_CHECK(real_dlopen = (DLOPEN_POINTER)dlsym(RTLD_NEXT, "dlopen"));

    if (ProcUtils::test_and_set_flag(true))
        return (*real_dlopen)(filename, flag);


    void *handle = (*real_dlopen)(filename, flag);
    if (handle)
    {
        std::string real_path;
        std::string md5_sum;

        get_lib_real_path(handle, &real_path);
        ProcUtils::get_md5_sum(real_path, &md5_sum);

        LibInfoMessage lib_info_msg;
        KVPair *kv_args = lib_info_msg.add_library();
        kv_args->set_key(real_path);
        kv_args->set_value(md5_sum);

        set_header_and_send(lib_info_msg, PayloadType::LIBINFO_MSG);
    }

    ProcUtils::test_and_set_flag(false);
    return handle;
}

extern "C" sighandler_t signal(int signum, sighandler_t handler)
{
    char *error = NULL;
    dlerror();

    /* Get the symbol address and store it */
    if (!real_signal)
        DLSYM_CHECK(real_signal = (SIGNAL_POINTER)dlsym(RTLD_NEXT, "signal"));

    /* We are within our own library */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_signal)(signum, handler);

    sighandler_t ret = NULL;
    SignalHandler *sh_obj = NULL;
    SignalHandler *prev_handler = NULL;

    try
    {
        sh_obj = new SAHandler(signum, handler);
        sighandler_t signal_callback =
                    SignalUtils::opus_type_one_signal_handler;

        if (handler == SIG_IGN) signal_callback = handler;

        ret = (*real_signal)(signum, signal_callback);
        if (ret == SIG_ERR)
            throw std::runtime_error("SIG_ERR");

        prev_handler = SignalUtils::add_signal_handler(signum, sh_obj);

        if (prev_handler)
            ret = reinterpret_cast<sighandler_t>(prev_handler->get_handler());
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        if (sh_obj) delete sh_obj;
    }

    if (prev_handler) delete prev_handler;

    ProcUtils::test_and_set_flag(false);
    return ret;
}


extern "C" int sigaction(int signum,
                        const struct sigaction *act,
                        struct sigaction *oldact)
{
    char *error = NULL;
    dlerror();

    /* Get the symbol address and store it */
    if (!real_sigaction)
        DLSYM_CHECK(real_sigaction =
                        (SIGACTION_POINTER)dlsym(RTLD_NEXT, "sigaction"));

    /* We are within our own library */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_sigaction)(signum, act, oldact);

    int ret = 0;
    SignalHandler *sh_obj = NULL;
    SignalHandler *prev_handler = NULL;

    // Cast away the constness
    struct sigaction *sa = const_cast<struct sigaction *>(act);

    try
    {
        if (sa->sa_flags & SA_SIGINFO)  // Type two handler
        {
            sh_obj = new SASigaction(signum, sa);
            sa->sa_sigaction = SignalUtils::opus_type_two_signal_handler;
        }
        else  // Type one handler
        {
            sh_obj = new SAHandler(signum, sa);

            if (sa->sa_handler != SIG_IGN)
                sa->sa_handler = SignalUtils::opus_type_one_signal_handler;
        }

        ret = (*real_sigaction)(signum, sa, oldact);
        if (ret < 0)
            throw std::runtime_error(strerror(errno));

        prev_handler = SignalUtils::add_signal_handler(signum, sh_obj);

        if (oldact && prev_handler) set_old_act_data(prev_handler, oldact);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        if (sh_obj) delete sh_obj;
    }

    if (prev_handler) delete prev_handler;

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" void _exit(int status)
{
    exit_program(real__exit, "_exit", status);
}

extern "C" void _Exit(int status)
{
    exit_program(real__Exit, "_Exit", status);
}
