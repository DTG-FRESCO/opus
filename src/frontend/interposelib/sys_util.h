#ifndef SRC_FRONTEND_INTERPOSELIB_SYS_UTIL_H_
#define SRC_FRONTEND_INTERPOSELIB_SYS_UTIL_H_

#include <string>

class SysUtil
{
    public:
        static uint64_t get_time();
        static void get_formatted_time(std::string* date_time);

        static char* get_env_val(const std::string& env_key);
        static const std::string get_user_name(const uid_t user_id);
        static const std::string get_group_name(const gid_t group_id);

        static const char* get_path_from_fd(const int fd, char *file_path);
        static const char* canonicalise_path(const char *path,
                                             char *actual_path);
        static const char* abs_path(const char *path, char *abs_path);
        static const char* dirfd_get_path(const int fd,
                           const char *path, char *path_res,
                           const char* (path_res_func)(const char*, char*));

        static const std::string get_error(const int err_num);
};

#endif  // SRC_FRONTEND_INTERPOSELIB_SYS_UTIL_H_
