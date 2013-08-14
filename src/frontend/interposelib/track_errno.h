#ifndef SRC_FRONTEND_INTERPOSELIB_TRACK_ERRNO_H_
#define SRC_FRONTEND_INTERPOSELIB_TRACK_ERRNO_H_

#include <errno.h>

class TrackErrno
{
    public:
        TrackErrno(const int err_val)
        {
            saved_errno = err_val;
        }

        ~TrackErrno()
        {
            errno = saved_errno;
        }

        void operator=(const int err_val)
        {
            saved_errno = err_val;
        }

        operator int() const
        {
            return saved_errno;
        }

    private:
        int saved_errno;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_TRACK_ERRNO_H_
