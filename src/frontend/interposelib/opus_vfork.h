#ifndef SRC_FRONTEND_INTERPOSELIB_OPUS_VFORK_H_
#define SRC_FRONTEND_INTERPOSELIB_OPUS_VFORK_H_

#include <sys/types.h>
#include <unistd.h>
#include <cstdint>

extern "C" pid_t vfork(void); // implemented in assembly
extern "C" void* get_vfork_symbol(void);
extern "C" void vfork_record_interpose(pid_t pid);
extern "C" void push_ret_addr(uint64_t ret_addr);
extern "C" uint64_t pop_ret_addr();

#endif // SRC_FRONTEND_INTERPOSELIB_OPUS_VFORK_H_
