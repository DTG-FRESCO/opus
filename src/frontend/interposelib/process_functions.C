#include <limits.h>
#include <stdlib.h>
#include <link.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <cstdint>
#include <string>
#include <vector>
#include <stdexcept>
#include "log.h"
#include "signal_utils.h"
#include "signal_handler.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "message_util.h"

#define STRINGIFY(value) #value

/**
 * Macros to minimize repetitive
 * code used in all exec functions
 */
#define PRE_EXEC_CALL(fptr_type, fname, desc, arg1, ...) \
    static fptr_type real_fptr = NULL; \
                                        \
    /* Get the symbol address and store it */\
    if (!real_fptr)\
        real_fptr = (fptr_type)ProcUtils::get_sym_addr(fname); \
                                                \
    /* Call function if global flag is true */ \
    if (ProcUtils::test_and_set_flag(true)) \
        return (*real_fptr)(arg1, __VA_ARGS__); \
                                            \
    /* Send pre function call generic message */ \
    bool conn_ret = send_pre_func_generic_msg(desc); \
                                                    \
    /* Call the original exec */ \
    uint64_t start_time = ProcUtils::get_time();

#define POST_EXEC_CALL(desc, arg1_val) \
                                    \
    if (!conn_ret) return ret; \
                                    \
    /* This part will execute only if exec fails */ \
    uint64_t end_time = ProcUtils::get_time(); \
    int errno_value = errno; \
                                \
    FuncInfoMessage func_msg; \
    set_func_info_msg(&func_msg, desc, ret, start_time, end_time, errno_value); \
                        \
    KVPair* arg_kv; \
    arg_kv = func_msg.add_args(); \
    arg_kv->set_key(STRINGIFY(arg1)); \
    arg_kv->set_value(arg1_val); \
                            \
    if (!set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG)) \
        return ret; \
                    \
    ProcUtils::test_and_set_flag(false); \
    return ret;

/**
 * This function macro is used by exec functions
 * that do not pass environment variables
 */
#define EXEC_FUNC(fptr_type, fname, desc, arg1, ...) \
    PRE_EXEC_CALL(fptr_type, fname, desc, arg1, __VA_ARGS__); \
    errno = 0; \
    int ret = (*real_fptr)(arg1, __VA_ARGS__); \
    POST_EXEC_CALL(desc, arg1);

/**
 * This function macro is used by exec functions
 * that pass environment variables. The environment
 * data allocated on the heap is released if exec fails.
 */
#define EXEC_FUNC_ENV(fptr_type, fname, desc, arg1, ...) \
    PRE_EXEC_CALL(fptr_type, fname, desc, arg1, __VA_ARGS__); \
    errno = 0; \
    int ret = (*real_fptr)(arg1, __VA_ARGS__); \
                                                \
    /* If exec returns, it indicates an error. Free allocated memory */ \
    cleanup_allocated_memory(&env_vec); \
    POST_EXEC_CALL(desc, arg1);


typedef void* (*PTHREAD_HANDLER)(void*);

/**
 * Structure to store the original
 * application thread handler
 * along with arguments passed
 */
struct OPUSThreadData
{
    PTHREAD_HANDLER real_handler;
    void *real_args;
};

/**
 * Called by all threads that exit.
 * Sends a thread exit generic
 * message to the backend
 */
static void opus_thread_cleanup_handler(void *cleanup_args)
{
    ProcUtils::test_and_set_flag(true);

    send_generic_msg(GenMsgType::THREAD_EXIT,
                std::to_string(ProcUtils::gettid()));

    ProcUtils::disconnect();
}

/**
 * OPUS thread handler wrapper routine.
 * Establishes a new connection to the backend.
 * Sends a thread start message and installs
 * a thread cleanup handler.
 */
static void* opus_thread_start_routine(void *args)
{
    /* Disable thread cancellation */
    int oldstate = 0;
    int err = pthread_setcancelstate(PTHREAD_CANCEL_DISABLE, &oldstate);
    if (err != 0)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(err));
    }

    ProcUtils::test_and_set_flag(true);

    DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, __PRETTY_FUNCTION__);

    OPUSThreadData *opus_thread_data = static_cast<OPUSThreadData*>(args);

    PTHREAD_HANDLER real_handler = opus_thread_data->real_handler;
    void *real_args = opus_thread_data->real_args;

    delete opus_thread_data; // don't need this pointer anymore

    pthread_cleanup_push(opus_thread_cleanup_handler, NULL);

    try
    {
        if (!ProcUtils::connect())
            throw std::runtime_error("ProcUtils::connect failed!!");

        if (send_generic_msg(GenMsgType::THREAD_START,
                    std::to_string(ProcUtils::gettid())))
        {
            ProcUtils::test_and_set_flag(false); // Turn on interposition
        }
    }
    catch(const std::exception& e)
    {
        // Interposition remains turned off
        DEBUG_LOG("[%s:%d]: TID: %d. %s\n", __FILE__, __LINE__, e.what());
    }

    /* Restore thread cancellation state */
    err = pthread_setcancelstate(oldstate, NULL);
    if (err != 0)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(err));
    }

    void *ret = real_handler(real_args);
    ProcUtils::test_and_set_flag(true);

    return ret;
    pthread_cleanup_pop(1); // Added to avoid compilation error
}

/**
 * Given a dlopen handle, this function
 * obtains the real path of the library
 */
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

/**
 * Invoked by the _exit or _Exit wrappers.
 * Disconnects from the OPUS backend and
 * calls the real _exit or _Exit functions.
 */
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

    ProcUtils::disconnect();

    (*exit_ptr)(status);

    // Will never reach here
    ProcUtils::test_and_set_flag(false);
}

/**
 * If the oldact pointer is not null,
 * the previous signal handler will be
 * returned in the sigaction structure.
 */
static inline void set_old_act_data(void* prev, struct sigaction *oldact)
{
    if (oldact->sa_flags & SA_SIGINFO)
        oldact->sa_sigaction = reinterpret_cast<SA_SIGACTION_PTR>(prev);
    else
        oldact->sa_handler = reinterpret_cast<sighandler_t>(prev);
}

/**
 * Called when a process is forked. The child
 * process closes the inherited UDS connection
 * and opens and new connection.
 */
static void setup_new_uds_connection()
{
    ProcUtils::test_and_set_flag(true);

#ifdef CAPTURE_SIGNALS
    SignalUtils::reset();
#endif
    ProcUtils::disconnect(); // Close inherited connection

    try
    {
        // Open a new connection
        if (!ProcUtils::connect())
            throw std::runtime_error("ProcUtils::connect failed!!");

        ProcUtils::send_startup_message();
        ProcUtils::test_and_set_flag(false); // Turn on interposition
    }
    catch(const std::exception& e)
    {
        // Interposition remains turned off
        DEBUG_LOG("[%s:%d]: TID: %d. %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Frees all environment variables
 * allocated on the heap.
 */
static void cleanup_allocated_memory(std::vector<char*>* env_vec)
{
    std::vector<char*>::iterator iter;
    for (iter = env_vec->begin(); iter != env_vec->end(); ++iter)
    {
        delete *iter;
        *iter = NULL;
    }
}

/**
 * Allocates memory for an environment variable
 * on the heap and returns a pointer to it.
 */
static char* alloc_and_copy(const std::string& env_str)
{
    char *env_data = NULL;

    try
    {
        const int len = env_str.length();
        env_data = new char[len + 1]();
        strncpy(env_data, env_str.c_str(), len);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return env_data;
}

/**
 * Checks if the OPUS library is present in the
 * LD_PRELOAD environment variable. If not present,
 * the OPUS library path is appended to LD_PRELOAD
 */
static void check_and_add_opus_lib(std::string* env_str)
{
    try
    {
        char *opus_lib_name = ProcUtils::get_env_val("OPUS_LIB_NAME");

        int64_t pos = env_str->find(opus_lib_name);
        if (pos != (int64_t)std::string::npos)
            return; // Libraray already present

        std::string preload_path;
        ProcUtils::get_preload_path(&preload_path);

        if (!preload_path.empty()) // Append OPUS library to existing value
            *env_str += " " + preload_path;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Adds the UDS path to the list of environment
 * variables being passed to the execed program
 */
static void add_uds_path(std::vector<char*>* env_vec_ptr)
{
    std::string uds_path;
    ProcUtils::get_uds_path(&uds_path);

    std::string uds_str = "OPUS_UDS_PATH=" + uds_path;
    char *env_data = alloc_and_copy(uds_str);
    if (!env_data) return;

    env_vec_ptr->push_back(env_data);

    DEBUG_LOG("[%s:%d]: Added OPUS_UDS_PATH: %s\n",
                __FILE__, __LINE__, env_data);

}

/**
 * Adds environment variables related to OPUS
 * if missing before the call to exec is made.
 */
static void copy_env_vars(char **envp, std::vector<char*>* env_vec_ptr)
{
    char *env = NULL;
    bool found = false;

    if (envp)
    {
        std::string env_str;
        std::string match_str("LD_PRELOAD");

        while ((env = *envp) != NULL)
        {
            env_str = env;

            /* Check if LD_PRELOAD is present */
            int64_t found_pos = env_str.find(match_str);
            if (found_pos != (int64_t)std::string::npos)
            {
                check_and_add_opus_lib(&env_str);
                found = true;
            }

            char *env_data = alloc_and_copy(env_str);
            if (env_data) env_vec_ptr->push_back(env_data);

            ++envp;
        }
    }

    /* Add the LD_PRELOAD path if not already present */
    if (!found)
    {
        std::string preload_path;
        ProcUtils::get_preload_path(&preload_path);

        std::string preload_str = "LD_PRELOAD=" + preload_path;
        char *env_data = alloc_and_copy(preload_str);
        if (!env_data)
        {
            DEBUG_LOG("[%s:%d]: Could not add LD_PRELOAD path\n",
                        __FILE__, __LINE__);
            return;
        }

        env_vec_ptr->push_back(env_data);

        DEBUG_LOG("[%s:%d]: Added LD_PRELOAD path: %s\n",
                    __FILE__, __LINE__, env_data);
    }

    add_uds_path(env_vec_ptr);
}

/**
 * Interposition function for execl
 */
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

    EXEC_FUNC(EXECV_POINTER, "execv", "execl", path, &arg_vec[0]);
}

/**
 * Interposition function for execlp
 */
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

    EXEC_FUNC(EXECVP_POINTER, "execvp", "execlp", file, &arg_vec[0]);
}

/**
 * Interposition function for execle
 */
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

    EXEC_FUNC_ENV(EXECVPE_POINTER, "execvpe", "execle",
                    path, &arg_vec[0], &env_vec[0]);
}

/**
 * Interposition function for execv
 */
extern "C" int execv(const char *path, char *const argv[])
{
    EXEC_FUNC(EXECV_POINTER, "execv", "execv", path, argv);
}

/**
 * Interposition function for execvp
 */
extern "C" int execvp(const char *file, char *const argv[])
{
    EXEC_FUNC(EXECVP_POINTER, "execvp", "execvp", file, argv);
}

/**
 * Interposition function for execvpe
 */
extern "C" int execvpe(const char *file, char *const argv[], char *const envp[])
{
    std::vector<char*> env_vec;

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    EXEC_FUNC_ENV(EXECVPE_POINTER, "execvpe", "execvpe",
                    file, argv, &env_vec[0]);
}

/**
 * Interposition function for execve
 */
extern "C" int execve(const char *file,
                    char *const argv[],
                    char *const envp[])
{
    std::vector<char*> env_vec;

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    EXEC_FUNC_ENV(EXECVE_POINTER, "execve", "execve", file, argv, &env_vec[0]);
}

/**
 * Interposition function for fexecve
 */
extern "C" int fexecve(int fd, char *const argv[], char *const envp[])
{
    std::vector<char*> env_vec;

    /* Copy OPUS specific env variables if possible */
    copy_env_vars(const_cast<char**>(envp), &env_vec);
    env_vec.push_back(NULL);

    PRE_EXEC_CALL(FEXECVE_POINTER, "fexecve", "fexecve", fd, argv, &env_vec[0]);
    errno = 0;
    int ret = (*real_fptr)(fd, argv, &env_vec[0]);
    POST_EXEC_CALL("fexecve", std::to_string(fd));
}

/**
 * Interposition function for fork
 */
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

    errno = 0;
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

    if (!set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG))
        return pid;

    ProcUtils::test_and_set_flag(false);
    return pid;
}

/**
 * Interposition function for dlopen
 */
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

        if (!set_header_and_send(lib_info_msg, PayloadType::LIBINFO_MSG))
            return handle;
    }

    ProcUtils::test_and_set_flag(false);
    return handle;
}

#ifdef CAPTURE_SIGNALS
/**
 * Interposition function for signal
 */
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

    if (!SignalUtils::is_signal_valid(signum))
    {
        ProcUtils::test_and_set_flag(false);
        return (*real_signal)(signum, real_handler);
    }

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

        ret = reinterpret_cast<sighandler_t>(prev_handler);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        delete sh_obj;
    }

    ProcUtils::test_and_set_flag(false);
    return ret;
}
#endif

#ifdef CAPTURE_SIGNALS
/**
 * Interposition function for sigaction
 */
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

    if (!SignalUtils::is_signal_valid(signum))
    {
        ProcUtils::test_and_set_flag(false);
        return (*real_sigaction)(signum, act, oldact);
    }

    int ret = 0;
    SignalHandler *sh_obj = NULL;
    struct sigaction *sa = NULL;

    try
    {
        if (act)
        {
            // Cast away the constness
            sa = const_cast<struct sigaction *>(act);

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
        }

        /*
           Calls the sigaction function and returns the
           previous handler as an atomic operation
        */
        void *prev_handler = SignalUtils::call_sigaction(real_sigaction, signum,
                                                    sa, oldact, sh_obj, ret);

        if (oldact) set_old_act_data(prev_handler, oldact);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        delete sh_obj;
    }

    ProcUtils::test_and_set_flag(false);
    return ret;
}
#endif

/**
 * Interposition function for _exit
 */
extern "C" void _exit(int status)
{
    exit_program("_exit", status);
}

/**
 * Interposition function for _Exit
 */
extern "C" void _Exit(int status)
{
    exit_program("_Exit", status);
}

/**
 * Interposition function for pthread_create
 */
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

    if (!set_header_and_send(func_msg, PayloadType::FUNCINFO_MSG))
        return ret;

    ProcUtils::test_and_set_flag(false);
    return ret;
}

/**
 * Interposition function for pthread_exit
 */
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

    if (ProcUtils::getpid() != ProcUtils::gettid())
    {
        // This will call the cleanup handlers
        (*real_pthread_exit)(retval);
    }

    // This is the main thread, setup a cleanup handler
    pthread_cleanup_push(opus_thread_cleanup_handler, NULL);
    (*real_pthread_exit)(retval);
    pthread_cleanup_pop(1);
}

#ifdef CAPTURE_SIGNALS
/**
 * Obsolete System V signal API. This is being
 * interposed mainly in order to track signal state
 * when a signal is set to SIG_IGN and SIG_DFL.
 */
extern "C" sighandler_t sigset(int sig, sighandler_t disp)
{
    std::string func_name = "sigset";
    static SIGSET_POINTER real_sigset = NULL;

    /* Get the symbol address and store it */
    if (!real_sigset)
        real_sigset = (SIGSET_POINTER)ProcUtils::get_sym_addr(func_name);

    /* We are within our own library */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_sigset)(sig, disp);

    if (disp == SIG_IGN || disp == SIG_DFL)
    {
        ProcUtils::test_and_set_flag(false);
        return signal(sig, disp);
    }

    /* We do not deal with SIG_HOLD */
    sighandler_t ret = (*real_sigset)(sig, disp);

    ProcUtils::test_and_set_flag(false);
    return ret;
}
#endif

#ifdef CAPTURE_SIGNALS
/**
 * Obsolete System V signal API. This is being
 * interposed mainly in order to track signal
 * state when signal is set to SIG_IGN.
 */
extern "C" int sigignore(int sig)
{
    std::string func_name = "sigignore";
    static SIGIGNORE_POINTER real_sigignore = NULL;

    /* Get the symbol address and store it */
    if (!real_sigignore)
        real_sigignore = (SIGIGNORE_POINTER)ProcUtils::get_sym_addr(func_name);

    /* We are within our own library */
    if (ProcUtils::test_and_set_flag(true))
        return (*real_sigignore)(sig);

    /* Use sigaction to ignore the signal */
    struct sigaction act;
    act.sa_handler = SIG_IGN;
    if (sigemptyset(&act.sa_mask) < 0)
        return -1;
    act.sa_flags = 0;

    /*
       Turn on interposition and call sigaction so that
       OPUS can track the current state of this signal.
    */
    ProcUtils::test_and_set_flag(false);
    return sigaction(sig, &act, NULL);
}
#endif
