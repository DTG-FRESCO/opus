#ifndef SRC_FRONTEND_INTERPOSELIB_MAIN_H_
#define SRC_FRONTEND_INTERPOSELIB_MAIN_H_

static void initialise(void) __attribute__((constructor));
static void deinitialise(void) __attribute__((destructor));

#endif // SRC_FRONTEND_INTERPOSELIB_MAIN_H_
