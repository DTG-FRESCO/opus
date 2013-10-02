#include <sys/syscall.h>

.file   "vfork_wrapper.S"

#ifdef VFORK_INTERPOSE
    .text
    .globl vfork
    .type vfork, @function
vfork:
    call    push_ret_addr       # Ret addr is passed on the stack
    pop     %edi                # pop the return address into a register

    call    get_vfork_symbol
    call    *%eax               # Call real vfork

    mov     %eax, %edi          # copy the return value

    call    pop_ret_addr        # retrieve the return address
    push    %eax                # push return address on the stack
    push    %edi                # push return value on the stack

    call    vfork_record_interpose # pid arg is on the stack

    pop     %eax                # pop the return value
    ret
#endif
