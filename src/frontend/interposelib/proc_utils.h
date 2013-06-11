#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include <string>
#include <vector>
#include <utility>
#include "uds_msg.pb.h"
#include "comm_thread.h"
#include "opus_lock.h"

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

        static void incr_appln_thread_count();
        static const int decr_appln_thread_count();

        /* libc function map related functions */
        static void* get_sym_addr(const std::string& symbol);
        static void* add_sym_addr(const std::string& symbol);
        static bool init_libc_interposition();
        static bool initialize_lock();
        static void reset_lock();

        static CommThread *comm_thread_obj; // made public for ease of use

    private:
        static __thread bool in_func_flag;
        static std::map<std::string, void*> libc_func_map;

        /* Count of application threads that are alive */
        static volatile sig_atomic_t appln_thread_count;
        static OPUSLock *appln_thread_count_lock;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
