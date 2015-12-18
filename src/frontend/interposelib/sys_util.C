#include "sys_util.h"

#include <time.h>
#include <stdlib.h>
#include <unistd.h>
#include <grp.h>
#include <pwd.h>
#include <errno.h>
#include <fcntl.h>
#include <libgen.h>
#include <linux/limits.h>

#include <cstdint>
#include <stdexcept>

#include "log.h"
#include "proc_utils.h"

using std::string;

/**
 * Returns the raw monotonic clock time of the system
 */
uint64_t SysUtil::get_time()
{
    struct timespec tp;

    if (clock_gettime(CLOCK_MONOTONIC_RAW, &tp) < 0)
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    SysUtil::get_error(errno).c_str());

    uint64_t nsecs = (uint64_t)tp.tv_sec * 1000000000UL + (uint64_t)tp.tv_nsec;

    return nsecs;
}

/**
 * Retrieves current time and date in a specific format
 */
void SysUtil::get_formatted_time(string* date_time)
{
    time_t unix_time;
    struct tm timeinfo;
    char buffer[128] = "";

    unix_time = time(NULL);
    localtime_r(&unix_time, &timeinfo);

    if (strftime(buffer, sizeof(buffer), "%Y-%m-%d %T", &timeinfo) == 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: strftime returned zero bytes\n",
                        __FILE__, __LINE__);
        return;
    }
    *date_time = buffer;
}

/**
 * Given an environment variable key
 * this function returns its value
 */
char* SysUtil::get_env_val(const string& env_key)
{
    char* val = getenv(env_key.c_str());
    if (!val)
    {
        string err_desc = "Could not read environment variable " + env_key;
        throw std::runtime_error(err_desc);
    }

    return val;
}

/**
 * Given a user ID, the user name string is returned
 */
const string SysUtil::get_user_name(const uid_t user_id)
{
    struct passwd pwd;
    struct passwd *result;
    char *buf = NULL;
    size_t bufsize = -1;
    string user_name_str = "";

    bufsize = sysconf(_SC_GETPW_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    try
    {
        buf = new char[bufsize];

        int ret = getpwuid_r(user_id, &pwd, buf, bufsize, &result);
        if (result == NULL)
        {
            if (ret == 0) throw std::runtime_error("User not found");
            else throw std::runtime_error(SysUtil::get_error(errno));
        }

        user_name_str = pwd.pw_name;
    }
    catch(const std::bad_alloc& e)
    {
        ProcUtils::interpose_off(e.what());
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    delete[] buf;
    return user_name_str;
}

/**
 * Given a group ID, the group name string is returned
 */
const string SysUtil::get_group_name(const gid_t group_id)
{
    struct group grp;
    struct group *result;
    char *buf = NULL;
    size_t bufsize = -1;
    string group_name_str = "";

    bufsize = sysconf(_SC_GETGR_R_SIZE_MAX);
    if (bufsize <= 0) bufsize = 1024;

    try
    {
        buf = new char[bufsize];

        int ret = getgrgid_r(group_id, &grp, buf, bufsize, &result);
        if (result == NULL)
        {
            if (ret == 0) throw std::runtime_error("Group not found");
            else throw std::runtime_error(SysUtil::get_error(errno));
        }

        group_name_str = grp.gr_name;
    }
    catch(const std::bad_alloc& e)
    {
        ProcUtils::interpose_off(e.what());
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    delete[] buf;
    return group_name_str;
}

const char* SysUtil::get_path_from_fd(const int fd, char *file_path)
{
    char proc_fd_path[PATH_MAX + 1] = "";
    snprintf(proc_fd_path, PATH_MAX, "/proc/self/fd/%d", fd);

    return SysUtil::canonicalise_path(proc_fd_path, file_path);
}


/**
 * Canonicalises a given pathname
 */
const char* SysUtil::canonicalise_path(const char *path, char *actual_path)
{
    char *real_path = realpath(path, actual_path);
    if (!real_path)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
        return path;
    }

    return real_path;
}

/**
 * Finds the absolute path of a given path
 */
const char* SysUtil::abs_path(const char *path, char *abs_path)
{
    // strdupa uses alloca
    char *dir = strdupa(path);
    char *base = strdupa(path);

    char *path_head = dirname(dir);
    char *path_tail = basename(base);

    char *real_path = realpath(path_head, abs_path);
    if (!real_path)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
        return path;
    }

    strcat(real_path, "/");
    strcat(real_path, path_tail);

    return real_path;
}

const char* SysUtil::dirfd_get_path(const int fd,
                                      const char *path,
                                      char *path_res,
                                      const char* (path_res_func)(const char*, char*))
{
    if(path[0] == '/')
    {
        return path_res_func(path, path_res);
    }
    else
    {
        char path_dir[PATH_MAX + 1] = "";
        char path_tmp[PATH_MAX + 1] = "";
        if(fd == AT_FDCWD)
        {
            if(getcwd(path_dir, PATH_MAX) == NULL)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                        SysUtil::get_error(errno).c_str());
                return path;
            }
        }
        else
        {
            SysUtil::get_path_from_fd(fd, path_dir);
        }
        snprintf(path_tmp, PATH_MAX, "%s/%s", path_dir, path);
        return path_res_func(path_tmp, path_res);
    }
}

/**
 * Given an errno value, this method uses a
 * thread safe implementation of strerror to
 * retrieve the error description.
 */
const string SysUtil::get_error(const int err_num)
{
    char err_buf[256] = "";

    char *err_str = strerror_r(err_num, err_buf, sizeof(err_buf));
    if (!err_str)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: strerror_r error: %d\n",
                    __FILE__, __LINE__, errno);
        return "";
    }

    return err_str;
}
