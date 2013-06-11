#ifndef SRC_FRONTEND_INTERPOSELIB_SIGNAL_HANDLER_H_
#define SRC_FRONTEND_INTERPOSELIB_SIGNAL_HANDLER_H_

#include <signal.h>

typedef void (*SA_SIGACTION_PTR)(int, siginfo_t *, void *);

/* Abstract Base class */
class SignalHandler
{
    public:
        SignalHandler(const int sig);
        virtual void operator()(const int sig) = 0;
        virtual void operator()(const int sig, siginfo_t *info, void *u_ctx) = 0;

        virtual void* get_handler() const = 0;
        bool is_handler_callable() { return callable_flag; }

        void check_and_reset_handler_flag(int *flags);
        bool get_reset_handler_flag() const { return reset_handler_flag; }

        virtual ~SignalHandler() = 0;

    protected:
        int sig_num;
        bool reset_handler_flag;
        bool callable_flag;
};


/*
    Deals with the single
    argument signal handler
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

/*
    Deals with the more
    elaborate signal handler
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
