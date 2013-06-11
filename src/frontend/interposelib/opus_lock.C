#include "opus_lock.h"

#include <errno.h>
#include <string.h>
#include <stdexcept>
#include "log.h"

OPUSLock::~OPUSLock() {}

/* SimpleLock begin */
SimpleLock::SimpleLock()
{
    if (pthread_mutexattr_init(&mutex_attr) != 0)
        throw std::runtime_error(strerror(errno));

    if (pthread_mutexattr_settype(&mutex_attr, PTHREAD_MUTEX_ERRORCHECK) != 0)
        throw std::runtime_error(strerror(errno));

    if (pthread_mutexattr_setrobust(&mutex_attr, PTHREAD_MUTEX_ROBUST) != 0)
        throw std::runtime_error(strerror(errno));

    if (pthread_mutex_init(&simple_lock, &mutex_attr) != 0)
        throw std::runtime_error(strerror(errno));
}

SimpleLock::~SimpleLock()
{
    destroy_lock();
}

void SimpleLock::destroy_lock()
{
    if (pthread_mutex_destroy(&simple_lock) != 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
}

void SimpleLock::acquire()
{
    while (pthread_mutex_lock(&simple_lock) != 0)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));

        if (errno == EOWNERDEAD)
        {
            if (pthread_mutex_consistent(&simple_lock) != 0)
                throw std::runtime_error(strerror(errno));

            continue;
        }
        throw std::runtime_error(strerror(errno));
    }
}

void SimpleLock::release()
{
    if (pthread_mutex_unlock(&simple_lock) != 0)
        throw std::runtime_error(strerror(errno));
}
/* SimpleLock end */

/* ConditionLock begin*/
ConditionLock::ConditionLock() : SimpleLock()
{
    if (pthread_cond_init(&cond, NULL) != 0)
        throw std::runtime_error(strerror(errno));
}

ConditionLock::~ConditionLock()
{
    destroy_lock();
}

void ConditionLock::destroy_lock()
{
    SimpleLock::destroy_lock();

    if (pthread_cond_destroy(&cond) != 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
}

void ConditionLock::wait()
{
    if (pthread_cond_wait(&cond, &simple_lock) != 0)
        throw std::runtime_error(strerror(errno));
}

void ConditionLock::notify()
{
    if (pthread_cond_signal(&cond) != 0)
        throw std::runtime_error(strerror(errno));
}
/* ConditionLock end */

/* ReadWriteLock begin */
ReadWriteLock::ReadWriteLock()
{
    if (pthread_rwlock_init(&rwlock, NULL) != 0)
        throw std::runtime_error(strerror(errno));
}

ReadWriteLock::~ReadWriteLock()
{
    destroy_lock();
}

void ReadWriteLock::acquire_rdlock()
{
    if (pthread_rwlock_rdlock(&rwlock) != 0)
        throw std::runtime_error(strerror(errno));
}

void ReadWriteLock::acquire_wrlock()
{
    if (pthread_rwlock_wrlock(&rwlock) != 0)
        throw std::runtime_error(strerror(errno));
}

void ReadWriteLock::release()
{
    if (pthread_rwlock_unlock(&rwlock) != 0)
        throw std::runtime_error(strerror(errno));
}

void ReadWriteLock::destroy_lock()
{
    if (pthread_rwlock_destroy(&rwlock) != 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
}
/* ReadWriteLock end*/
