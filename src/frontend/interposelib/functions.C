#include "functions.h"

#include <cstdint>
#ifndef __USE_GNU
  #define __USE_GNU
  #define __USE_GNU_DEFINED
#endif
#include <dlfcn.h>
#ifdef __USE_GNU_DEFINED
  #undef __USE_GNU
  #undef __USE_GNU_DEFINED
#endif
#include <errno.h>
#include <grp.h>
#include <fcntl.h>
#include <pwd.h>
#include <stdarg.h>
#include <string>

#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"

#include "gen_functions.C"
#include "io_functions.C"
#include "process_functions.C"
