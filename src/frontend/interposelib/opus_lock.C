#include "opus_lock.h"

#include <string.h>
#include <stdexcept>
#include "log.h"
#include "proc_utils.h"

/**
 * Dummy destructor to
 * appease the compiler
 */
OPUSLock::~OPUSLock() {}

/**
 * Constructor for simple lock.
 * Initializes a robust pthread mutex
 * lock with support for error checking.
 */
SimpleLock::SimpleLock()
{
    int err = 0;

    if ((err = pthread_mutexattr_init(&mutex_attr)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));

    if ((err = pthread_mutexattr_settype(&mutex_attr,
                        PTHREAD_MUTEX_ERRORCHECK)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));

    if ((err = pthread_mutexattr_setrobust(&mutex_attr,
                        PTHREAD_MUTEX_ROBUST)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));

    if ((err = pthread_mutex_init(&simple_lock, &mutex_attr)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Destructor for simple lock
 */
SimpleLock::~SimpleLock()
{
    destroy_lock();
}

/**
 * Destroys the NPTL mutex lock
 */
void SimpleLock::destroy_lock()
{
    int err = 0;

    if ((err = pthread_mutex_destroy(&simple_lock)) != 0)
    {
        /*
          Only inherited locks are destroyed and if
          this fails, we cannot do much apart from
          reallocating a new lock object.
        */
        DEBUG_LOG(ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                ProcUtils::get_error(err).c_str());
    }
}

/**
 * Acquires the NPTL mutex lock.
 * Brings the lock to a consistent state
 * if the lock ower dies unexpectedly
 */
void SimpleLock::acquire()
{
    int err = 0;

    while ((err = pthread_mutex_lock(&simple_lock)) != 0)
    {
        DEBUG_LOG(ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                ProcUtils::get_error(err).c_str());

        if (err == EOWNERDEAD)
        {
            if ((err = pthread_mutex_consistent(&simple_lock)) != 0)
                throw std::runtime_error(ProcUtils::get_error(err));

            continue;
        }
        throw std::runtime_error(ProcUtils::get_error(err));
    }
}

/**
 * Unlocks the NPTL mutex lock
 */
void SimpleLock::release()
{
    int err = 0;

    if ((err = pthread_mutex_unlock(&simple_lock)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Calls the base class constructor
 * that initializes a simple mutex lock.
 * Initializes a NPTL condition variable.
 */
ConditionLock::ConditionLock() : SimpleLock()
{
    int err = 0;

    if ((err = pthread_cond_init(&cond, NULL)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Destructor for condition lock
 */
ConditionLock::~ConditionLock()
{
    destroy_lock();
}

/**
 * Destroy's the condition variable
 */
void ConditionLock::destroy_lock()
{
    int err = 0;

    if ((err = pthread_cond_destroy(&cond)) != 0)
    {
        /*
          Only inherited locks are destroyed and if
          this fails, we cannot do much apart from
          reallocating a new lock object.
        */
        DEBUG_LOG(ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                ProcUtils::get_error(err).c_str());
    }
}

/**
 * Waits on a condition variable.
 * Returns when notified by a thread.
 */
void ConditionLock::wait()
{
    int err = 0;

    if ((err = pthread_cond_wait(&cond, &simple_lock)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Notify thread waiting on
 * a condition variable
 */
void ConditionLock::notify()
{
    int err = 0;

    if ((err = pthread_cond_signal(&cond)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Initializes a NPTL read write lock
 */
ReadWriteLock::ReadWriteLock()
{
    int err = 0;

    if ((err = pthread_rwlock_init(&rwlock, NULL)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Destroys a NPTL read write lock
 */
ReadWriteLock::~ReadWriteLock()
{
    destroy_lock();
}

/**
 * Obtains a read lock
 */
void ReadWriteLock::acquire_rdlock()
{
    int err = 0;

    if ((err = pthread_rwlock_rdlock(&rwlock)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Obtains a write lock
 */
void ReadWriteLock::acquire_wrlock()
{
    int err = 0;

    if ((err = pthread_rwlock_wrlock(&rwlock)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Release the read write lock
 */
void ReadWriteLock::release()
{
    int err = 0;

    if ((err = pthread_rwlock_unlock(&rwlock)) != 0)
        throw std::runtime_error(ProcUtils::get_error(err));
}

/**
 * Destroys the read write lock
 */
void ReadWriteLock::destroy_lock()
{
    int err = 0;

    if ((err = pthread_rwlock_destroy(&rwlock)) != 0)
    {
        /*
          Only inherited locks are destroyed and if
          this fails, we cannot do much apart from
          reallocating a new lock object.
        */
        DEBUG_LOG(ERROR, "[%s:%d]: %s\n", __FILE__, __LINE__,
                ProcUtils::get_error(err).c_str());
    }
}
