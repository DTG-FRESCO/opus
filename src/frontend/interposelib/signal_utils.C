#include "signal_utils.h"

#include <string.h>
#include <errno.h>
#include <map>
#include <vector>
#include <string>
#include <stdexcept>
#include "log.h"
#include "proc_utils.h"
#include "message_util.h"

std::map<int, SignalHandler*> SignalUtils::sig_handle_map;

#define call_handler(...) (*saved_handler)(__VA_ARGS__)

#define HANDLER_BODY(...) \
    ProcUtils::test_and_set_flag(true); \
                                        \
    sigset_t old_set; \
    SignalUtils::block_all_signals(&old_set); \
                                              \
    send_generic_msg(GenMsgType::SIGNAL, std::to_string(sig));\
                                                            \
    SignalHandler *saved_handler = SignalUtils::get_signal_handler(sig);\
                                                                \
    if (saved_handler && saved_handler->is_handler_callable())\
    {\
        SignalUtils::restore_signal_mask(&old_set);\
                                                    \
        ProcUtils::test_and_set_flag(false); \
        call_handler(__VA_ARGS__);\
        ProcUtils::test_and_set_flag(true); \
                                \
        if (saved_handler->get_reset_handler_flag())\
        {                                               \
            SignalUtils::remove_signal_handler(sig); \
            set_signal(sig, SignalUtils::opus_type_one_signal_handler);\
        }\
    }\
    else\
    {\
        set_signal(sig, SIG_DFL);\
        SignalUtils::restore_signal_mask(&old_set);\
                                                    \
        if (raise(sig) != 0)\
        {\
            DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));\
            _exit(EXIT_FAILURE);\
        }\
    }\
                                        \
    ProcUtils::test_and_set_flag(false);



static inline void set_signal(const int sig, sighandler_t handler)
{
    sighandler_t ret = ::signal(sig, handler);
    if (ret == SIG_ERR)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
}

void SignalUtils::opus_type_one_signal_handler(int sig)
{
    HANDLER_BODY(sig);
}

void SignalUtils::opus_type_two_signal_handler(int sig,
                                siginfo_t *info, void *u_ctx)
{
    HANDLER_BODY(sig, info, u_ctx);
}

void SignalUtils::block_all_signals(sigset_t *old_set)
{
    sigset_t new_set;

    try
    {
        if (sigfillset(&new_set) < 0)
            throw std::runtime_error(strerror(errno));

        if (sigprocmask(SIG_BLOCK, &new_set, old_set) < 0)
            throw std::runtime_error(strerror(errno));
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", e.what());
    }
}

void SignalUtils::restore_signal_mask(sigset_t *old_set)
{
    try
    {
        if (sigprocmask(SIG_SETMASK, old_set, NULL) < 0)
            throw std::runtime_error(strerror(errno));
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", e.what());
    }
}

SignalHandler* SignalUtils::get_signal_handler(const int sig)
{
    SignalHandler *prev_handler = NULL;
    std::map<int, SignalHandler*>::iterator m_iter = sig_handle_map.find(sig);

    if (m_iter != sig_handle_map.end())
        prev_handler = m_iter->second;

    return prev_handler;
}

SignalHandler* SignalUtils::add_signal_handler(const int sig,
                                    SignalHandler* new_handler)
{
    SignalHandler *prev_handler = get_signal_handler(sig);

    if (prev_handler)
        sig_handle_map.erase(sig);

    sig_handle_map[sig] = new_handler;

    return prev_handler;
}

void SignalUtils::remove_signal_handler(const int sig)
{
    sig_handle_map.erase(sig);
}

void SignalUtils::init_signal_capture()
{
    static const int signal_list[] = { SIGFPE, SIGSEGV, SIGBUS, SIGABRT, SIGIOT,
                                    SIGTRAP, SIGSYS, SIGTERM, SIGINT, SIGQUIT,
                                    SIGHUP, SIGALRM, SIGVTALRM, SIGPROF, SIGIO,
                                    SIGPOLL, SIGTSTP, SIGTTIN, SIGTTOU, SIGPIPE,
                                    SIGXCPU, SIGXFSZ, SIGUSR1, SIGUSR2, SIGPWR,
                                    SIGSTKFLT, SIGILL, SIGSYS, SIGUNUSED };

    std::vector<int> signals_vec(signal_list,
                signal_list + sizeof(signal_list) / sizeof(int));

    struct sigaction sa;
    sa.sa_sigaction = SignalUtils::opus_type_two_signal_handler;
    sigfillset(&sa.sa_mask);
    sa.sa_flags = SA_SIGINFO;

    for (size_t i = 0; i < signals_vec.size(); ++i)
    {
        if (sigaction(signals_vec[i], &sa, NULL) < 0)
        {
            DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
            continue;
        }
    }
}
