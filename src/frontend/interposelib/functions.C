#include "functions.h"

#include <cstdint>
#include <dlfcn.h>
#include <errno.h>
#include <grp.h>
#include <fcntl.h>
#include <pwd.h>
#include <stdarg.h>
#include <signal.h>
#include <string>

#include "log.h"
#include "proc_utils.h"
#include "message_util.h"

/** Include the generated interposition functions */
#include "gen_functions.C"
