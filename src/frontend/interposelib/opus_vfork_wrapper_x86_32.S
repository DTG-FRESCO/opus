#include <sys/syscall.h>

.file   "opus_vfork_wrapper_x86_32.S"

#ifdef VFORK_INTERPOSE
    .text
    .globl vfork
    .type vfork, @function
vfork:
    pop     %ebx # Save return address
    call    get_vfork_symbol
    call    *%eax # Call the real vfork
    push    %ebx # push return address on the stack
    push    %eax # push return value on the stack

    cmp     $0, %eax # pid_t is 32 bits
    je      __child_handler

    # Parent process
    pop     %eax
    ret

__child_handler:
    call    vfork_send_startup_message
    pop     %eax # Get saved return value
    ret

#endif
