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

static void set_user_name(KVPair*& tmp_arg, const uid_t user_id)
{
    struct passwd pwd;
    struct passwd *result;
    char *buf = NULL;
    size_t bufsize = -1;

    bufsize = sysconf(_SC_GETPW_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    buf = (char*)malloc(bufsize);
    if (buf == NULL)
    {
        DEBUG_LOG("[%s:%d]: malloc: %s\n", __FILE__, __LINE__, strerror(errno));
        tmp_arg->set_value("");
        return;
    }

    int ret = getpwuid_r(user_id, &pwd, buf, bufsize, &result);
    if (result == NULL)
    {
        if (ret == 0) DEBUG_LOG("[%s:%d]: User not found\n", __FILE__,__LINE__);
        else DEBUG_LOG("[%s:%d]: Error: %s\n", __FILE__, __LINE__, strerror(errno));

        tmp_arg->set_value("");
        free(buf);
        return;
    }

    tmp_arg->set_value(pwd.pw_name);
    free(buf);
}

static void set_group_name(KVPair*& tmp_arg, const gid_t group_id)
{
    struct group grp;
    struct group *result;
    char *buf = NULL;
    size_t bufsize = -1;

    bufsize = sysconf(_SC_GETGR_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    buf = (char*)malloc(bufsize);
    if (buf == NULL)
    {
        DEBUG_LOG("[%s:%d]: malloc: %s\n", __FILE__, __LINE__, strerror(errno));
        tmp_arg->set_value("");
        return;
    }

    int ret = getgrgid_r(group_id, &grp, buf, bufsize, &result);
    if (result == NULL)
    {
        if (ret == 0) DEBUG_LOG("[%s:%d]: Group not found\n", __FILE__,__LINE__);
        else DEBUG_LOG("[%s:%d]: Error: %s\n", __FILE__, __LINE__, strerror(errno));

        tmp_arg->set_value("");
        free(buf);
        return;
    }

    tmp_arg->set_value(grp.gr_name);
    free(buf);
}

#include "gen_functions.C"