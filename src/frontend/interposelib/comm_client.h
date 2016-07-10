#ifndef SRC_FRONTEND_INTERPOSELIB_COMM_CLIENT_H_
#define SRC_FRONTEND_INTERPOSELIB_COMM_CLIENT_H_

#include <string>

class CommClient
{
    public:
        virtual ~CommClient() = 0;
        bool send_data(const std::string& data);
        bool send_data(const void* const data, const int data_size);
        bool is_opus_fd(const int fd);

    protected:
        void protect_fd();
        int get_conn_fd();
        void set_conn_fd(const int fd);
        void close_connection();

    private:
        int conn_fd;
};

/**
 * Unix domain socket client communication class
 */
class UDSCommClient : public CommClient
{
    public:
        UDSCommClient(const std::string& path);
        ~UDSCommClient();

    private:
        std::string uds_path;

        bool connect();
        UDSCommClient(const UDSCommClient& copy_obj) {}
        UDSCommClient& operator=(const UDSCommClient& copy_obj);
};

/**
 * TCP socket client communication class
 */
class TCPCommClient : public CommClient
{
    public:
        TCPCommClient(const std::string& addr, const uint16_t port);
        ~TCPCommClient();

    private:
        std::string ip_addr;
        uint16_t port;

        bool connect();
        TCPCommClient(const TCPCommClient& copy_obj) {}
        TCPCommClient& operator=(const TCPCommClient& copy_obj);
};

#endif  // SRC_FRONTEND_INTERPOSELIB_COMM_CLIENT_H_
