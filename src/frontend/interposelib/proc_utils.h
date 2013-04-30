#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include <string>

#include "protobuf_typedefs.h"

class ProcUtils
{
    public:
        static uint64_t get_time();
        static void get_formatted_time(std::string* date_time);
        static bool test_and_set_flag(const bool value);
        static void serialise_and_send_data(const Message& msg_obj);
        static void send_startup_message();
        static void get_uds_path(std::string* uds_path_str);
        static const std::string& get_preload_path();
        static const std::string get_user_name(const uid_t user_id);
        static const std::string get_group_name(const gid_t group_id);

    private:
        static bool in_func_flag;
        static std::string ld_preload_path;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
