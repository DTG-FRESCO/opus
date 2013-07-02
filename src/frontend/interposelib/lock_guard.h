#ifndef SRC_FRONTEND_INTERPOSELIB_LOCK_GUARD_H_
#define SRC_FRONTEND_INTERPOSELIB_LOCK_GUARD_H_

#include "opus_lock.h"

/**
 * An RAII class to release
 * a lock automatically once
 * the object goes out of scope
 */
class LockGuard
{
    public:
        LockGuard(OPUSLock&);
        LockGuard(OPUSLock&, const ReadWriteLock::LockType);
        ~LockGuard();

    private:
        LockGuard(const LockGuard&);

        OPUSLock& lock;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_LOCK_GUARD_H_
