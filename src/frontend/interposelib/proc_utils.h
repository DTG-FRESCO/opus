#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include <signal.h>
#include <map>
#include <string>
#include <vector>
#include <utility>

#include "uds_msg.pb.h"
#include "opus_lock.h"
#include "comm_client.h"
#include "messaging.h"
#include "aggr_msg.h"

// Process global constants
#define MAX_INT32_LEN   16
#define MAX_TEL_DESC    256
#define INTERPOSE_OFF_MSG "Global interpose flag is off"

/**
 * A utility class that encapsulates common
 * process functions used by the library
 */
class ProcUtils
{
    public:
        static bool inside_opus(const bool value);

        static bool serialise_and_send_data(
                    const struct Header& hdr_obj,
                    const ::google::protobuf::Message& pay_obj);

        static bool buffer_and_send_data(
            const ::fresco::opus::IPCMessage::FuncInfoMessage& buf_func_info_msg);

        static bool flush_buffered_data();

        static void send_startup_message();
        static void send_startup_message(const int argc,
                                        char** argv, char** envp);
        static void send_loaded_libraries();
        static void send_libinfo_message
            (const std::vector<std::pair<std::string, std::string> >& lib_vec);

        static void get_uds_path(std::string* uds_path_str);
        static void get_tcp_address(std::string* address, int* port);
        static void get_preload_path(std::string* ld_preload_path);

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

        static const bool is_opus_fd(const int fd);
        static const bool is_opus_fd(FILE* fp);

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

        /* Aggregation message related functions */
        static bool get_msg_aggr_flag();
        static void set_msg_aggr_flag(const bool flag);
        static void set_msg_aggr_flag();
        static void discard_aggr_msgs();

        /* Getter and setter for OPUS interpose mode */
        static void set_opus_ipose_mode(const int _mode);
        static const int get_opus_ipose_mode();

    private:
        static __thread bool in_opus_flag;
        static __thread CommClient *comm_obj;
        static __thread uint32_t conn_ref_count;
        static pid_t opus_pid;
        static std::map<std::string, void*> *libc_func_map;
        static sig_atomic_t opus_interpose_mode;
        static bool aggr_on_flag;

        /* Thread local cached message objects */
        static __thread ::fresco::opus::IPCMessage::FuncInfoMessage *func_msg_obj;
        static __thread ::fresco::opus::IPCMessage::GenericMessage *gen_msg_obj;
        static __thread AggrMsg *aggr_msg_obj;

        /* TLS pointing to objects on the stack */
        static __thread ::fresco::opus::IPCMessage::FuncInfoMessage *__alt_func_msg_ptr;
        static __thread ::fresco::opus::IPCMessage::GenericMessage *__alt_gen_msg_ptr;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
