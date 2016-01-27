#ifndef SRC_FRONTEND_INTERPOSELIB_LOG_H_
#define SRC_FRONTEND_INTERPOSELIB_LOG_H_

#include <cstdint>

#define likely(x)       __builtin_expect(!!(x), 1)
#define unlikely(x)     __builtin_expect(!!(x), 0)

#ifdef DEBUG_LOGGING
#define LOG_MSG(level, ...)                   \
    if (unlikely(level >= Logging::get_current_level()))  \
        Logging::log_msg(__VA_ARGS__)
#else
#define LOG_MSG(level, ...)
#endif

enum {LOG_DEBUG = 1, LOG_ERROR, LOG_CRITICAL};

class Logging
{
    public:
        static void init_logging();
        static uint16_t get_current_level() { return logging_level; };

        static void log_msg(const char* msg, ...);

    private:
        static uint16_t logging_level;
};


#endif // SRC_FRONTEND_INTERPOSELIB_LOG_H_
