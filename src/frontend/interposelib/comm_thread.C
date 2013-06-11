#include "comm_thread.h"

#include <unistd.h>
#include <errno.h>
#include <string.h>
#include <sched.h>
#include <sys/syscall.h>
#include <stdexcept>
#include <cstdlib>
#include "log.h"
#include "proc_utils.h"
#include "signal_utils.h"
#include "lock_guard.h"

#define MAX_BATCH_SIZE 4*1024

CommThread* CommThread::comm_thread = NULL;

CommThread* CommThread::get_instance()
{
    /*
        NOTE: If the singleton can be instantiated from
        any thread within the library use DCLP as per,
        "C++ and the Perils of Double-Checked Locking"
    */
    if (!comm_thread)
    {
        try
        {
            comm_thread = new CommThread();
        }
        catch(const std::exception& e)
        {
            DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
        }
    }
    return comm_thread;
}

/*
    Called by a child process
    spawed by call to fork.
*/
void CommThread::reset_instance()
{
    delete comm_thread;
    comm_thread = NULL;
}

CommThread::CommThread() : thread_event(CommThread::Event::STOP)
{
    queue_lock = new ConditionLock();

    if (!start_thread())
        throw std::runtime_error("CommThread start failed!!");
}

CommThread::~CommThread()
{
    /* Destroy all locks inherited */
    if (queue_lock)
    {
        delete queue_lock;
        queue_lock = NULL;
    }

    /*
        Clear queue contents and free
        the memory for each element
    */
    while (!msg_queue.empty())
    {
        std::pair<void*, size_t> msg_pair = msg_queue.front();

        void *msg = msg_pair.first;
        if (msg) delete static_cast<char*>(msg);

        msg_queue.pop();
    }

    /* Closes UDS connection */
    delete uds_comm_obj;
    uds_comm_obj = NULL;
}

bool CommThread::enqueue_msg(void* msg, size_t msg_size)
{

    DEBUG_LOG("[%s:%d]: %ld inside enqueue_msg\n",
                __FILE__, __LINE__, ProcUtils::gettid());

    if (!msg) return false;

    bool ret = true;

    try
    {
        LockGuard guard(*queue_lock);

        if (is_stop_event_set())
            throw std::runtime_error("Thread stop event set!!");

        size_t queue_size = msg_queue.size();
        msg_queue.push(std::make_pair(msg, msg_size));

        /* Comm thread must be waiting on condition */
        if (queue_size == 0)
            queue_lock->notify();
    }
    catch(const std::exception& e)
    {
        ret = false;
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

bool CommThread::dequeue_msg(std::pair<void*, size_t> *msg_pair)
{
    DEBUG_LOG("[%s:%d]: %ld inside dequeue_msg\n",
                __FILE__, __LINE__, ProcUtils::gettid());

    bool ret = true;

    try
    {
        LockGuard guard(*queue_lock);

        if (is_stop_event_set())
            throw std::runtime_error("Thread stop event set!!");

        while (msg_queue.empty())
        {
            if (is_stop_event_set())
                throw std::runtime_error("Thread stop event set!!");

            queue_lock->wait();
        }

        *msg_pair = msg_queue.front();
        msg_queue.pop();
    }
    catch(const std::exception& e)
    {
        ret = false;
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

void CommThread::set_thread_event(const CommThread::Event val)
{
    try
    {
        LockGuard guard(*queue_lock);
        thread_event = val;
        queue_lock->notify();
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }
}

bool CommThread::is_stop_event_set() const
{
    bool ret = false;

    try
    {
        if (thread_event == CommThread::Event::STOP)
            ret = true;
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

bool CommThread::start_thread()
{
    bool ret = true;

    try
    {
        std::string uds_path_str;
        ProcUtils::get_uds_path(&uds_path_str);

        if (uds_path_str.empty())
            throw std::runtime_error("Cannot connect!! UDS path is empty");

        uds_comm_obj = new UDSCommClient(uds_path_str);

        if (pthread_attr_init(&attr) != 0)
            throw std::runtime_error(strerror(errno));

        if (pthread_attr_setscope(&attr, PTHREAD_SCOPE_SYSTEM) != 0)
            throw std::runtime_error(strerror(errno));

        if (pthread_create(&comm_tid, &attr, CommThread::poll_mailbox, this) != 0)
            throw std::runtime_error(strerror(errno));

        set_thread_event(CommThread::Event::START);
    }
    catch(const std::exception& e)
    {
        ret = false;
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    return ret;
}

/*
    Should be called before program terminates
*/
void CommThread::shutdown_thread()
{
    /*
        Check if the stop event is already set,
        in case multiple threads try to shutdown
        the communication thread 
    */
    if (is_stop_event_set())
        return;

    set_thread_event(CommThread::Event::STOP);

    try
    {
        /* Notify the communication thread */
        LockGuard guard(*queue_lock);
        queue_lock->notify();
    }
    catch(const std::exception& e)
    {
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, e.what());
    }

    if (pthread_join(comm_tid, NULL) != 0)
        DEBUG_LOG("[%s:%d]: %s\n", __FILE__, __LINE__, strerror(errno));
}

void CommThread::flush_remaining_msgs()
{
    DEBUG_LOG("[%s:%d]: Flushing messages...\n", __FILE__, __LINE__);

    while (!msg_queue.empty())
    {
        std::pair<void*, size_t> msg_pair = msg_queue.front();
        msg_queue.pop();
        send_message(msg_pair);
    }
}

void* CommThread::poll_mailbox(void* args)
{
    /* Flag has TLS, set it to true */
    ProcUtils::test_and_set_flag(true);

    DEBUG_LOG("[%s:%d]: %ld inside poll_mailbox\n",
                __FILE__, __LINE__, ProcUtils::gettid());

    sigset_t old_set;
    SignalUtils::block_all_signals(&old_set);

    CommThread* comm_thread_obj = static_cast<CommThread*>(args);

    for (;;)
    {
        std::pair<void*, size_t> msg_pair;

        if (!comm_thread_obj->dequeue_msg(&msg_pair))
        {
            comm_thread_obj->flush_remaining_msgs();
            break;
        }

        comm_thread_obj->send_message(msg_pair);
    }

    DEBUG_LOG("[%s:%d]: %ld thread exiting...\n",
                __FILE__, __LINE__, ProcUtils::gettid());

    return NULL;
}

void CommThread::send_message(const std::pair<void*, size_t>& msg_pair)
{
    void *msg = msg_pair.first;
    size_t msg_size = msg_pair.second;

    if (!msg) return;

    if (!uds_comm_obj->send_data(msg, msg_size))
    {
        DEBUG_LOG("[%s:%d]: Could not send data of size %d\n",
                    __FILE__, __LINE__, msg_size);
    }

    delete static_cast<char*>(msg);
}

/* Function not used at present */
void CommThread::add_to_write_batch(const std::pair<void*, size_t>& msg_pair,
                                    char*& batch_buf, bool force_flush)
{
    static size_t bytes_left = MAX_BATCH_SIZE;
    static size_t start_pos = 0;

    if (force_flush)
    {
        if (!uds_comm_obj->send_data(batch_buf, MAX_BATCH_SIZE-bytes_left))
            DEBUG_LOG("[%s:%d]: Failed to send data\n", __FILE__, __LINE__);

        return;
    }

    void* msg = msg_pair.first;
    size_t msg_size = msg_pair.second;

    if (msg_size > bytes_left)
    {
        if (!uds_comm_obj->send_data(batch_buf, MAX_BATCH_SIZE-bytes_left))
            DEBUG_LOG("[%s:%d]: Failed to send data\n", __FILE__, __LINE__);

        bytes_left = MAX_BATCH_SIZE;
        start_pos = 0;
        memset(batch_buf, 0, MAX_BATCH_SIZE);
    }

    memcpy(batch_buf + start_pos, msg, msg_size);
    bytes_left -= msg_size;
    start_pos += msg_size;
}
