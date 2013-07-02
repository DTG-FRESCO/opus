#ifndef SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_
#define SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_

#include <string>

/**
 * Unix Domain Socket client communication class
 */
class UDSCommClient
{
    public:
        UDSCommClient(const std::string& path);
        ~UDSCommClient();

        bool connect(const std::string& uds_path);
        bool reconnect();
        void close_connection();
        void shutdown();

        bool send_data(const std::string& data);
        bool send_data(const void* const data, const int data_size);

    private:
        int conn_fd;
        std::string uds_path;

        UDSCommClient(const UDSCommClient& copy_obj) {}
        UDSCommClient& operator=(const UDSCommClient& copy_obj);
};

#endif  // SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_
