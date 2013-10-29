#include <stdio.h>
#include <stdarg.h>
#include <time.h>
#include <stdexcept>
#include "log.h"
#include "proc_utils.h"

#define MAX_MSG_SIZE 4096
#define LOGGING_OFF 999

uint16_t Logging::logging_level = LOGGING_OFF;

/**
 * Gets the current time in H:M:S format
 */
static void get_time_stamp(char *time_stamp)
{
    time_t current_time = time(0);
    struct tm date_time;

    localtime_r(&current_time, &date_time);
    strftime(time_stamp, 9, "%H:%M:%S", &date_time);
}

/**
 *  Logs debug messages to standard error
 */
void Logging::debug_msg(const char* msg, ...)
{
    va_list list;
    char time_stamp[16] = "";
    char line[MAX_MSG_SIZE] = "";

    get_time_stamp(time_stamp);

    va_start(list, msg);

    snprintf(line, MAX_MSG_SIZE, "%s:%s", time_stamp, msg);
    vfprintf(stderr, line, list);

    va_end(list);
}

void Logging::init_logging()
{
    try
    {
        char *log_level = ProcUtils::get_env_val("OPUS_LOG_LEVEL");
        logging_level = atoi(log_level);

        if (logging_level < DEBUG || logging_level > CRITICAL)
        {
            logging_level = LOGGING_OFF;
            throw std::runtime_error("Invalid logging level");
        }

        DEBUG_LOG(DEBUG, "[%s:%d]: Logging level set to %d\n",
                        __FILE__, __LINE__, logging_level);
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG(ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}
