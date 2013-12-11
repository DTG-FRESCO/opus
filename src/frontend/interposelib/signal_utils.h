#ifndef SRC_FRONTEND_INTERPOSELIB_SIGNAL_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_SIGNAL_UTILS_H_

#include <signal.h>
#include <pthread.h>
#include <map>
#include <vector>
#include "signal_handler.h"
#include "opus_lock.h"

typedef sighandler_t (*SIGNAL_POINTER)(int signum, sighandler_t handler);
typedef int (*SIGACTION_POINTER)(int signum, const struct sigaction *act,
                                struct sigaction *oldact);

/**
 * Utility class for signal handling
 * functionality within OPUS.
 */
class SignalUtils
{
    public:
        static void opus_type_one_signal_handler(int sig);
        static void opus_type_two_signal_handler(int sig,
                                        siginfo_t *info, void *u_ctx);
        static bool init_signal_capture();
        static bool initialize();
        static void reset();
        static bool is_signal_valid(const int sig);

        static void block_all_signals(sigset_t *old_set);
        static void restore_signal_mask(sigset_t *old_set);
        static void* get_real_handler(const int sig);

        /* Wrappers for various signal APIs */
        static void* call_signal(const SIGNAL_POINTER& real_signal,
                                const int signum,
                                const sighandler_t& signal_handler,
                                SignalHandler *sh_obj,
                                sighandler_t& ret);

        static void* call_sigaction(const SIGACTION_POINTER& real_sigaction,
                                const int signum,
                                const struct sigaction *sa,
                                struct sigaction *oldact,
                                SignalHandler *sh_obj,
                                int& ret);

        /* Signal map related functions */
        static SignalHandler* get_signal_handler(const int sig);
        static void* add_signal_handler(const int sig,
                                        SignalHandler* new_handler);
        static void remove_signal_handler(const int sig);

        /* Function to restore signal states when interposition it turned off */
        static void restore_all_signal_states();


    private:
        static std::vector<bool> *sig_valid_ptr;
        static OPUSLock *sig_vec_lock;
        static std::vector<SignalHandler*> *sig_handler_vec;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_SIGNAL_UTILS_H_
