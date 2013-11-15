#include <cstddef>
#include "signal_handler.h"

/**
 * Initializes common data used
 * by the derived classes
 */
SignalHandler::SignalHandler(const int sig)
                : sig_num(sig),
                reset_handler_flag(false),
                callable_flag(true)
{
    /* Do nothing */
}

/**
 * Dummy destructor
 */
SignalHandler::~SignalHandler()
{
    /* Do nothing */
}

/**
 * If the reset handler flag is set in call to
 * sigaction, the flag is removed as the OPUS
 * signal handling logic will take care of
 * setting the behaviour of this signal as default.
 */
void SignalHandler::check_and_reset_handler_flag(int *flags)
{
    if (*flags & SA_RESETHAND)
    {
        reset_handler_flag = true;
        *flags &= ~SA_RESETHAND;
    }
}

void SignalHandler::get_sigact_data(struct sigaction *act)
{
    if (sa_flags & SA_SIGINFO)
        act->sa_sigaction = reinterpret_cast<SA_SIGACTION_PTR>(get_handler());
    else act->sa_handler = reinterpret_cast<sighandler_t>(get_handler());

    act->sa_mask = sa_mask;
    act->sa_flags = sa_flags;
}

/**
 * Constructor for type one signal handler
 * called when the signal function is invoked.
 */
SAHandler::SAHandler(const int sig, sighandler_t handler)
                    : SignalHandler(sig), signal_handler(handler)
{
    if (signal_handler == SIG_DFL || signal_handler == SIG_IGN)
        callable_flag = false;

    signal_func_type = SignalHandler::SIGNAL;
}

/**
 * Constructor for type one signal handler,
 * called when the sigaction function is used
 * to install a signal handler of type sighandler_t
 */
SAHandler::SAHandler(const int sig, struct sigaction *act)
                    : SignalHandler(sig)
{
    if (!act) return;

    signal_func_type = SignalHandler::SIGACTION;
    signal_handler = act->sa_handler;
    sa_mask = act->sa_mask;
    sa_flags = act->sa_flags;

    if (signal_handler == SIG_DFL || signal_handler == SIG_IGN)
        callable_flag = false;

    check_and_reset_handler_flag(&act->sa_flags);
}

/**
 * Overload the function call operator to provide
 * functor behaviour for the signal handler object
 */
void SAHandler::operator()(const int sig)
{
    signal_handler(sig);
}

/**
 * Overload the function call operator to provide
 * functor behaviour for the signal handler object
 */
void SAHandler::operator()(const int sig, siginfo_t *info, void *u_ctx)
{
    this->operator()(sig);
}

/**
 * Returns the original signal handler function pointer
 */
void* SAHandler::get_handler() const
{
    return reinterpret_cast<void*>(signal_handler);
}

/**
 * Constructor for type two signal handler
 */
SASigaction::SASigaction(const int sig, SA_SIGACTION_PTR handler)
                    : SignalHandler(sig), signal_handler(handler)
{
}

/**
 * Constructor for type two signal handler with extra information
 */
SASigaction::SASigaction(const int sig, struct sigaction *act)
                    : SignalHandler(sig)
{
    if (!act) return;

    signal_func_type = SignalHandler::SIGACTION;
    signal_handler = act->sa_sigaction;
    sa_mask = act->sa_mask;
    sa_flags = act->sa_flags;

    check_and_reset_handler_flag(&act->sa_flags);
}

/**
 * Overload the function call operator to provide
 * functor behaviour for the signal handler object
 */
void SASigaction::operator()(const int sig)
{
    this->operator()(sig, NULL, NULL);
}

/**
 * Overload the function call operator to provide
 * functor behaviour for the signal handler object
 */
void SASigaction::operator()(const int sig, siginfo_t *info, void *u_ctx)
{
    signal_handler(sig, info, u_ctx);
}

/**
 * Returns the original signal handler function pointer
 */
void* SASigaction::get_handler() const
{
    return reinterpret_cast<void*>(signal_handler);
}

// TODO: Need a function that will return the old act
// data so that we can retore the signal state
