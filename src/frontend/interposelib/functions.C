#include "functions.h"

#include <cstdint>
#include <dlfcn.h>
#include <errno.h>
#include <grp.h>
#include <fcntl.h>
#include <linux/limits.h>
#include <pwd.h>
#include <stdarg.h>
#include <signal.h>
#include <sys/socket.h>
#include <string>

#include "log.h"
#include "proc_utils.h"
#include "sys_util.h"
#include "file_hash.h"
#include "message_util.h"
#include "track_errno.h"

/** Include the generated interposition functions */
#include "gen_functions.C"
