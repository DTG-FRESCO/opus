#include "aggr_msg.h"

#include <stdexcept>
#include "log.h"
#include "proc_utils.h"
#include "message_util.h"

AggrMsg::AggrMsg()
{
    cur_msg_size = 0;
    max_aggr_msg_size = DEFAULT_MAX_BUF_SIZE;

    char *aggr_msg_size = ProcUtils::get_env_val("OPUS_MAX_AGGR_MSG_SIZE");
    if (aggr_msg_size) max_aggr_msg_size = atoi(aggr_msg_size);

    try
    {
        aggr_msg = new AggregationMessage();
    }
    catch(const std::bad_alloc& e)
    {
        throw e;
    }
}

uint64_t AggrMsg::get_cur_msg_size()
{
    return cur_msg_size;
}


bool AggrMsg::add_msg(const FuncInfoMessage& buf_func_info_msg)
{
    bool ret = true;

    const uint32_t msg_size = buf_func_info_msg.ByteSize();
    char *msg_buf = NULL;

    try
    {
        msg_buf = new char[msg_size];

        if (!buf_func_info_msg.SerializeToArray(msg_buf, msg_size))
            throw std::runtime_error("Failed to serialise function info msg");

        aggr_msg->add_messages(msg_buf, msg_size);
        cur_msg_size += msg_size;

        if (cur_msg_size >= max_aggr_msg_size)
            ret = flush();
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        ret = false;
    }

    delete[] msg_buf;
    return ret;
}

bool AggrMsg::flush()
{
    bool ret = true;

    if (cur_msg_size == 0) return true;

    Header hdr_msg;
    set_header_data(&hdr_msg, aggr_msg->ByteSize(), PayloadType::AGGREGATION_MSG);

    if (!ProcUtils::serialise_and_send_data(hdr_msg, *aggr_msg))
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: Failed sending AGGREGATION_MSG\n",
                            __FILE__, __LINE__);
        return false;
    }

    cur_msg_size = 0;
    aggr_msg->Clear();
    return ret;
}
