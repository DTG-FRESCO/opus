#include <errno.h>
#include <string.h>
#include <stdio.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <linux/un.h>
#include <unistd.h>
#include <cstdint>
#include <string>
#include <stdexcept>
#include "log.h"
#include "proc_utils.h"
#include "uds_client.h"
#include "uds_comm_exception.h"

/**
 * Constructor establishes a UDS
 * connection to the OPUS backend
 */
UDSCommClient::UDSCommClient(const std::string& path) : conn_fd(-1)
{
    if (!connect(path))
        throw std::runtime_error("Connect failed!!");
}

/**
 * Destructor shuts down the UDS
 * connection with the OPUS backend
 */
UDSCommClient::~UDSCommClient()
{
    shutdown();
}

/**
 * Opens a UDS connection to the specified path
 */
bool UDSCommClient::connect(const std::string& path)
{
    DEBUG_LOG(DEBUG, "[%s:%d]: Entering %s\n",
        __FILE__, __LINE__, __PRETTY_FUNCTION__);

    if (uds_path.empty()) uds_path = path;

    try
    {
        struct sockaddr_un address;


        while ((conn_fd = ::socket(PF_UNIX, SOCK_STREAM | SOCK_CLOEXEC, 0)) < 0)
        {
            if (errno == EINTR)
            {
                DEBUG_LOG(ERROR, "[%s:%d]: socket interrupted\n", __FILE__, __LINE__);
                continue;
            }
            else throw UDSCommException(__FILE__, __LINE__,
                        ProcUtils::get_error(errno));
        }

        memset(&address, 0, sizeof(struct sockaddr_un));

        address.sun_family = AF_UNIX;
        snprintf(address.sun_path, UNIX_PATH_MAX, "%s", uds_path.c_str());

        while (::connect(conn_fd, (struct sockaddr *)&address,
            sizeof(struct sockaddr_un)) < 0)
        {
            if (errno == EINTR)
            {
                DEBUG_LOG(ERROR, "[%s:%d]: connect interrupted\n", __FILE__, __LINE__);
                continue;
            }
            else if (errno == EINPROGRESS) break;
            else throw UDSCommException(__FILE__, __LINE__,
                            ProcUtils::get_error(errno));
        }
    }
    catch(const UDSCommException& e)
    {
        e.print_msg();
        return false;
    }

    return true;
}

/**
 * Reestablishes the UDS connection
 * with the existing path.
 */
bool UDSCommClient::reconnect()
{
    DEBUG_LOG(DEBUG, "[%s:%d]: Entering %s\n",
        __FILE__, __LINE__, __PRETTY_FUNCTION__);

    return connect(uds_path);
}

/**
 * Sends data_size bytes of data
 * pointed to by the data pointer
 */
bool UDSCommClient::send_data(const void* const data, const int data_size)
{
    DEBUG_LOG(DEBUG, "[%s:%d]: Entering %s\n",
        __FILE__, __LINE__, __PRETTY_FUNCTION__);

    size_t bytes_left = data_size;

    try
    {
        DEBUG_LOG(DEBUG, "[%s:%d]: Bytes to be sent: %d\n",
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
                    DEBUG_LOG(ERROR, "[%s:%d]: send interrupted\n",
                                __FILE__, __LINE__);
                    continue;
                }
                else throw UDSCommException(__FILE__, __LINE__,
                                    ProcUtils::get_error(errno));
            }

            DEBUG_LOG(DEBUG, "[%s:%d]: Wrote %ld bytes to socket\n",
                        __FILE__, __LINE__, bytes_sent);

            total_bytes_sent += bytes_sent;
            bytes_left -= bytes_sent;
        }

    }
    catch(const UDSCommException& e)
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
bool UDSCommClient::send_data(const std::string& data)
{
    DEBUG_LOG(DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    const char* data_ptr = data.c_str();
    const int data_size = data.length();

    return send_data((const void*)data_ptr, data_size);
}

/**
 * Closes the UDS socket descriptor
 */
void UDSCommClient::close_connection()
{
    DEBUG_LOG(DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    try
    {
        while (::close(conn_fd) < 0)
        {
            if (errno == EINTR)
            {
                DEBUG_LOG(ERROR, "[%s:%d]: close interrupted\n", __FILE__, __LINE__);
                continue;
            }
            else throw UDSCommException(__FILE__, __LINE__,
                            ProcUtils::get_error(errno));
        }
    }
    catch(const UDSCommException& e)
    {
        e.print_msg();
    }
}

/**
 * Closes the UDS socket descriptor
 */
void UDSCommClient::shutdown()
{
    DEBUG_LOG(DEBUG, "[%s:%d]: Entering %s\n",
                __FILE__, __LINE__, __PRETTY_FUNCTION__);

    close_connection();
}
