#ifndef SRC_FRONTEND_INTERPOSELIB_OPUS_EXCEPTION_H_
#define SRC_FRONTEND_INTERPOSELIB_OPUS_EXCEPTION_H_

#include <stdio.h>
#include <string>

class OPUSException
{
    public:
        OPUSException(const std::string& file,
                        const int line, const std::string& msg)
        {
            file_name = file;
            line_no = line;
            message = msg;
        }

        void print_msg() const
        {
            DEBUG_LOG("[%s:%d]: %s\n", file_name.c_str(),
                        line_no, message.c_str());
        }

    private:
        int line_no;
        std::string file_name;
        std::string message;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_OPUS_EXCEPTION_H_
