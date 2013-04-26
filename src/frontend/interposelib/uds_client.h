#ifndef SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_
#define SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_

#include <string>

class UDSCommClient
{
    public:
        static UDSCommClient* get_instance();
        bool connect(const std::string& uds_path);
        bool reconnect();
        void close_connection();
        void shutdown();

        bool send_data(const std::string& data);
        bool send_data(const void* const data, const int data_size);

    private:
        static UDSCommClient* comm_obj;
        int conn_fd;
        std::string uds_path;

        UDSCommClient() : conn_fd(-1) {}
        UDSCommClient(const UDSCommClient& copy_obj) {}
        UDSCommClient& operator=(const UDSCommClient& copy_obj);
};

#endif  // SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_
