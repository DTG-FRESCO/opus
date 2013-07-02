#ifndef SRC_FRONTEND_INTERPOSELIB_UDS_COMM_EXCEPTION_H_
#define SRC_FRONTEND_INTERPOSELIB_UDS_COMM_EXCEPTION_H_

#include <string>
#include "opus_exception.h"

/**
 * Class for UDS communication exception
 */
class UDSCommException : public OPUSException
{
    public:
        UDSCommException(const std::string& file,
                        const int line, const std::string& msg)
                        : OPUSException(file, line, msg) {}
};

#endif  // SRC_FRONTEND_INTERPOSELIB_UDS_COMM_EXCEPTION_H_
