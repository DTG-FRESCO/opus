#ifndef SRC_FRONTEND_INTERPOSELIB_OPUS_VFORK_H_
#define SRC_FRONTEND_INTERPOSELIB_OPUS_VFORK_H_

#include <sys/types.h>
#include <unistd.h>

extern "C" pid_t vfork(void); // implemented in assembly
extern "C" void* get_vfork_symbol(void);
extern "C" void vfork_send_startup_message(void);

#endif // SRC_FRONTEND_INTERPOSELIB_OPUS_VFORK_H_
