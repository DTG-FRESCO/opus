#ifndef SRC_FRONTEND_INTERPOSELIB_PROTOBUF_TYPEDEFS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROTOBUF_TYPEDEFS_H_

#include "uds_msg.pb.h"

typedef ::google::protobuf::Message Message;
typedef ::fresco::opus::IPCMessage::KVPair KVPair;
typedef ::fresco::opus::IPCMessage::StartupMessage StartupMessage;
typedef ::fresco::opus::IPCMessage::FuncInfoMessage FuncInfoMessage;
typedef ::fresco::opus::IPCMessage::Header HeaderMessage;
typedef ::fresco::opus::IPCMessage::LibInfoMessage LibInfoMessage;
typedef ::fresco::opus::IPCMessage::GenericMessage GenericMessage;
typedef ::fresco::opus::IPCMessage::PayloadType PayloadType;
typedef ::fresco::opus::IPCMessage::GenMsgType GenMsgType;

#endif  // SRC_FRONTEND_INTERPOSELIB_PROTOBUF_TYPEDEFS_H_
