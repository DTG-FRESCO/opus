#ifndef SRC_FRONTEND_INTERPOSELIB_SIGNAL_HANDLER_H_
#define SRC_FRONTEND_INTERPOSELIB_SIGNAL_HANDLER_H_

#include <signal.h>
#include <cstdint>

typedef void (*SA_SIGACTION_PTR)(int, siginfo_t *, void *);

/**
 * Abstract base class for signal handling logic.
 * The OPUS front-end stores and tracks the application's
 * signal handlers along with relevant flags.
 */
class SignalHandler
{
    public:

        enum { SIGNAL = 1, SIGACTION = 2 };

        SignalHandler(const int sig);
        virtual void operator()(const int sig) = 0;
        virtual void operator()(const int sig, siginfo_t *info, void *u_ctx) = 0;

        virtual void* get_handler() const = 0;
        bool is_handler_callable() { return callable_flag; }

        void check_and_reset_handler_flag(int *flags);
        bool get_reset_handler_flag() const { return reset_handler_flag; }

        uint16_t get_signal_func_type() const { return signal_func_type; }
        void get_sigact_data(struct sigaction *act);

        virtual ~SignalHandler() = 0;

    protected:
        int sig_num;
        bool reset_handler_flag;
        bool callable_flag;
        uint16_t signal_func_type;

        // Need this when restoring signal state
        // after interposition is turned off
        sigset_t sa_mask;
        int sa_flags;
};


/**
 * Deals with type one signal handler
 * the takes a single argument
 */
class SAHandler : public SignalHandler
{
    public:
        SAHandler(const int sig, sighandler_t handler);
        SAHandler(const int sig, struct sigaction *act);

        void operator()(const int sig);
        void operator()(const int sig, siginfo_t *info, void *u_ctx);
        void* get_handler() const;

    private:
        sighandler_t signal_handler;
};

/**
 * Deals with type two signal handler
 * that takes three arguments.
 */
class SASigaction : public SignalHandler
{
    public:
        SASigaction(const int sig, SA_SIGACTION_PTR handler);
        SASigaction(const int sig, struct sigaction *act);

        void operator()(const int sig);
        void operator()(const int sig, siginfo_t *info, void *u_ctx);
        void* get_handler() const;

    private:
        SA_SIGACTION_PTR signal_handler;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_SIGNAL_HANDLER_H_
