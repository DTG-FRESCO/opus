#ifndef SRC_FRONTEND_INTERPOSELIB_SIGNAL_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_SIGNAL_UTILS_H_

#include <signal.h>
#include <map>
#include "signal_handler.h"

class SignalUtils
{
    public:
        static void opus_type_one_signal_handler(int sig);
        static void opus_type_two_signal_handler(int sig,
                                        siginfo_t *info, void *u_ctx);
        static void init_signal_capture();

        static void block_all_signals(sigset_t *old_set);
        static void restore_signal_mask(sigset_t *old_set);

        /* Signal map related functions */
        static SignalHandler* get_signal_handler(const int sig);
        static SignalHandler* add_signal_handler(const int sig,
                                                SignalHandler* new_handler);
        static void remove_signal_handler(const int sig);

    private:
        static std::map<int, SignalHandler*> sig_handle_map;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_SIGNAL_UTILS_H_
