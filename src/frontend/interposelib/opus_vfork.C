#include "opus_vfork.h"

#include <dlfcn.h>
#include <stdlib.h>
#include <stack>
#include <utility>
#include "log.h"
#include "proc_utils.h"
#include "message_util.h"

static __thread std::stack<std::pair<uint64_t, bool> > *proc_state_stack = NULL;
static __thread std::stack<uint64_t> *start_time_stack = NULL;

void* get_vfork_symbol(void)
{
    typedef pid_t (*VFORK_PTR)(void);
    static VFORK_PTR real_vfork = NULL;

    if (!real_vfork)
        real_vfork = (VFORK_PTR)ProcUtils::get_sym_addr("vfork");

    if (!start_time_stack) start_time_stack = new std::stack<uint64_t>;

    start_time_stack->push(ProcUtils::get_time()); // Store the vfork call start time

    return reinterpret_cast<void*>(real_vfork);
}

void vfork_record_interpose(pid_t pid)
{
    int errno_value = 0;
    bool prev_aggr_on_flag = false;

    // vfork returned error
    if (pid < 0) errno_value = pid;

    if (ProcUtils::test_and_set_flag(true)) return;

    if (pid == 0) // Child
    {
        // Set the correct pid
        ProcUtils::setpid(ProcUtils::__getpid());

        // Read previous message aggregation flag value
        prev_aggr_on_flag = ProcUtils::get_msg_aggr_flag();

        // Turn off aggregation
        ProcUtils::set_msg_aggr_flag(false);

        ProcUtils::send_startup_message();
        ProcUtils::test_and_set_flag(false);
        return;
    }

    // Parent

    uint64_t start_time = start_time_stack->top();
    start_time_stack->pop();

    uint64_t end_time = ProcUtils::get_time();

    // Set message aggregation flag to the previous state
    ProcUtils::set_msg_aggr_flag(prev_aggr_on_flag);

    // Restore the pid as child might have modified it
    ProcUtils::setpid(getpid());
    FuncInfoMessage *func_msg = static_cast<FuncInfoMessage*>(
            ProcUtils::get_proto_msg(PayloadType::FUNCINFO_MSG));

    // Keep interposition turned off
    if (!func_msg) return;

    set_func_info_msg(func_msg, "vfork", pid,
            start_time, end_time, errno_value);

    bool comm_ret = set_header_and_send(*func_msg, PayloadType::FUNCINFO_MSG);
    ProcUtils::test_and_set_flag(!comm_ret);
    func_msg->Clear();

    ProcUtils::test_and_set_flag(false);

}

void push_ret_addr(uint64_t ret_addr)
{
    bool prev_state = ProcUtils::test_and_set_flag(true);

    if (!proc_state_stack) proc_state_stack = new std::stack<std::pair<uint64_t, bool> >;

    /* Store return address and the interposition state of the process */
    std::pair<uint64_t, bool> proc_state = std::make_pair(ret_addr, prev_state);
    proc_state_stack->push(proc_state); // For parent
    proc_state_stack->push(proc_state); // For child

}

uint64_t pop_ret_addr()
{
    std::pair<uint64_t, bool> proc_state = proc_state_stack->top();
    proc_state_stack->pop();

    ProcUtils::test_and_set_flag(proc_state.second);
    return proc_state.first;
}
