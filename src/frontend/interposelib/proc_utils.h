#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include "uds_msg.pb.h"

typedef ::google::protobuf::Message Message;

class ProcUtils
{
    public:
        static uint64_t get_time();
        static bool test_and_set_flag(const bool value);
        static void serialise_and_send_data(const Message& msg_obj);

    private:
        static bool in_func_flag;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
