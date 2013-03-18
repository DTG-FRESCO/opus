#ifndef SRC_FRONTEND_INTERPOSELIB_LOG_H_
#define SRC_FRONTEND_INTERPOSELIB_LOG_H_

#ifdef DEBUG
#define DEBUG_LOG debug_msg
#else
#define DEBUG_LOG
#endif

void debug_msg(const char* msg, ...);

#endif // SRC_FRONTEND_INTERPOSELIB_LOG_H_
