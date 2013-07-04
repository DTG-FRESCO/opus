#include <sys/syscall.h>

.file   "vfork_wrapper.S"

#ifdef VFORK_INTERPOSE
    .text
    .globl vfork
    .type vfork, @function
vfork:
    pop     %r15 # Save return address
    call    get_vfork_symbol@PLT
    call    *%rax # Call the real vfork
    push    %r15 # push return address on the stack
    push    %rax # push return value on the stack

    cmp     $0, %eax # pid_t is 32 bits
    je      __child_handler

    # Parent process
    pop     %rax
    ret

__child_handler:
    call    vfork_send_startup_message@PLT
    pop     %rax # Get saved return value
    ret

#endif
