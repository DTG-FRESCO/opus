#ifndef SRC_FRONTEND_INTERPOSELIB_AGGR_MSG_H_
#define SRC_FRONTEND_INTERPOSELIB_AGGR_MSG_H_

#define DEFAULT_MAX_BUF_SIZE 65536

#include "uds_msg.pb.h"
#include "messaging.h"

class AggrMsg
{
    public:
        AggrMsg();
        ~AggrMsg();

        uint64_t get_cur_msg_size();
        bool add_msg(const ::fresco::opus::IPCMessage::FuncInfoMessage&
                        buf_func_info_msg);
        bool flush();

    private:
        uint32_t max_aggr_msg_size;
        uint32_t cur_msg_size;
        ::fresco::opus::IPCMessage::AggregationMessage *aggr_msg;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_AGGR_MSG_H_
