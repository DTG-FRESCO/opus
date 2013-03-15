#include <stdio.h>
#include <stdarg.h>
#include <time.h>
#include "log.h"

#define MAX_MSG_SIZE 4096

static void get_time_stamp(char *time_stamp)
{
    time_t current_time = time(0);
    struct tm date_time;

    localtime_r(&current_time, &date_time);
    strftime(time_stamp, 9, "%H:%M:%S", &date_time);
}

/*
   Prints message to stderr
*/
void debug_msg(const char* msg, ...)
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
