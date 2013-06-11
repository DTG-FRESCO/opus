#ifndef SRC_FRONTEND_INTERPOSELIB_FUNCTIONS_H_
#define SRC_FRONTEND_INTERPOSELIB_FUNCTIONS_H_

#define NUM_BUFF_SIZE 64

#define DLSYM_CHECK(A) if ((A)==NULL){ \
  DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, "Critical error, failed to dlsym a function correctly."); \
  if ((error = dlerror()) != NULL){ \
    DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, error); \
  } \
  exit(EXIT_FAILURE); \
}

typedef void* (*PTHREAD_HANDLER)(void*);

struct OPUSThreadData
{
    PTHREAD_HANDLER real_handler;
    void *real_args;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_FUNCTIONS_H_
