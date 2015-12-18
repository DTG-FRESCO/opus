#ifndef SRC_FRONTEND_INTERPOSELIB_MESSAGE_UTIL_H_
#define SRC_FRONTEND_INTERPOSELIB_MESSAGE_UTIL_H_

/**
 * This file contains protocol buffer message
 * utility functions that may be inlined.
 */
namespace
{
    using ::google::protobuf::Message;
    using ::fresco::opus::IPCMessage::KVPair;
    using ::fresco::opus::IPCMessage::GenMsgType;
    using ::fresco::opus::IPCMessage::PayloadType;
    using ::fresco::opus::IPCMessage::GenericMessage;
    using ::fresco::opus::IPCMessage::FuncInfoMessage;
    using ::fresco::opus::IPCMessage::LibInfoMessage;
    using ::fresco::opus::IPCMessage::StartupMessage;
    using ::fresco::opus::IPCMessage::FrontendTelemetry;
    using ::fresco::opus::IPCMessage::AggregationMessage;


    inline void set_header_data(Header *hdr_msg,
                                const uint64_t pay_msg_size,
                                const PayloadType pay_type)
    {
        hdr_msg->timestamp = SysUtil::get_time();
        hdr_msg->pid = static_cast<uint64_t>(ProcUtils::getpid());
        hdr_msg->payload_type = pay_type;
        hdr_msg->payload_len = pay_msg_size;
        hdr_msg->tid = ProcUtils::gettid();
        hdr_msg->sys_time = time(NULL);
    }

    inline bool set_header_and_send(const Message& pay_msg,
                                    const PayloadType pay_type)
    {
        struct Header hdr_msg;
        set_header_data(&hdr_msg, pay_msg.ByteSize(), pay_type);

        return ProcUtils::serialise_and_send_data(hdr_msg, pay_msg);
    }

    inline bool send_generic_msg(const GenMsgType gen_msg_type,
                                const char *desc)
    {
        GenericMessage *gen_msg = static_cast<GenericMessage*>(
                        ProcUtils::get_proto_msg(PayloadType::GENERIC_MSG));

        // Will turn off interposition
        if (!gen_msg) return false;

        gen_msg->set_msg_type(gen_msg_type);
        gen_msg->set_msg_desc(desc);

        bool ret_val = set_header_and_send(*gen_msg, PayloadType::GENERIC_MSG);
        gen_msg->Clear();

        return ret_val;
    }

    inline bool send_pre_func_generic_msg(const char *desc)
    {
        return send_generic_msg(GenMsgType::PRE_FUNC_CALL, desc);
    }

    inline void set_func_info_msg(FuncInfoMessage* func_msg,
            const char *desc,
            const uint64_t start_time,
            const uint64_t end_time,
            const int errno_value)
    {
        func_msg->set_func_name(desc);
        func_msg->set_begin_time(start_time);
        func_msg->set_end_time(end_time);
        func_msg->set_error_num(errno_value);
    }

    inline void set_func_info_msg(FuncInfoMessage* func_msg,
            const char *desc,
            const int ret,
            const uint64_t start_time,
            const uint64_t end_time,
            const int errno_value)
    {
        func_msg->set_ret_val(ret);
        set_func_info_msg(func_msg, desc, start_time, end_time, errno_value);
    }

    inline void send_telemetry_msg(const FrontendTelemetry::TelMsgType msg_type,
                                    const char *desc)
    {
        FrontendTelemetry tel_msg;

        tel_msg.set_msg_type(msg_type);
        tel_msg.set_desc(desc);

        set_header_and_send(tel_msg, PayloadType::TELEMETRY_MSG);
    }
}

#endif  // SRC_FRONTEND_INTERPOSELIB_MESSAGE_UTIL_H_
