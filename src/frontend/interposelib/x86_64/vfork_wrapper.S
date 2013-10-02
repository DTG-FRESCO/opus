#include <sys/syscall.h>

.file   "vfork_wrapper.S"

#ifdef VFORK_INTERPOSE
    .text
    .globl vfork
    .type vfork, @function
vfork:
    pop     %rdi                # pop the return address
    call    push_ret_addr@PLT   # store return address in memory

    call    get_vfork_symbol@PLT
    call    *%rax               # Call real vfork

    mov     %rax, %r12          # copy the return value

    call    pop_ret_addr@PLT    # retrieve the return address
    push    %rax                # Push return address on the stack
    push    %r12                # Push return value on the stack

    mov     %r12, %rdi          # Pass the pid as argument to record
    call    vfork_record_interpose@PLT

    pop     %rax                # Pop the return value
    ret
#endif
