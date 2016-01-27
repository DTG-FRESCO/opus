#ifndef SRC_FRONTEND_INTERPOSELIB_FILE_HASH_H_
#define SRC_FRONTEND_INTERPOSELIB_FILE_HASH_H_

#include <stdio.h>
#include <string>

class FileHash
{
    public:
        static bool get_git_hash(const char *file_path, char *git_hash);
        static bool get_git_hash(FILE *fp, char *git_hash);
        static bool get_git_hash(int fd, char *git_hash);
        static void get_md5_sum(const std::string& real_path,
                                std::string *md5_sum);
};

#endif  // SRC_FRONTEND_INTERPOSELIB_FILE_HASH_H_
