#include "lock_guard.h"

#include <stdexcept>

/**
 * Acquire lock during object construction
 */
LockGuard::LockGuard(OPUSLock& _l) : lock(_l)
{
    lock.acquire();
}

/**
 * Acquire appropriate type of RW
 * lock during object construction
 */
LockGuard::LockGuard(OPUSLock& _l,
            const ReadWriteLock::LockType lock_type)
            : lock(_l)
{
    if (lock_type == ReadWriteLock::LockType::READ_LOCK)
        lock.acquire_rdlock();
    else if(lock_type == ReadWriteLock::LockType::WRITE_LOCK)
        lock.acquire_wrlock();
    else
        throw std::runtime_error("Invalid lock type");
}

/**
 * Releases the lock
 */
LockGuard::~LockGuard()
{
    lock.release();
}
