#ifndef SRC_FRONTEND_INTERPOSELIB_TRACK_ERRNO_H_
#define SRC_FRONTEND_INTERPOSELIB_TRACK_ERRNO_H_

#include <errno.h>

/**
 * RAII class to track and restore the correct
 * value of errno within a glibc wrapper function.
 */
class TrackErrno
{
    public:
        /**
         * ctor strores the current errno value
         */
        TrackErrno(const int err_val)
        {
            saved_errno = err_val;
        }

        /**
         * dtor restores the saved errno value
         */
        ~TrackErrno()
        {
            errno = saved_errno;
        }

        /**
         * Updates the class object with a
         * new errno value if it is not zero.
         */
        void operator=(const int err_val)
        {
            if (err_val != 0) saved_errno = err_val;
        }

        /**
         * Can be used if the error object needs
         * to be assigned to an integer variable.
         */
        operator int() const
        {
            return saved_errno;
        }

    private:
        int saved_errno;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_TRACK_ERRNO_H_
