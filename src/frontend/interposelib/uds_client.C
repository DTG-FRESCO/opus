#include "log.h"
#include "uds_client.h"
#include "uds_comm_exception.h"

#include <iostream>
#include <errno.h>
#include <string.h>
#include <stdio.h>

#include <stdint.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <sys/un.h>

UDSCommClient* UDSCommClient::comm_obj = NULL;

UDSCommClient* UDSCommClient::get_instance()
{
    if(comm_obj == NULL) 
        UDSCommClient::comm_obj = new UDSCommClient();

    return comm_obj;
}

bool UDSCommClient::connect(const std::string& path)
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",__FILE__,__LINE__,__PRETTY_FUNCTION__);

    if(uds_path.empty()) uds_path = path;

    try
    {
        struct sockaddr_un address;


        while( (conn_fd = ::socket(PF_UNIX, SOCK_STREAM, 0)) < 0)
        {
            if(errno == EINTR)
            {
                DEBUG_LOG("[%s:%d]: socket interrupted\n",__FILE__,__LINE__);
                continue;
            }
            else throw UDSCommException(__FILE__,__LINE__,strerror(errno));
        }

        memset(&address, 0, sizeof(struct sockaddr_un));

        address.sun_family = AF_UNIX;
        snprintf(address.sun_path, UNIX_PATH_MAX, "%s", uds_path.c_str());

        while(::connect(conn_fd, (struct sockaddr *)&address, sizeof(struct sockaddr_un)) < 0)
        {
            if(errno == EINTR)
            {
                DEBUG_LOG("[%s:%d]: connect interrupted\n",__FILE__,__LINE__);
                continue;
            }
            else if(errno == EINPROGRESS) break;
            else throw UDSCommException(__FILE__,__LINE__,strerror(errno));
        }
    }
    catch(UDSCommException& e)
    {
        e.print_msg();
        return false;
    }

    return true;
}

bool UDSCommClient::reconnect()
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",__FILE__,__LINE__,__PRETTY_FUNCTION__);

    return connect(uds_path);
}

bool UDSCommClient::send_data(void* data, const int data_size)
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",__FILE__,__LINE__,__PRETTY_FUNCTION__);

    size_t bytes_left = data_size;

    try
    {
        DEBUG_LOG("[%s:%d]: Bytes to be sent: %d\n",__FILE__,__LINE__,data_size);

        unsigned long total_bytes_sent = 0;

        while(total_bytes_sent < bytes_left)
        {
            ssize_t bytes_sent = ::send(conn_fd, (char*)data+total_bytes_sent, bytes_left, 0);
            if(bytes_sent < (ssize_t)0)
            {
                if(errno == EINTR)
                {
                    DEBUG_LOG("[%s:%d]: send interrupted\n",__FILE__,__LINE__);
                    continue;
                }
                else throw UDSCommException(__FILE__,__LINE__,strerror(errno));
            }

            DEBUG_LOG("[%s:%d]: Wrote %ld bytes to socket\n",__FILE__,__LINE__,bytes_sent);

            total_bytes_sent += bytes_sent;
            bytes_left -= bytes_sent;
        }

    }
    catch(UDSCommException& e)
    {
        e.print_msg();
        return false;
    }

    return true;
}

bool UDSCommClient::send_data(const std::string& data)
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",__FILE__,__LINE__,__PRETTY_FUNCTION__);

    const char* data_ptr = data.c_str();
    const int data_size = data.length();

    return send_data((void*)data_ptr, data_size);
}


void UDSCommClient::shutdown()
{
    DEBUG_LOG("[%s:%d]: Entering %s\n",__FILE__,__LINE__,__PRETTY_FUNCTION__);

    try
    {
        while(::close(conn_fd) < 0)
        {
            if(errno == EINTR)
            {
                DEBUG_LOG("[%s:%d]: close interrupted\n",__FILE__,__LINE__);
                continue;
            }
            else throw UDSCommException(__FILE__,__LINE__,strerror(errno));
        }
    }
    catch(UDSCommException& e)
    {
        e.print_msg();
    }

    if(comm_obj != NULL)
    {
        delete comm_obj;
        comm_obj = NULL;
    }
}
