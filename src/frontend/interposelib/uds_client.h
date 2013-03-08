#ifndef _UDS_CLIENT_H
#define _UDS_CLIENT_H

#include <string>

#define UNIX_PATH_MAX 108

class UDSCommClient
{
    public:
        static UDSCommClient* get_instance();
        bool connect(const std::string& uds_path);
        bool reconnect();
        void shutdown();

        bool send_data(const std::string& data);
        bool send_data(void* data, const int data_size);

    private:
        static UDSCommClient* comm_obj;
        int conn_fd;
        std::string uds_path;

        UDSCommClient() : conn_fd(-1) {}
        UDSCommClient(const UDSCommClient& copy_obj) {}
        UDSCommClient& operator=(const UDSCommClient& copy_obj);
};

#endif
