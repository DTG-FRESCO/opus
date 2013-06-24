#include <cstddef>
#include "signal_handler.h"

SignalHandler::SignalHandler(const int sig)
                : sig_num(sig),
                reset_handler_flag(false),
                callable_flag(true)
{
    /* Do nothing */
}

SignalHandler::~SignalHandler()
{
    /* Do nothing */
}

void SignalHandler::check_and_reset_handler_flag(int *flags)
{
    if (*flags & SA_RESETHAND)
    {
        reset_handler_flag = true;
        *flags &= ~SA_RESETHAND;
    }
}

SAHandler::SAHandler(const int sig, sighandler_t handler)
                    : SignalHandler(sig), signal_handler(handler)
{
    if (signal_handler == SIG_DFL || signal_handler == SIG_IGN)
        callable_flag = false;
}

SAHandler::SAHandler(const int sig, struct sigaction *act)
                    : SignalHandler(sig)
{
    if (!act) return;

    signal_handler = act->sa_handler;

    if (signal_handler == SIG_DFL || signal_handler == SIG_IGN)
        callable_flag = false;

    check_and_reset_handler_flag(&act->sa_flags);
}

void SAHandler::operator()(const int sig)
{
    signal_handler(sig);
}

void SAHandler::operator()(const int sig, siginfo_t *info, void *u_ctx)
{
    this->operator()(sig);
}

void* SAHandler::get_handler() const
{
    return reinterpret_cast<void*>(signal_handler);
}

SASigaction::SASigaction(const int sig, SA_SIGACTION_PTR handler)
                    : SignalHandler(sig), signal_handler(handler)
{
}

SASigaction::SASigaction(const int sig, struct sigaction *act)
                    : SignalHandler(sig)
{
    if (!act) return;

    signal_handler = act->sa_sigaction;

    check_and_reset_handler_flag(&act->sa_flags);
}

void SASigaction::operator()(const int sig)
{
    this->operator()(sig, NULL, NULL);
}

void SASigaction::operator()(const int sig, siginfo_t *info, void *u_ctx)
{
    signal_handler(sig, info, u_ctx);
}

void* SASigaction::get_handler() const
{
    return reinterpret_cast<void*>(signal_handler);
}
