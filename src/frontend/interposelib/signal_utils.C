#include "signal_utils.h"

#include <string.h>
#include <errno.h>
#include <map>
#include <vector>
#include <string>
#include <stdexcept>
#include <algorithm>
#include <unistd.h>
#include "log.h"
#include "proc_utils.h"
#include "message_util.h"
#include "lock_guard.h"

/**
 * Initialization of static class members
 */
std::vector<bool> *SignalUtils::sig_valid_ptr = NULL;
std::vector<SignalHandler*> *SignalUtils::sig_handler_vec = NULL;
OPUSLock *SignalUtils::sig_vec_lock = NULL;

/**
 * This variadic macro is used for both type one
 * and type two signal handlers. The handler
 * type is passed to the function macro along
 * with arguments for the handler.
 */
#define HANDLER_BODY(ptr_type, ...)                                 \
    ProcUtils::test_and_set_flag(true);                             \
                                                                    \
    bool interpose_off_flag = false;                                \
    FuncInfoMessage *func_msg = NULL;                               \
    GenericMessage *gen_msg = NULL;                                 \
                                                                    \
    sigset_t old_set;                                               \
    SignalUtils::block_all_signals(&old_set);                       \
                                                                    \
    try                                                             \
    {                                                               \
        func_msg = new FuncInfoMessage();                           \
        gen_msg = new GenericMessage();                             \
                                                                    \
        ProcUtils::use_alt_proto_msg(func_msg, gen_msg);            \
                                                                    \
        char sig_buf[MAX_INT32_LEN] = "";                           \
                                                                    \
        send_generic_msg(GenMsgType::SIGNAL, ProcUtils::opus_itoa(sig, sig_buf)); \
    }                                                               \
    catch(const std::exception& e)                                  \
    {                                                               \
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", e.what());              \
        interpose_off_flag = true;                                  \
    }                                                               \
                                                                    \
    void *real_handler = NULL;                                      \
    if ((real_handler = get_real_handler(sig)) != NULL)             \
    {                                                               \
        SignalUtils::restore_signal_mask(&old_set);                 \
                                                                    \
        ProcUtils::test_and_set_flag(interpose_off_flag);           \
        reinterpret_cast<ptr_type>(real_handler)(__VA_ARGS__);      \
        ProcUtils::test_and_set_flag(true);                         \
    }                                                               \
    else                                                            \
    {                                                               \
        ProcUtils::flush_buffered_data();                           \
                                                                    \
        char desc_buf[256];                                         \
        snprintf(desc_buf, 256, "Process terminating. Received signal %d", sig); \
        send_telemetry_msg(FrontendTelemetry::CRITICAL, desc_buf);  \
                                                                    \
        set_signal(sig, SIG_DFL);                                   \
        SignalUtils::restore_signal_mask(&old_set);                 \
                                                                    \
        if (raise(sig) != 0)                                        \
        {                                                           \
            LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, \
                        ProcUtils::get_error(errno).c_str());       \
            _exit(EXIT_FAILURE);                                    \
        }                                                           \
    }                                                               \
                                                                    \
    ProcUtils::restore_proto_tls();                                 \
    delete func_msg;                                                \
    delete gen_msg;                                                 \
                                                                    \
    ProcUtils::test_and_set_flag(false);


/**
 * Calls signal and performs error checks
 */
static inline void set_signal(const int sig, sighandler_t handler)
{
    sighandler_t ret = ::signal(sig, handler);
    if (ret == SIG_ERR)
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    ProcUtils::get_error(errno).c_str());
}

/**
 * OPUS signal handler wrapper
 * for type one signal handlers
 */
void SignalUtils::opus_type_one_signal_handler(int sig)
{
    HANDLER_BODY(sighandler_t, sig);
}

/**
 * OPUS signal handler wrapper
 * for type two signal handlers
 */
void SignalUtils::opus_type_two_signal_handler(int sig,
                                siginfo_t *info, void *u_ctx)
{
    HANDLER_BODY(SA_SIGACTION_PTR, sig, info, u_ctx);
}

/**
 * Blocks all signals from being
 * delivered to the calling thread.
 */
void SignalUtils::block_all_signals(sigset_t *old_set)
{
    sigset_t new_set;

    try
    {
        if (sigfillset(&new_set) < 0)
            throw std::runtime_error(ProcUtils::get_error(errno));

        if (pthread_sigmask(SIG_BLOCK, &new_set, old_set) < 0)
            throw std::runtime_error(ProcUtils::get_error(errno));
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", e.what());
    }
}

/**
 * Restores the signal mask to the
 * previous state for the calling thread.
 */
void SignalUtils::restore_signal_mask(sigset_t *old_set)
{
    try
    {
        if (pthread_sigmask(SIG_SETMASK, old_set, NULL) < 0)
            throw std::runtime_error(ProcUtils::get_error(errno));
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", e.what());
    }
}

/**
 * Wrapper for call to signal. A lock is obtained before
 * calling signal bacause we are tracking the previous
 * signal handler for a given signal and in a multi-threaded
 * process, obtaining a lock prevents the wrong
 * previous handler from being returned.
 */
void* SignalUtils::call_signal(const SIGNAL_POINTER& real_signal,
                                const int signum,
                                const sighandler_t& signal_handler,
                                SignalHandler *sh_obj,
                                sighandler_t& ret)
{
    void *prev_handler = NULL;

    sigset_t old_set;
    block_all_signals(&old_set);

    try
    {
        /* Obtain a lock */
        LockGuard guard(*sig_vec_lock);

        errno = 0;
        ret = (*real_signal)(signum, signal_handler);
        if (ret == SIG_ERR)
            throw std::runtime_error(ProcUtils::get_error(errno));

        prev_handler = SignalUtils::add_signal_handler(signum, sh_obj);
    }
    catch(const std::exception& e)
    {
        restore_signal_mask(&old_set);
        throw e;
    }

    restore_signal_mask(&old_set);
    return prev_handler;
}

/**
 * Wrapper for call to sigaction. A lock is obtained before
 * calling sigaction bacause we are tracking the previous
 * signal handler for a given signal and in a multi-threaded
 * process, obtaining a lock prevents the wrong previous
 * handler from being populated in the oldact structure.
 */
void* SignalUtils::call_sigaction(const SIGACTION_POINTER& real_sigaction,
                                    const int signum,
                                    const struct sigaction *sa,
                                    struct sigaction *oldact,
                                    SignalHandler *sh_obj,
                                    int& ret)
{
    void *prev_handler = NULL;

    sigset_t old_set;
    block_all_signals(&old_set);

    try
    {
        /* Obtain a lock */
        LockGuard guard(*sig_vec_lock);

        errno = 0;
        ret = (*real_sigaction)(signum, sa, oldact);
        if (ret < 0) throw std::runtime_error(ProcUtils::get_error(errno));

        prev_handler = SignalUtils::add_signal_handler(signum, sh_obj);
    }
    catch(const std::exception& e)
    {
        restore_signal_mask(&old_set);
        throw e;
    }

    restore_signal_mask(&old_set);
    return prev_handler;
}

/**
 * Retrieves the original handler to call.
 * Restores signal to default state if
 * SA_RESETHAND flag is set.
 */
void* SignalUtils::get_real_handler(const int sig)
{
    void *real_handler = NULL;

    try
    {
        LockGuard guard(*sig_vec_lock);
        SignalHandler *saved_handler = SignalUtils::get_signal_handler(sig);

        if (saved_handler && saved_handler->is_handler_callable())
        {
            real_handler = saved_handler->get_handler();

            if (saved_handler->get_reset_handler_flag())
            {
                SignalUtils::remove_signal_handler(sig);
                set_signal(sig, SignalUtils::opus_type_one_signal_handler);
            }
        }
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s", __FILE__, __LINE__, e.what());
    }

    return real_handler;
}


/**
 * Returns the signal handler object for a given signal.
 * This function must be called after acquiring sig_vec_lock
*/
SignalHandler* SignalUtils::get_signal_handler(const int sig)
{
    return (*sig_handler_vec)[sig];
}

/**
 * Stores the signal handler registered by the process for
 * a given signal in a vector and removes the previous
 * signal handler and returns it to the caller. This
 * function must be called after acquiring sig_vec_lock.
*/
void* SignalUtils::add_signal_handler(const int sig, SignalHandler* new_handler)
{
    void *real_handler = NULL;

    try
    {
        SignalHandler *prev_handler = get_signal_handler(sig);

        if (prev_handler) real_handler = prev_handler->get_handler();

        /*
           new_handler might be null if the call to signal/sigaction
           is to only check the previous signal disposition
        */
        if (new_handler)
        {
            (*sig_handler_vec)[sig] = new_handler;
            delete prev_handler;
            prev_handler = NULL;
        }
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return real_handler;
}

/**
 * Removes the stored signal handler from the signal vector.
 * This function must be called after acquiring sig_vec_lock
 */
void SignalUtils::remove_signal_handler(const int sig)
{
    try
    {
        SignalHandler *handler = (*sig_handler_vec)[sig];

        if (!handler) return;

        delete handler;
        (*sig_handler_vec)[sig] = NULL;
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}

bool SignalUtils::is_signal_valid(const int sig)
{
    return (*sig_valid_ptr)[sig];
}

/**
 * Installs signal handlers for
 * signals that we need to capture.
 */
bool SignalUtils::init_signal_capture()
{
    bool ret = true;

    try
    {
        static const int signal_list[] = {
            SIGFPE, SIGSEGV, SIGBUS, SIGABRT, SIGIOT,
            SIGTRAP, SIGSYS, SIGTERM, SIGINT, SIGQUIT,
            SIGHUP, SIGALRM, SIGVTALRM, SIGPROF, SIGIO,
            SIGPOLL, SIGTSTP, SIGTTIN, SIGTTOU, SIGPIPE,
            SIGXCPU, SIGXFSZ, SIGUSR1, SIGUSR2, SIGPWR,
            SIGSTKFLT, SIGILL, SIGSYS, SIGUNUSED };

        std::vector<int> signals_vec(signal_list,
                signal_list + sizeof(signal_list) / sizeof(int));

        /* We remove duplicates as some of the signals have the same value */
        sort(signals_vec.begin(), signals_vec.end());
        signals_vec.erase(unique(signals_vec.begin(), signals_vec.end()),
                                signals_vec.end());

        if (!sig_valid_ptr)
            sig_valid_ptr = new std::vector<bool>(NSIG, false);

        if (!sig_handler_vec)
            sig_handler_vec = new std::vector<SignalHandler*>(NSIG, NULL);

        struct sigaction sa;
        sa.sa_sigaction = SignalUtils::opus_type_two_signal_handler;
        sigfillset(&sa.sa_mask);
        sa.sa_flags = SA_SIGINFO;

        for (size_t i = 0; i < signals_vec.size(); ++i)
        {
            const int sig = signals_vec[i];
            (*sig_valid_ptr)[sig] = true;

            /* Get the current signal disposition */
            struct sigaction oldact;
            if (sigaction(sig, NULL, &oldact) < 0)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                        ProcUtils::get_error(errno).c_str());
                continue;
            }

            /* Store the current disposition */
            SignalHandler *sh_obj = new SAHandler(sig, oldact.sa_handler);
            add_signal_handler(sig, sh_obj);

            /* If the current disposition is SIG_IGN do not install the OPUS handler */
            if (oldact.sa_handler == SIG_IGN)
            {
                LOG_MSG(LOG_DEBUG, "[%s:%d]: %d signal disposition is SIG_IGN\n",
                            __FILE__, __LINE__, sig);
                continue;
            }

            /* Install the opus signal handler */
            if (sigaction(sig, &sa, NULL) < 0)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                        ProcUtils::get_error(errno).c_str());
                continue;
            }
        }
    }
    catch(const std::bad_alloc& e)
    {
        ret = false;
        ProcUtils::interpose_off(e.what());
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
    return ret;
}

/**
 * Initialize the lock used by the SignalUtils class.
 * Usually called during process startup.
 */
bool SignalUtils::initialize()
{
    bool ret = true;

    try
    {
        sig_vec_lock = new SimpleLock();
    }
    catch(const std::exception& e)
    {
        ret = false;
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

/**
 * Reinitialize the lock used by the SignalUtils class.
 * Usually called when a process inherits the address space
 * from its parent and needs to reset state.
 */
void SignalUtils::reset()
{
    try
    {
        if (sig_vec_lock)
        {
            delete sig_vec_lock;
            sig_vec_lock = NULL;
        }

        SignalUtils::initialize();
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}

/**
 * Restores the signal handlers for the process
 * to the state they were before interposition
 */
void SignalUtils::restore_all_signal_states()
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);


    sigset_t old_set;
    block_all_signals(&old_set);

    try
    {
        /* Obtain a lock */
        LockGuard guard(*sig_vec_lock);

        int sig = 0;
        std::vector<SignalHandler*>::iterator viter;

        if (!sig_handler_vec)
        {
            LOG_MSG(LOG_DEBUG, "[%s:%d]: sig_handler_vec not initialized\n",
                                __FILE__, __LINE__);
            restore_signal_mask(&old_set);
            return;
        }

        for (viter = sig_handler_vec->begin();
                viter != sig_handler_vec->end(); ++sig, ++viter)
        {
            if (!is_signal_valid(sig)) continue;

            SignalHandler* &handler = *viter;

            if (!handler)
            {
                LOG_MSG(LOG_DEBUG, "[%s:%d]: Setting signal %d to SIG_DFL\n",
                                    __FILE__, __LINE__, sig);
                set_signal(sig, SIG_DFL);
                continue;
            }

            if (handler->get_signal_func_type() == SignalHandler::SIGNAL)
            {
                LOG_MSG(LOG_DEBUG, "[%s:%d]: Setting signal %d using signal\n",
                                    __FILE__, __LINE__, sig);

                sighandler_t signal_handler = reinterpret_cast<sighandler_t>
                                                    (handler->get_handler());
                set_signal(sig, signal_handler);
            }
            else
            {
                struct sigaction act;
                handler->get_sigact_data(&act);

                LOG_MSG(LOG_DEBUG, "[%s:%d]: Setting signal %d using sigaction\n",
                                    __FILE__, __LINE__, sig);

                if (sigaction(sig, &act, NULL) < 0)
                {
                    LOG_MSG(LOG_DEBUG, "[%s:%d]: %s\n", __FILE__, __LINE__,
                                ProcUtils::get_error(errno).c_str());
                    continue;
                }
            }

            delete handler;
            handler = NULL;
        }
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s", __FILE__, __LINE__, e.what());
    }

    restore_signal_mask(&old_set);
}
