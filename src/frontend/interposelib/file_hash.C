#include "file_hash.h"

#include <unistd.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <fcntl.h>
#include <string.h>
#include <sys/mman.h>
#include <openssl/md5.h>
#include <openssl/sha.h>
#include <openssl/crypto.h>
#include <linux/limits.h>

#include <stdexcept>
#include <sstream>
#include <iomanip>

#include "log.h"
#include "sys_util.h"

#define HASH_HDR_SZ 32

using std::string;

static int open_read_mode(const int fd)
{
    int new_fd = -1;

    char file_path[PATH_MAX + 1] = "";
    if (!SysUtil::get_path_from_fd(fd, file_path))
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: Could not obtain file path\n",
                __FILE__, __LINE__);
        return new_fd;
    }

    new_fd = open(file_path, O_RDONLY);
    if (new_fd < 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                SysUtil::get_error(errno).c_str());
        return new_fd;
    }

    return new_fd;
}

bool FileHash::get_git_hash(const char *file_path, char *git_hash)
{
    if (!file_path) return false;

    int fd = open(file_path, O_RDONLY);
    if (fd < 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                SysUtil::get_error(errno).c_str());
        return false;
    }

    get_git_hash(fd, git_hash);
    close(fd);

    return true;
}

bool FileHash::get_git_hash(FILE *fp, char *git_hash)
{
    if (!fp) return false;

    return FileHash::get_git_hash(fileno(fp), git_hash);
}

bool FileHash::get_git_hash(int fd, char *git_hash)
{
    bool retval = false;

    int flags = fcntl(fd, F_GETFL, 0);
    if (flags < 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                SysUtil::get_error(errno).c_str());
        return retval;
    }

    int new_fd = -1;
    if (!(flags & O_RDONLY || flags & O_RDWR))
    {
        LOG_MSG(LOG_DEBUG, "[%s:%d]: FD does not have read perms\n",
                __FILE__, __LINE__);

        int new_fd = open_read_mode(fd);
        if (new_fd >= 0) fd = new_fd;
    }

    try
    {
        struct stat stat_buf;
        if (fstat(fd, &stat_buf) < 0)
            throw std::runtime_error(SysUtil::get_error(errno));

        if (!S_ISREG(stat_buf.st_mode))
            throw std::runtime_error("Not a regular file");

        size_t file_size = stat_buf.st_size;
        if (file_size == 0)
            throw std::runtime_error("File size is zero");

        char hash_header[HASH_HDR_SZ] = "";  // "blob <file_size>\0"
        snprintf(hash_header, HASH_HDR_SZ, "%s %zu%c", "blob", file_size, '\0');

        SHA_CTX ctx;
        SHA1_Init(&ctx);
        SHA1_Update(&ctx, hash_header, strlen(hash_header) + 1);

        void *file_data = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);
        if (file_data == MAP_FAILED)
            throw std::runtime_error(SysUtil::get_error(errno));

        unsigned char hash_buf[SHA_DIGEST_LENGTH] = "";
        SHA1_Update(&ctx, file_data, file_size);
        SHA1_Final(hash_buf, &ctx);
        OPENSSL_cleanse(&ctx, sizeof(ctx));

        if (munmap(file_data, file_size) < 0)
        {
            LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                    SysUtil::get_error(errno).c_str());
        }

        for (int i = 0; i < SHA_DIGEST_LENGTH; i++)
            snprintf(git_hash + (i * 2), 3, "%02x", hash_buf[i]);

        retval = true;
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    if (new_fd >= 0) close(new_fd);

    return retval;
}

/**
 * Computes the md5 checksum for a given file
 */
void FileHash::get_md5_sum(const string& real_path, string *md5_sum)
{
    int fd = -1;

    try
    {
        struct stat buf;

        fd = open(real_path.c_str(), O_RDONLY);
        if (fd < 0) throw std::runtime_error(SysUtil::get_error(errno));

        if (fstat(fd, &buf) < 0)
            throw std::runtime_error(SysUtil::get_error(errno));

        size_t file_size = buf.st_size;
        void *data = mmap(NULL, file_size, PROT_READ, MAP_SHARED, fd, 0);
        if (data == MAP_FAILED)
            throw std::runtime_error(SysUtil::get_error(errno));

        unsigned char result[MD5_DIGEST_LENGTH] = "";
        if (MD5(reinterpret_cast<unsigned char*>(data),
                file_size, result) != NULL)
        {
            std::stringstream sstr;
            for (int i = 0; i < MD5_DIGEST_LENGTH; i++)
            {
                sstr << std::setfill('0') << std::setw(2)
                    << std::hex << (uint16_t)result[i];
            }
            *md5_sum = sstr.str();
        }

        if (munmap(data, file_size) < 0)
            throw std::runtime_error(SysUtil::get_error(errno));
    }
    catch(const std::exception& e)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    if (fd != -1) close(fd);
}

