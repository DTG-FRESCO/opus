#include <limits.h>
#include <stdlib.h>
#include <link.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdarg.h>
#include <unistd.h>
#include <cstdint>
#include <string>
#include <vector>
#include <stdexcept>
#include "log.h"
#include "signal_utils.h"
#include "signal_handler.h"
#include "func_ptr_types.h"
#include "proc_utils.h"
#include "track_errno.h"
#include "common_macros.h"
#include "sys_util.h"
#include "file_hash.h"
#include "message_util.h"

#define STRINGIFY(value) #value

static inline void exit_program(const char *exit_str, const int status) __attribute__ ((noreturn));


/**
 * Macros to minimize repetitive
 * code used in all exec functions
 */
#define PRE_EXEC_CALL(fptr_type, fname, desc, arg1, ...)    \
    static fptr_type real_fptr = NULL;                      \
    TrackErrno err_obj(errno);                              \
                                                            \
    /* Get the symbol address and store it */               \
    if (!real_fptr)\
        real_fptr = (fptr_type)ProcUtils::get_sym_addr(fname); \
                                                            \
    /* Call function if global flag is true */              \
    if (ProcUtils::inside_opus(true))                       \
    {                                                       \
        CALL_FUNC(int, ret, real_fptr, arg1, __VA_ARGS__);  \
        return ret;                                         \
    }                                                       \
                                                            \
    if (ProcUtils::is_interpose_off())                      \
    {                                                       \
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);        \
        CALL_FUNC(int, ret, real_fptr, arg1, __VA_ARGS__);  \
        return ret;                                         \
    }                                                       \
                                                            \
    /* Flush the aggregated messages */                     \
    ProcUtils::flush_buffered_data();                       \
                                                            \
    /* Send pre function call generic message */            \
    bool comm_ret = send_pre_func_generic_msg(desc);        \
                                                            \
    /* Call the original exec */                            \
    uint64_t start_time = SysUtil::get_time();


#define POST_EXEC_CALL(desc, arg1_val)                      \
                                                            \
    if (!comm_ret) return ret;                              \
                                                            \
    /* This part will execute only if exec fails */         \
    uint64_t end_time = SysUtil::get_time();              \
    int errno_value = errno;                                \
                                                            \
    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>( \
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG)); \
    if (!func_msg) return ret;                              \
                                                            \
    set_func_info_msg(func_msg, desc, ret, start_time, end_time, errno_value); \
                                                            \
    KVPair* arg_kv;                                         \
    arg_kv = func_msg->add_args();                          \
    arg_kv->set_key(STRINGIFY(arg1));                       \
    arg_kv->set_value(arg1_val);                            \
                                                            \
    comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG); \
    ProcUtils::inside_opus(!comm_ret);                      \
    func_msg->Clear();                                      \
    return ret;

/**
 * This function macro is used by exec functions
 * that do not pass environment variables
 */
#define EXEC_FUNC(fptr_type, fname, desc, arg1, ...)            \
    PRE_EXEC_CALL(fptr_type, fname, desc, arg1, __VA_ARGS__);   \
    CALL_FUNC(int, ret, real_fptr, arg1, __VA_ARGS__);          \
    POST_EXEC_CALL(desc, arg1);

/**
 * This function macro is used by exec functions
 * that pass environment variables. The environment
 * data allocated on the heap is released if exec fails.
 */
#define EXEC_FUNC_ENV(fptr_type, fname, desc, arg1, ...)        \
    PRE_EXEC_CALL(fptr_type, fname, desc, arg1, __VA_ARGS__);   \
    CALL_FUNC(int, ret, real_fptr, arg1, __VA_ARGS__);          \
                                                                \
    /* If exec returns, it indicates an error
       Free allocated memory
    */                                                          \
    cleanup_allocated_memory(&env_vec);                         \
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
    ProcUtils::inside_opus(true);

    char tid_buf[MAX_INT32_LEN] = "";
    send_generic_msg(GenMsgType::THREAD_EXIT,
                    ProcUtils::opus_itoa(ProcUtils::gettid(), tid_buf));

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
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                SysUtil::get_error(err).c_str());
    }

    ProcUtils::inside_opus(true);

    LOG_MSG(LOG_DEBUG, "[%s:%d]: %s\n", __FILE__, __LINE__, __PRETTY_FUNCTION__);

    OPUSThreadData *opus_thread_data = static_cast<OPUSThreadData*>(args);

    PTHREAD_HANDLER real_handler = opus_thread_data->real_handler;
    void *real_args = opus_thread_data->real_args;

    delete opus_thread_data; // don't need this pointer anymore

    pthread_cleanup_push(opus_thread_cleanup_handler, NULL);

    try
    {
        if (!ProcUtils::connect())
            throw std::runtime_error("ProcUtils::connect failed!!");

        char tid_buf[MAX_INT32_LEN] = "";
        if (send_generic_msg(GenMsgType::THREAD_START,
            ProcUtils::opus_itoa(ProcUtils::gettid(), tid_buf)))
        {
            ProcUtils::inside_opus(false); // Turn on interposition
        }
    }
    catch(const std::exception& e)
    {
        // Interposition remains turned off
        LOG_MSG(LOG_ERROR, "[%s:%d]: TID: %d. %s\n", __FILE__, __LINE__, e.what());
    }

    /* Restore thread cancellation state */
    err = pthread_setcancelstate(oldstate, NULL);
    if (err != 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                SysUtil::get_error(err).c_str());
    }

    void *ret = real_handler(real_args);
    ProcUtils::inside_opus(true);

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
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, dlerror());
        return;
    }

    char *path = realpath(link->l_name, NULL);
    if (!path)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                SysUtil::get_error(errno).c_str());
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
    static _EXIT_POINTER exit_ptr __attribute__ ((noreturn)) = NULL;

    if (!exit_ptr)
        exit_ptr = (_EXIT_POINTER)ProcUtils::get_sym_addr(exit_str);

    if (ProcUtils::inside_opus(true))
    {
        (*exit_ptr)(status);
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        (*exit_ptr)(status);
    }

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (func_msg)
    {
        KVPair* tmp_arg;
        tmp_arg = func_msg->add_args();
        tmp_arg->set_key("status");

        char status_buf[MAX_INT32_LEN] = "";
        tmp_arg->set_value(ProcUtils::opus_itoa(status, status_buf));

        uint64_t start_time = SysUtil::get_time();
        uint64_t end_time = 0;  // function does not return
        int errno_value = 0;

        set_func_info_msg(func_msg, exit_str, start_time, end_time, errno_value);
        set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);

        if (ProcUtils::decr_conn_ref_count() == 0)
        {
            ProcUtils::flush_buffered_data();
            ProcUtils::disconnect();
        }

        (*exit_ptr)(status);

        // Will never reach here
        ProcUtils::inside_opus(false);
        func_msg->Clear();
    }
    else
    {
        (*exit_ptr)(status);
    }
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
 * process must reset some state inherited
 * from the parent process.
 */
static void setup_forked_child_process()
{
    ProcUtils::inside_opus(true);

#ifdef CAPTURE_SIGNALS
    SignalUtils::reset();
#endif
    ProcUtils::disconnect(); // Close inherited connection
    ProcUtils::clear_proto_objects(); // Clear inherited protobuf objects
    ProcUtils::discard_aggr_msgs(); // Discard all inherited aggregation messages

    try
    {
        // Set the correct pid
        ProcUtils::setpid(getpid());

        // Open a new connection
        if (!ProcUtils::connect())
            throw std::runtime_error("ProcUtils::connect failed!!");

        ProcUtils::send_startup_message();
        ProcUtils::inside_opus(false); // Turn on interposition
    }
    catch(const std::exception& e)
    {
        // Interposition remains turned off
        LOG_MSG(LOG_ERROR, "[%s:%d]: TID: %d. %s\n", __FILE__, __LINE__, e.what());
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
    catch(const std::bad_alloc& e)
    {
        ProcUtils::interpose_off(e.what());
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
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
        char *opus_lib_name = SysUtil::get_env_val("OPUS_LIB_NAME");

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
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
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

    LOG_MSG(LOG_DEBUG, "[%s:%d]: Added OPUS_UDS_PATH: %s\n",
                __FILE__, __LINE__, env_data);

}

/**
 * Adds OPUS_INTERPOSE_MODE to the list of environment
 * variables being passed to the execed program
 */
static void add_opus_interpose_mode(std::vector<char*>* env_vec_ptr)
{
    try
    {
        char *ipose_mode = SysUtil::get_env_val("OPUS_INTERPOSE_MODE");

        std::string opus_interpose_mode = "OPUS_INTERPOSE_MODE=";
        opus_interpose_mode += std::string(ipose_mode);

        char *env_data = alloc_and_copy(opus_interpose_mode);
        if (!env_data)
        {
            throw std::runtime_error("Could not add OPUS_INTERPOSE_MODE");
        }

        env_vec_ptr->push_back(env_data);

        LOG_MSG(LOG_DEBUG, "[%s:%d]: Added OPUS_INTERPOSE_MODE: %s\n",
                    __FILE__, __LINE__, env_data);
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
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
            LOG_MSG(LOG_ERROR, "[%s:%d]: Could not add LD_PRELOAD path\n",
                        __FILE__, __LINE__);
            return;
        }

        env_vec_ptr->push_back(env_data);

        LOG_MSG(LOG_DEBUG, "[%s:%d]: Added LD_PRELOAD path: %s\n",
                    __FILE__, __LINE__, env_data);
    }

    add_uds_path(env_vec_ptr);
    add_opus_interpose_mode(env_vec_ptr);
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
    err_obj = errno;
    char fd_buf[MAX_INT32_LEN] = "";
    POST_EXEC_CALL("fexecve", ProcUtils::opus_itoa(fd, fd_buf));
}

/**
 * Interposition function for fork
 */
extern "C" pid_t fork(void)
{
    static FORK_POINTER real_fork = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_fork)
        real_fork = (FORK_POINTER)ProcUtils::get_sym_addr("fork");

    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(pid_t, pid, real_fork);
        return pid;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(pid_t, pid, real_fork);
        return pid;
    }


    uint64_t start_time = SysUtil::get_time();

    CALL_FUNC(pid_t, pid, real_fork);

    if (pid == 0)
    {
        /* Child process */
        setup_forked_child_process();
        return pid;
    }

    /* Parent process */
    int errno_value = errno;

    uint64_t end_time = SysUtil::get_time();

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg) return pid;

    set_func_info_msg(func_msg, "fork", pid,
                start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::inside_opus(!comm_ret);
    func_msg->Clear();

    return pid;
}

/**
 * Interposition function for dlopen
 */
extern "C" void* dlopen(const char * filename, int flag)
{
    bool comm_ret = true;
    static DLOPEN_POINTER real_dlopen = NULL;
    TrackErrno err_obj(errno);

    if (!real_dlopen)
        real_dlopen = (DLOPEN_POINTER)ProcUtils::get_sym_addr("dlopen");

    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(void*, handle, real_dlopen, filename, flag);
        return handle;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(void*, handle, real_dlopen, filename, flag);
        return handle;
    }

    CALL_FUNC(void*, handle, real_dlopen, filename, flag);

    if (handle)
    {
        std::string real_path;
        std::string md5_sum;

        get_lib_real_path(handle, &real_path);
        FileHash::get_md5_sum(real_path, &md5_sum);

        LibInfoMessage lib_info_msg;
        KVPair *kv_args = lib_info_msg.add_library();
        kv_args->set_key(real_path);
        kv_args->set_value(md5_sum);

        comm_ret = set_header_and_send(lib_info_msg, PayloadType::LIBINFO_MSG);
    }

    ProcUtils::inside_opus(!comm_ret);
    return handle;
}

#ifdef CAPTURE_SIGNALS
/**
 * Interposition function for signal
 */
extern "C" sighandler_t signal(int signum, sighandler_t real_handler)
{
    static SIGNAL_POINTER real_signal = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_signal)
        real_signal = (SIGNAL_POINTER)ProcUtils::get_sym_addr("signal");

    /* We are within our own library */
    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(sighandler_t, ret, real_signal, signum, real_handler);
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(sighandler_t, ret, real_signal, signum, real_handler);
        return ret;
    }

    /*
       We don't care about this signal. Call the
       real libc function and turn on interposition
    */
    if (!SignalUtils::is_signal_valid(signum))
    {
        CALL_FUNC(sighandler_t, ret, real_signal, signum, real_handler);
        ProcUtils::inside_opus(false);
        return ret;
    }

    SignalHandler *sh_obj = NULL;
    sighandler_t ret = NULL;

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
    catch(const std::bad_alloc& e)
    {
        ProcUtils::interpose_off(e.what());
        CALL_FUNC(sighandler_t, retval, real_signal, signum, real_handler);
        return retval;
    }
    catch(const std::exception& e)
    {
        err_obj = errno;
        LOG_MSG(LOG_ERROR, "[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        delete sh_obj;
    }

    ProcUtils::inside_opus(false);
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
    static SIGACTION_POINTER real_sigaction = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_sigaction)
        real_sigaction = (SIGACTION_POINTER)ProcUtils::get_sym_addr("sigaction");

    LOG_MSG(LOG_ERROR, "Inside sigaction %d\n", signum);

    /* We are within our own library */
    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(int, ret, real_sigaction, signum, act, oldact);
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(int, ret, real_sigaction, signum, act, oldact);
        return ret;
    }

    /*
       We don't care about this signal. Call the
       real libc function and turn on interposition
    */
    if (!SignalUtils::is_signal_valid(signum))
    {
        CALL_FUNC(int, ret, real_sigaction, signum, act, oldact);
        ProcUtils::inside_opus(false);
        return ret;
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
    catch(const std::bad_alloc& e)
    {
        ProcUtils::interpose_off(e.what());
        CALL_FUNC(int, retval, real_sigaction, signum, act, oldact);
        return retval;
    }
    catch(const std::exception& e)
    {
        err_obj = errno;
        LOG_MSG(LOG_ERROR, "[%s:%d]: : %s\n", __FILE__, __LINE__, e.what());
        delete sh_obj;
    }

    ProcUtils::inside_opus(false);
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
    static PTHREAD_CREATE_POINTER real_pthread_create = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_pthread_create)
    {
        real_pthread_create =
                (PTHREAD_CREATE_POINTER)ProcUtils::get_sym_addr("pthread_create");
    }

    if (ProcUtils::inside_opus(true))
        return (*real_pthread_create)(thread, attr, real_handler, real_args);

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        return (*real_pthread_create)(thread, attr, real_handler, real_args);
    }

    uint64_t start_time = SysUtil::get_time();

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
    catch(const std::bad_alloc& e)
    {
        ProcUtils::interpose_off(e.what());
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                        SysUtil::get_error(errno).c_str());
    }

    int ret = (*real_pthread_create)(thread, attr, handler, args);

    uint64_t end_time = SysUtil::get_time();

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg) return ret;

    set_func_info_msg(func_msg, "pthread_create", ret, start_time,
                        end_time, ret);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::inside_opus(!comm_ret);
    func_msg->Clear();

    return ret;
}

/**
 * Interposition function for pthread_exit
 */
extern "C" void pthread_exit(void *retval)
{
    static PTHREAD_EXIT_POINTER real_pthread_exit __attribute__ ((noreturn)) = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_pthread_exit)
    {
        real_pthread_exit =
            (PTHREAD_EXIT_POINTER)ProcUtils::get_sym_addr("pthread_exit");
    }

    if (ProcUtils::inside_opus(true))
        (*real_pthread_exit)(retval);

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        (*real_pthread_exit)(retval);
    }

    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg)
    {
        uint64_t start_time = SysUtil::get_time();
        uint64_t end_time = 0;
        int errno_value = 0;

        set_func_info_msg(func_msg, "pthread_exit", start_time, end_time, errno_value);
        set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
        func_msg->Clear();

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
    else
    {
        (*real_pthread_exit)(retval);
    }
}

#ifdef CAPTURE_SIGNALS
/**
 * Obsolete System V signal API. This is being
 * interposed mainly in order to track signal state
 * when a signal is set to SIG_IGN and SIG_DFL.
 */
extern "C" sighandler_t sigset(int sig, sighandler_t disp)
{
    static SIGSET_POINTER real_sigset = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_sigset)
        real_sigset = (SIGSET_POINTER)ProcUtils::get_sym_addr("sigset");

    /* We are within our own library */
    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(sighandler_t, ret, real_sigset, sig, disp);
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(sighandler_t, ret, real_sigset, sig, disp);
        return ret;
    }

    /*
       Turn on interposition and call signal so that
       OPUS can track the current state of this signal.
    */
    if (disp == SIG_IGN || disp == SIG_DFL)
    {
        ProcUtils::inside_opus(false);
        CALL_FUNC(sighandler_t, ret, real_sigset, sig, disp);
        return ret;
    }

    /* We do not deal with SIG_HOLD */
    CALL_FUNC(sighandler_t, ret, real_sigset, sig, disp);

    ProcUtils::inside_opus(false);
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
    static SIGIGNORE_POINTER real_sigignore = NULL;
    TrackErrno err_obj(errno);

    /* Get the symbol address and store it */
    if (!real_sigignore)
        real_sigignore = (SIGIGNORE_POINTER)ProcUtils::get_sym_addr("sigignore");

    /* We are within our own library */
    if (ProcUtils::inside_opus(true))
    {
        CALL_FUNC(int, ret, real_sigignore, sig);
        return ret;
    }

    if (ProcUtils::is_interpose_off())
    {
        ProcUtils::interpose_off(INTERPOSE_OFF_MSG);
        CALL_FUNC(int, ret, real_sigignore, sig);
        return ret;
    }


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
    ProcUtils::inside_opus(false);
    CALL_FUNC(int, ret, sigaction, sig, &act, NULL);

    return ret;
}
#endif
