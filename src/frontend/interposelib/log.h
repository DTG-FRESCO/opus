#ifndef SRC_FRONTEND_INTERPOSELIB_LOG_H_
#define SRC_FRONTEND_INTERPOSELIB_LOG_H_

#define likely(x)       __builtin_expect(!!(x), 1)
#define unlikely(x)     __builtin_expect(!!(x), 0)

#ifdef LOGGING
#define DEBUG_LOG(level, ...)                   \
    if (unlikely(level >= Logging::get_current_level()))  \
        Logging::debug_msg(__VA_ARGS__)
#else
#define DEBUG_LOG(...)
#endif

enum {DEBUG = 1, ERROR, CRITICAL};

class Logging
{
    public:
        static void init_logging();
        static uint16_t get_current_level() { return logging_level; };

        static void debug_msg(const char* msg, ...);

    private:
        static uint16_t logging_level;
};


#endif // SRC_FRONTEND_INTERPOSELIB_LOG_H_
