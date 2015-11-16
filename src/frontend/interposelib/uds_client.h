#ifndef SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_
#define SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_

#include <string>

/**
 * Unix Domain Socket client communication class
 */
class UDSCommClient
{
    public:
#ifdef TCP_SOCKET
	UDSCommClient(const std::string& addr, const int port);
        ~UDSCommClient();

        bool connect(const std::string& addr, const int port);
#else
	UDSCommClient(const std::string& path);
        ~UDSCommClient();

        bool connect(const std::string& uds_path);
#endif
        void close_connection();
        void shutdown();

        bool send_data(const std::string& data);
        bool send_data(const void* const data, const int data_size);

        bool is_opus_fd(const int fd);

        void protect_fd();

    private:
        int conn_fd;
        std::string uds_path;

        UDSCommClient(const UDSCommClient& copy_obj) {}
        UDSCommClient& operator=(const UDSCommClient& copy_obj);
};

#endif  // SRC_FRONTEND_INTERPOSELIB_UDS_CLIENT_H_
