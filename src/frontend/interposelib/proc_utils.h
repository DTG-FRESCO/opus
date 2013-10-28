#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include <signal.h>
#include <map>
#include <string>
#include <vector>
#include <utility>
#include "uds_msg.pb.h"
#include "opus_lock.h"
#include "uds_client.h"
#include "messaging.h"

// Process global constants
#define MAX_INT32_LEN   16
#define MAX_TEL_DESC    256
#define __TRUE    1
#define __FALSE   0
#define INTERPOSE_OFF_MSG "Global interpose flag is off"

/**
 * A utility class that encapsulates common
 * process functions used by the library
 */
class ProcUtils
{
    public:
        static uint64_t get_time();
        static void get_formatted_time(std::string* date_time);
        static bool test_and_set_flag(const bool value);

        static bool serialise_and_send_data(
                    const struct Header& hdr_obj,
                    const ::google::protobuf::Message& pay_obj);

        static void send_startup_message();
        static void send_startup_message(const int argc,
                                        char** argv, char** envp);
        static void send_loaded_libraries();
        static void send_libinfo_message
            (const std::vector<std::pair<std::string, std::string> >& lib_vec);

        static char* get_env_val(const std::string& env_key);
        static void get_uds_path(std::string* uds_path_str);
        static void get_preload_path(std::string* ld_preload_path);
        static const std::string get_user_name(const uid_t user_id);
        static const std::string get_group_name(const gid_t group_id);
        static void get_md5_sum(const std::string& real_path,
                                std::string* md5_sum);
        static pid_t gettid();
        static pid_t getpid();
        static pid_t __getpid(); // Used internally
        static void setpid(const pid_t pid);

        /* libc function map related functions */
        static void* get_sym_addr(const std::string& symbol);
        static void* add_sym_addr(const std::string& symbol);

        /* Backend communication related functions */
        static bool connect();
        static void disconnect();

        static const char* canonicalise_path(const char *path,
                                            char *actual_path);
        static const char* abs_path(const char *path, char *abs_path);
        static const std::string get_error(const int err_num);

        /* Converts an integer to a string */
        static char* opus_itoa(const int32_t val, char *str);

        /* Access function for TLS protobuf message objects */
        static ::google::protobuf::Message* get_proto_msg(
                        const ::fresco::opus::IPCMessage::PayloadType msg_type);
        static void clear_proto_objects();
        static void use_alt_proto_msg(::fresco::opus::IPCMessage::FuncInfoMessage *__func_obj,
                                        ::fresco::opus::IPCMessage::GenericMessage *__gen_obj);
        static void restore_proto_tls();

        static void incr_conn_ref_count();
        static uint32_t decr_conn_ref_count();

        /* Functions to check and turn off interposition */
        static bool is_interpose_off();
        static void interpose_off(const std::string& desc);

    private:
        static __thread bool in_func_flag;
        static __thread UDSCommClient *comm_obj;
        static __thread uint32_t conn_ref_count;
        static pid_t opus_pid;
        static std::map<std::string, void*> *libc_func_map;
        static volatile sig_atomic_t opus_interpose_off;

        /* Thread local cached message objects */
        static __thread ::fresco::opus::IPCMessage::FuncInfoMessage *func_msg_obj;
        static __thread ::fresco::opus::IPCMessage::GenericMessage *gen_msg_obj;

        /* TLS pointing to objects on the stack */
        static __thread ::fresco::opus::IPCMessage::FuncInfoMessage *__alt_func_msg_ptr;
        static __thread ::fresco::opus::IPCMessage::GenericMessage *__alt_gen_msg_ptr;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
