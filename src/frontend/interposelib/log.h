#ifndef _LOG_H_
#define _LOG_H_

#ifdef DEBUG
#define DEBUG_LOG debug_msg
#else
#define DEBUG_LOG
#endif

char* getTimeStamp(char *time_stamp);
void debug_msg(const char* msg, ...);

#endif
