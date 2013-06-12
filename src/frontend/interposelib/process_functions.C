#include <limits.h>
#include <stdlib.h>
#include <link.h>
#include <cstdint>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <string>
#include <vector>
#include <stdexcept>
#include "log.h"
#include "signal_utils.h"
#include "signal_handler.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "message_util.h"


typedef void* (*PTHREAD_HANDLER)(void*);

struct OPUSThreadData
{
    PTHREAD_HANDLER real_handler;
    void *real_args;
};

/*
    Called by all threads that exit.
    Sends a thread exit generic
    message to the backend.
*/
static void opus_thread_cleanup_handler(void *cleanup_args)
{
    send_generic_msg(GenMsgType::THREAD_EXIT,
                std::to_string(ProcUtils::gettid()));

    int thread_count = ProcUtils::decr_appln_thread_count();
    if (thread_count == 0)
    {
        if (ProcUtils::comm_thread_obj)
            ProcUtils::comm_thread_obj->shutdown_thread();
    }
}

/*
    Wrapper thread routine for
    the real thread handler
*/
static void* opus_thread_start_routine(void *args)
{
    ProcUtils::incr_appln_thread_count();

    OPUSThreadData *opus_thread_data = static_cast<OPUSThreadData*>(args);

    PTHREAD_HANDLER real_handler = opus_thread_data->real_handler;
    void *real_args = opus_thread_data->real_args;

    delete opus_thread_data; // don't need this pointer anymore

    pthread_cleanup_push(opus_thread_cleanup_handler, NULL);

    send_generic_msg(GenMsgType::THREAD_START,
                    std::to_string(ProcUtils::gettid()));

    ProcUtils::test_and_set_flag(false);
    void *ret = real_handler(real_args);
    ProcUtils::test_and_set_flag(true);

    return ret;
    pthread_cleanup_pop(1); // Added to avoid compilation error
}

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

static inline void exit_program(const char *exit_str, const int status)
{
    std::string func_name = exit_str;
    static _EXIT_POINTER exit_ptr = NULL;

    if (!exit_ptr)
        exit_ptr = (_EXIT_POINTER)ProcUtils::get_sym_addr(func_name);

    if (ProcUtils::test_and_set_flag(true))
        (*exit_ptr)(status);

    FuncInfoMessage func_msg;
    KVPair* tmp_arg;
    tmp_arg = func_msg.add_args();
    tmp_arg->set_key("status");
    tmp_arg->set_value(std::to_string(status));

    uint64_t start_time = ProcUtils::get_time();
    uint64_t end_time = 0;  // function does not return
    int errno_value = 0;

    set_func_info_msg(&func_msg, func_name, start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    if (ProcUtils::comm_thread_obj)
        ProcUtils::comm_thread_obj->shutdown_thread();

    (*exit_ptr)(status);

    // Will never reach here
    ProcUtils::test_and_set_flag(false);
}


static inline void set_old_act_data(void* prev, struct sigaction *oldact)
{
    if (oldact->sa_flags & SA_SIGINFO)
        oldact->sa_sigaction = reinterpret_cast<SA_SIGACTION_PTR>(prev);
    else
        oldact->sa_handler = reinterpret_cast<sighandler_t>(prev);
}

static void setup_new_uds_connection()
{
    ProcUtils::test_and_set_flag(true);

    SignalUtils::reset();
    ProcUtils::reset();

    if (ProcUtils::comm_thread_obj)
    {
        ProcUtils::comm_thread_obj->reset_instance();
        ProcUtils::comm_thread_obj = NULL;
    }

    ProcUtils::comm_thread_obj = CommThread::get_instance();
    if (!ProcUtils::comm_thread_obj)
    {
        DEBUG_LOG("[%s:%d]: Could not instantiate communication thread\n",
                        __FILE__, __LINE__);
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

        std::string preload_path;
        ProcUtils::get_preload_path(&preload_path);

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
    std::vector<char*> arg_vec;

    /* Read the argument list */
    arg_vec.push_back(const_cast<char*>(arg));
    va_start(lst, arg);

    char *val = NULL;
    while ((val = va_arg(lst, char*)) != 0)
        arg_vec.push_back(val);

    arg_vec.push_back(NULL);
    va_end(lst);

    std::string func_name = "execv";
    static EXECV_POINTER real_execv = NULL;

    /* Get the symbol address and store it */
    if (!real_execv)
        real_execv = (EXECV_POINTER)ProcUtils::get_sym_addr(func_name);

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
    std::vector<char*> arg_vec;

    /* Read the argument list */
    arg_vec.push_back(const_cast<char*>(arg));
    va_start(lst, arg);

    char *val = NULL;
    while ((val = va_arg(lst, char*)) != 0)
        arg_vec.push_back(val);

    arg_vec.push_back(NULL);
    va_end(lst);

    std::string func_name = "execvp";
    static EXECVP_POINTER real_execvp = NULL;

    /* Get the symbol address and store it */
    if (!real_execvp)
        real_execvp = (EXECVP_POINTER)ProcUtils::get_sym_addr(func_name);

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

    std::string func_name = "execvpe";
    static EXECVPE_POINTER real_execvpe = NULL;

    /* Get the symbol address and store it */
    if (!real_execvpe)
        real_execvpe = (EXECVPE_POINTER)ProcUtils::get_sym_addr(func_name);

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
    std::string func_name = "execv";
    static EXECV_POINTER real_execv = NULL;

    /* Get the symbol address and store it */
    if (!real_execv)
        real_execv = (EXECV_POINTER)ProcUtils::get_sym_addr(func_name);

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execv)(path, argv);

    /* Send pre function call generic message */
    send_pre_func_generic_msg(func_name);

    /* Call the original execv */
    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execv)(path, argv);

    /* This part will execute only if exec fails */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, func_name, ret,
                start_time, end_time, errno_value);

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
    std::string func_name = "execvp";
    static EXECVP_POINTER real_execvp = NULL;

    /* Get the symbol address and store it */
    if (!real_execvp)
        real_execvp = (EXECVP_POINTER)ProcUtils::get_sym_addr(func_name);

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execvp)(file, argv);

    /* Send pre function call generic message */
    send_pre_func_generic_msg(func_name);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execvp)(file, argv);

    /* This part will execute only if exec fails */
    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, func_name, ret, start_time, end_time, errno_value);

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
    std::vector<char*> env_vec;

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    std::string func_name = "execvpe";
    static EXECVPE_POINTER real_execvpe = NULL;

    /* Get the symbol address and store it */
    if (!real_execvpe)
        real_execvpe = (EXECVPE_POINTER)ProcUtils::get_sym_addr(func_name);

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execvpe)(file, argv, &env_vec[0]);

    /* Send pre function call generic message */
    send_pre_func_generic_msg(func_name);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execvpe)(file, argv, &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, func_name, ret, start_time, end_time, errno_value);

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
    std::vector<char*> env_vec;

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    std::string func_name = "execve";
    static EXECVE_POINTER real_execve = NULL;

    /* Get the symbol address and store it */
    if (!real_execve)
        real_execve = (EXECVE_POINTER)ProcUtils::get_sym_addr(func_name);

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_execve)(filename, argv, &env_vec[0]);

    /* Send pre function call generic message */
    send_pre_func_generic_msg(func_name);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_execve)(filename, argv, &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, func_name, ret, start_time, end_time, errno_value);

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
    std::vector<char*> env_vec;

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    std::string func_name = "fexecve";
    static FEXECVE_POINTER real_fexecve = NULL;

    /* Get the symbol address and store it */
    if (!real_fexecve)
        real_fexecve = (FEXECVE_POINTER)ProcUtils::get_sym_addr(func_name);

    /* Call function if global flag is true */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_fexecve)(fd, argv, &env_vec[0]);

    /* Send pre function call generic message */
    send_pre_func_generic_msg(func_name);

    uint64_t start_time = ProcUtils::get_time();
    int ret = (*real_fexecve)(fd, argv, &env_vec[0]);

    uint64_t end_time = ProcUtils::get_time();
    int errno_value = errno;

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, func_name, ret, start_time, end_time, errno_value);

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
    std::string func_name = "fork";
    static FORK_POINTER real_fork = NULL;

    /* Get the symbol address and store it */
    if (!real_fork)
        real_fork = (FORK_POINTER)ProcUtils::get_sym_addr(func_name);

    if (ProcUtils::test_and_set_flag(true))
        return (*real_fork)();

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
    std::string func_name = "dlopen";
    static DLOPEN_POINTER real_dlopen = NULL;

    if (!real_dlopen)
        real_dlopen = (DLOPEN_POINTER)ProcUtils::get_sym_addr(func_name);

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

extern "C" sighandler_t signal(int signum, sighandler_t real_handler)
{
    std::string func_name = "signal";
    static SIGNAL_POINTER real_signal = NULL;

    /* Get the symbol address and store it */
    if (!real_signal)
        real_signal = (SIGNAL_POINTER)ProcUtils::get_sym_addr(func_name);

    /* We are within our own library */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_signal)(signum, real_handler);

    sighandler_t ret = NULL;
    SignalHandler *sh_obj = NULL;

    try
    {
        sh_obj = new SAHandler(signum, real_handler);
        sighandler_t signal_handler = SignalUtils::opus_type_one_signal_handler;

        if (real_handler == SIG_IGN)
            signal_handler = real_handler;

        /*
           Calls the signal function and returns the
           previous handler as an atomic operation
        */
        void *prev_handler = SignalUtils::call_signal(real_signal, signum,
                                                signal_handler, sh_obj, ret);

        if (prev_handler)
            ret = reinterpret_cast<sighandler_t>(prev_handler);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        if (sh_obj) delete sh_obj;
    }

    ProcUtils::test_and_set_flag(false);
    return ret;
}


extern "C" int sigaction(int signum,
                        const struct sigaction *act,
                        struct sigaction *oldact)
{
    std::string func_name = "sigaction";
    static SIGACTION_POINTER real_sigaction = NULL;

    /* Get the symbol address and store it */
    if (!real_sigaction)
        real_sigaction = (SIGACTION_POINTER)ProcUtils::get_sym_addr(func_name);

    /* We are within our own library */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_sigaction)(signum, act, oldact);

    if (!act)
    {
        ProcUtils::test_and_set_flag(false);
        return (*real_sigaction)(signum, act, oldact);
    }

    int ret = 0;
    SignalHandler *sh_obj = NULL;

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

        /*
           Calls the sigaction function and returns the
           previous handler as an atomic operation
        */
        void *prev_handler = SignalUtils::call_sigaction(real_sigaction, signum,
                                                    sa, oldact, sh_obj, ret);

        if (oldact && prev_handler) set_old_act_data(prev_handler, oldact);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        if (sh_obj) delete sh_obj;
    }

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" void _exit(int status)
{
    exit_program("_exit", status);
}

extern "C" void _Exit(int status)
{
    exit_program("_Exit", status);
}

extern "C" int pthread_create(pthread_t *thread, const pthread_attr_t *attr,
                            PTHREAD_HANDLER real_handler, void *real_args)
{
    std::string func_name = "pthread_create";
    static PTHREAD_CREATE_POINTER real_pthread_create = NULL;

    /* Get the symbol address and store it */
    if (!real_pthread_create)
    {
        real_pthread_create =
                (PTHREAD_CREATE_POINTER)ProcUtils::get_sym_addr(func_name);
    }

    if (ProcUtils::test_and_set_flag(true))
        return (*real_pthread_create)(thread, attr, real_handler, real_args);

    uint64_t start_time = ProcUtils::get_time();

    PTHREAD_HANDLER handler = real_handler;
    void *args = real_args;

    try
    {
        OPUSThreadData *opus_thread_data = new OPUSThreadData();
        opus_thread_data->real_handler = real_handler;
        opus_thread_data->real_args = real_args;

        handler = opus_thread_start_routine;
        args = opus_thread_data;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
    }

    errno = 0;
    int ret = (*real_pthread_create)(thread, attr, handler, args);
    int errno_value = errno;

    uint64_t end_time = ProcUtils::get_time();

    FuncInfoMessage func_msg;
    set_func_info_msg(&func_msg, func_name, ret, start_time,
                        end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    ProcUtils::test_and_set_flag(false);
    return ret;
}

extern "C" void pthread_exit(void *retval)
{
    std::string func_name = "pthread_exit";
    static PTHREAD_EXIT_POINTER real_pthread_exit = NULL;

    /* Get the symbol address and store it */
    if (!real_pthread_exit)
    {
        real_pthread_exit =
            (PTHREAD_EXIT_POINTER)ProcUtils::get_sym_addr(func_name);
    }

    if (ProcUtils::test_and_set_flag(true))
        (*real_pthread_exit)(retval);

    FuncInfoMessage func_msg;

    uint64_t start_time = ProcUtils::get_time();
    uint64_t end_time = 0;
    int errno_value = 0;

    set_func_info_msg(&func_msg, func_name, start_time, end_time, errno_value);
    set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG);

    if (getpid() != ProcUtils::gettid())
    {
        // This will call the cleanup handlers
        (*real_pthread_exit)(retval);
    }

    // This is the main thread, setup a cleanup handler
    pthread_cleanup_push(opus_thread_cleanup_handler, NULL);
    (*real_pthread_exit)(retval);
    pthread_cleanup_pop(1);
}
