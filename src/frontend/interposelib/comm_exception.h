#ifndef SRC_FRONTEND_INTERPOSELIB_COMM_EXCEPTION_H_
#define SRC_FRONTEND_INTERPOSELIB_COMM_EXCEPTION_H_

#include <string>
#include "opus_exception.h"

/**
 * Class for communication client exception
 */
class CommException : public OPUSException
{
    public:
        CommException(const std::string& file, const int line,
                      const std::string& msg)
                      : OPUSException(file, line, msg) {}
};

#endif  // SRC_FRONTEND_INTERPOSELIB_COMM_EXCEPTION_H_
