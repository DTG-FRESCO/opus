#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include <map>
#include <string>
#include <vector>
#include <utility>
#include "uds_msg.pb.h"
#include "opus_lock.h"
#include "uds_client.h"

class ProcUtils
{
    public:
        static uint64_t get_time();
        static void get_formatted_time(std::string* date_time);
        static bool test_and_set_flag(const bool value);

        static void serialise_and_send_data(
                    const ::fresco::opus::IPCMessage::Header& hdr_obj,
                    const ::google::protobuf::Message& pay_obj);

        static void send_startup_message();
        static void send_startup_message(const int argc,
                                        char** argv, char** envp);
        static void send_loaded_libraries();
        static void send_libinfo_message
            (const std::vector<std::pair<std::string, std::string> >& lib_vec);

        static void get_uds_path(std::string* uds_path_str);
        static void get_preload_path(std::string* ld_preload_path);
        static const std::string get_user_name(const uid_t user_id);
        static const std::string get_group_name(const gid_t group_id);
        static void get_md5_sum(const std::string& real_path,
                                std::string* md5_sum);
        static pid_t gettid();

        /* libc function map related functions */
        static void* get_sym_addr(const std::string& symbol);
        static void* add_sym_addr(const std::string& symbol);

        /* Backend communication related functions */
        static bool connect();
        static void disconnect();

    private:
        static __thread bool in_func_flag;
        static __thread UDSCommClient *comm_obj;
        static std::map<std::string, void*> *libc_func_map;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
