#ifndef SRC_FRONTEND_GEN_BOILER_FUNCTIONS_H_
#define SRC_FRONTEND_GEN_BOILER_FUNCTIONS_H_

#include "protobuf_typedefs.h"

#define NUM_BUFF_SIZE 50

#define DLSYM_CHECK(A) if ((A)==NULL){ \
  DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, "Critical error, failed to dlsym a function correctly."); \
  if ((error = dlerror()) != NULL){ \
    DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, error); \
  } \
  exit(EXIT_FAILURE); \
}

#endif  // SRC_FRONTEND_GEN_BOILER_FUNCTIONS_H_
