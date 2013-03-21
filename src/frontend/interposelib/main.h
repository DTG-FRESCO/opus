#include "uds_msg.pb.h"

void initialise(void) __attribute__((constructor));
void deinitialise(void) __attribute__((destructor));

typedef ::fresco::opus::IPCMessage::Header HeaderMessage;
typedef ::fresco::opus::IPCMessage::StartupMessage StartupMessage;
