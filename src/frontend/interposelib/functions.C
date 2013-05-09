#include "functions.h"

#include <cstdint>
#ifndef __USE_GNU
  #define __USE_GNU
  #define __USE_GNU_DEFINED
#endif
#include <dlfcn.h>
#ifdef __USE_GNU_DEFINED
  #undef __USE_GNU
  #undef __USE_GNU_DEFINED
#endif
#include <errno.h>
#include <grp.h>
#include <fcntl.h>
#include <pwd.h>
#include <stdarg.h>
#include <string>

#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"

using ::google::protobuf::Message;
using ::fresco::opus::IPCMessage::KVPair;
using ::fresco::opus::IPCMessage::Header;
using ::fresco::opus::IPCMessage::GenMsgType;
using ::fresco::opus::IPCMessage::PayloadType;
using ::fresco::opus::IPCMessage::GenericMessage;
using ::fresco::opus::IPCMessage::FuncInfoMessage;

static inline void set_header_and_send(const Message& pay_msg,
                                const PayloadType pay_type)
{
    const uint64_t msg_size = pay_msg.ByteSize();
    const uint64_t current_time = ProcUtils::get_time();

    Header hdr_msg;
    hdr_msg.set_timestamp(current_time);
    hdr_msg.set_pid((uint64_t)getpid());
    hdr_msg.set_payload_type(pay_type);
    hdr_msg.set_payload_len(msg_size);

    ProcUtils::serialise_and_send_data(hdr_msg, pay_msg);
}


static inline void send_pre_func_generic_msg(const std::string& desc)
{
    GenericMessage gen_msg;
    gen_msg.set_msg_type(GenMsgType::PRE_FUNC_CALL);
    gen_msg.set_msg_desc(desc);

    std::string date_time;
    ProcUtils::get_formatted_time(&date_time);
    gen_msg.set_sys_time(date_time);

    set_header_and_send(gen_msg, PayloadType::GENERIC_MSG);
}

static inline void set_func_info_msg(FuncInfoMessage* func_msg,
                                        const std::string& desc,
                                        const uint64_t start_time,
                                        const uint64_t end_time,
                                        const int errno_value)
{
    func_msg->set_func_name(desc);
    func_msg->set_begin_time(start_time);
    func_msg->set_end_time(end_time);
    func_msg->set_error_num(errno_value);
}

static inline void set_func_info_msg(FuncInfoMessage* func_msg,
                                        const std::string& desc,
                                        const int ret,
                                        const uint64_t start_time,
                                        const uint64_t end_time,
                                        const int errno_value)
{
    func_msg->set_ret_val(ret);
    set_func_info_msg(func_msg, desc, start_time, end_time, errno_value);
}


#include "gen_functions.C"
#include "io_functions.C"
#include "process_functions.C"
