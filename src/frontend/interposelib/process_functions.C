
#include <string>
#include <vector>

typedef pid_t (*FORK_POINTER)(void);
typedef int (*EXECV_POINTER)(const char*, char *const[]);
typedef int (*EXECVP_POINTER)(const char*, char *const argv[]);
typedef int (*EXECVPE_POINTER)(const char*, char *const[], char *const[]);
typedef int (*EXECVE_POINTER)(const char*, char *const[], char *const[]);
typedef int (*FEXECVE_POINTER)(int, char *const[], char *const[]);

/* Initialize function pointers */
static FORK_POINTER real_fork = NULL;
static EXECV_POINTER real_execv = NULL;
static EXECVP_POINTER real_execvp = NULL;
static EXECVPE_POINTER real_execvpe = NULL;
static EXECVE_POINTER real_execve = NULL;
static FEXECVE_POINTER real_fexecve = NULL;

using ::fresco::opus::IPCMessage::GenMsgType;
using ::fresco::opus::IPCMessage::PayloadType;

using ::fresco::opus::IPCMessage::KVPair;
using ::fresco::opus::IPCMessage::Header;
using ::fresco::opus::IPCMessage::GenericMessage;
using ::fresco::opus::IPCMessage::FuncInfoMessage;


static inline void setup_new_uds_connection()
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

static inline void send_pre_func_generic_msg(const std::string& desc)
{
    GenericMessage gen_msg;
    gen_msg.set_msg_type(GenMsgType::PRE_FUNC_CALL);

    gen_msg.set_msg_desc(desc);

    std::string date_time;
    ProcUtils::get_formatted_time(&date_time);
    gen_msg.set_sys_time(date_time);

    const uint64_t msg_size = gen_msg.ByteSize();
    uint64_t current_time = ProcUtils::get_time();

    Header hdr_msg;
    hdr_msg.set_timestamp(current_time);
    hdr_msg.set_pid((uint64_t)getpid());
    hdr_msg.set_payload_type(PayloadType::GENERIC_MSG);
    hdr_msg.set_payload_len(msg_size);

    ProcUtils::serialise_and_send_data(hdr_msg, gen_msg);
}

static inline void send_func_info_msg(const FuncInfoMessage& func_msg)

{
    const uint64_t msg_size = func_msg.ByteSize();
    const uint64_t current_time = ProcUtils::get_time();

    Header hdr_msg;
    hdr_msg.set_timestamp(current_time);
    hdr_msg.set_pid((uint64_t)getpid());
    hdr_msg.set_payload_type(PayloadType::FUNCINFO_MSG);
    hdr_msg.set_payload_len(msg_size);

    ProcUtils::serialise_and_send_data(hdr_msg, func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("path");
    arg_kv->set_value(path);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(file);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("path");
    arg_kv->set_value(path);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("path");
    arg_kv->set_value(path);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(file);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(file);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("file");
    arg_kv->set_value(filename);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name(desc);
    func_msg.set_ret_val(ret);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    char buffer[64];
    memset(buffer, 0, sizeof buffer);
    snprintf(buffer, (sizeof buffer)-1, "%d", fd);

    KVPair* arg_kv;
    arg_kv = func_msg.add_args();
    arg_kv->set_key("fd");
    arg_kv->set_value(buffer);

    send_func_info_msg(func_msg);
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
    func_msg.set_func_name("fork");
    func_msg.set_ret_val(pid);
    func_msg.set_begin_time(start_time);
    func_msg.set_end_time(end_time);
    func_msg.set_error_num(errno_value);

    send_func_info_msg(func_msg);
    ProcUtils::test_and_set_flag(false);

    return pid;
}
