#include <errno.h>
#include <fcntl.h>
#include <string.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netdb.h>
#include <linux/un.h>
#include <netinet/in.h>
#include <unistd.h>
#include <cstdint>
#include <string>
#include <stdexcept>

#include "log.h"
#include "comm_client.h"
#include "comm_exception.h"
#include "sys_util.h"

/* UDSCommClient */
UDSCommClient::UDSCommClient(const std::string& path) : uds_path(path)
{
    if (!connect())
        throw std::runtime_error("Connect failed!!");
}

UDSCommClient::~UDSCommClient()
{
    close_connection();
}

bool UDSCommClient::connect()
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
        __FILE__, __LINE__, __PRETTY_FUNCTION__);

    try
    {
        struct sockaddr_un address;

        int fd;
        while ((fd = ::socket(PF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0)) < 0)
        {
            if (errno == EINTR)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: socket interrupted\n",
                        __FILE__, __LINE__);
                continue;
            }
            else throw CommException(__FILE__, __LINE__,
                                        SysUtil::get_error(errno));
        }

        set_conn_fd(fd);
        protect_fd();

        memset(&address, 0, sizeof(struct sockaddr_un));

        address.sun_family = AF_UNIX;
        snprintf(address.sun_path, UNIX_PATH_MAX, "%s", uds_path.c_str());

        while (::connect(get_conn_fd(), (struct sockaddr *)&address,
                sizeof(struct sockaddr_un)) < 0)
        {
            if (errno == EINTR)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: connect interrupted\n",
                        __FILE__, __LINE__);
                continue;
            }
            else if (errno == EINPROGRESS) break;
            else throw CommException(__FILE__, __LINE__,
                                        SysUtil::get_error(errno));
        }
    }
    catch(const CommException& e)
    {
        e.print_msg();
        return false;
    }

    return true;
}

/* TCPCommClient */
TCPCommClient::TCPCommClient(const std::string& addr, const uint16_t port)
{
    this->ip_addr = addr;
    this->port = port;
    if (!connect())
        throw std::runtime_error("Connect failed!!");
}

TCPCommClient::~TCPCommClient()
{
    close_connection();
}


CommClient::~CommClient() {}

bool TCPCommClient::connect()
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
            __FILE__, __LINE__, __PRETTY_FUNCTION__);

    try
    {
        struct sockaddr_in address;

        int fd;
        while ((fd = ::socket(PF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0)) < 0)
        {
            if (errno == EINTR)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: socket interrupted\n",
                        __FILE__, __LINE__);
                continue;
            }
            else throw CommException(__FILE__, __LINE__,
                                        SysUtil::get_error(errno));
        }

        set_conn_fd(fd);
        protect_fd();

        memset(&address, 0, sizeof(struct sockaddr_in));

        address.sin_family = AF_INET;
        address.sin_port = htons(port);

        struct addrinfo *res;
        if(::getaddrinfo(ip_addr.c_str(), NULL, NULL, &res)!=0)
            throw CommException(__FILE__, __LINE__,
                    SysUtil::get_error(errno));

        memcpy(&(address.sin_addr),
                &((struct sockaddr_in *) res->ai_addr)->sin_addr,
                sizeof(struct in_addr));

        while (::connect(get_conn_fd(), (struct sockaddr *)&address,
                    sizeof(struct sockaddr_in)) < 0)
        {
            if (errno == EINTR)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: connect interrupted\n",
                        __FILE__, __LINE__);
                continue;
            }
            else if (errno == EINPROGRESS) break;
            else throw CommException(__FILE__, __LINE__,
                    SysUtil::get_error(errno));
        }
    }
    catch(const CommException& e)
    {
        e.print_msg();
        return false;
    }

    return true;
}

/**
 * Sends data_size bytes of data
 * pointed to by the data pointer
 */
bool CommClient::send_data(const void* const data, const int data_size)
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
        __FILE__, __LINE__, __PRETTY_FUNCTION__);

    size_t bytes_left = data_size;

    try
    {
        LOG_MSG(LOG_DEBUG, "[%s:%d]: Bytes to be sent: %d\n",
                    __FILE__, __LINE__, data_size);

        uint32_t total_bytes_sent = 0;

        while (bytes_left)
        {
            ssize_t bytes_sent = ::send(conn_fd,
                reinterpret_cast<const char*>(data)+total_bytes_sent,
                bytes_left, MSG_NOSIGNAL);
            if (bytes_sent < (ssize_t)0)
            {
                if (errno == EINTR)
                {
                    LOG_MSG(LOG_ERROR, "[%s:%d]: send interrupted\n",
                                __FILE__, __LINE__);
                    continue;
                }
                else throw CommException(__FILE__, __LINE__,
                                    SysUtil::get_error(errno));
            }

            LOG_MSG(LOG_DEBUG, "[%s:%d]: Wrote %ld bytes to socket\n",
                        __FILE__, __LINE__, bytes_sent);

            total_bytes_sent += bytes_sent;
            bytes_left -= bytes_sent;
        }

    }
    catch(const CommException& e)
    {
        e.print_msg();
        return false;
    }

    return true;
}

/**
 * Converts a string object to char
 * bytes and sends the data over UDS
 */
bool CommClient::send_data(const std::string& data)
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    const char* data_ptr = data.c_str();
    const int data_size = data.length();

    return send_data((const void*)data_ptr, data_size);
}

/**
 * Closes the UDS socket descriptor
 */
void CommClient::close_connection()
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    try
    {
        while (::close(conn_fd) < 0)
        {
            if (errno == EINTR)
            {
                LOG_MSG(LOG_ERROR, "[%s:%d]: close interrupted\n",
                        __FILE__, __LINE__);
                continue;
            }
            else throw CommException(__FILE__, __LINE__,
                            SysUtil::get_error(errno));
        }
    }
    catch(const CommException& e)
    {
        e.print_msg();
    }
}

/**
 * Checks if a given file descriptor is in use by OPUS
 */
bool CommClient::is_opus_fd(const int fd)
{
    return fd == conn_fd;
}

/**
 * Protect file descriptor by copying it to a high range
 */
void CommClient::protect_fd()
{
    LOG_MSG(LOG_DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);
    int max_fd;
    int new_fd;

    max_fd = sysconf(_SC_OPEN_MAX);
    if(errno != 0 || max_fd < 0)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: failed to elivate file descriptor\n",
                __FILE__, __LINE__);
        return;
    }

//  Reduce max_fd to give a larger range of possible landing sites.
    max_fd = max_fd * 0.95;

    new_fd = fcntl(conn_fd, F_DUPFD, max_fd);
    if(new_fd == -1)
    {
        LOG_MSG(LOG_ERROR, "[%s:%d]: failed to elivate file descriptor\n",
                __FILE__, __LINE__);
        return;
    }
    ::close(conn_fd);
    conn_fd = new_fd;
}

int CommClient::get_conn_fd()
{
    return conn_fd;
}

void CommClient::set_conn_fd(const int fd)
{
    conn_fd = fd;
}
