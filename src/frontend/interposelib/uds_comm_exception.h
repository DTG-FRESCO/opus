#ifndef _UDS_COMM_EXEP_
#define _UDS_COMM_EXEP_

#include <string>
#include "log.h"

class UDSCommException
{
    public:
        UDSCommException(const std::string& file, const int line, const std::string& msg)
        {
            file_name = file;
            line_no = line;
            message = msg;
        }

        void print_msg()
        {
            DEBUG_LOG("[%s:%d]: %s\n", file_name.c_str(), line_no, message.c_str());
        }

    private:
        int line_no;
        std::string file_name;
        std::string message;
};

#endif
