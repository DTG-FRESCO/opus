#ifndef SRC_FRONTEND_INTERPOSELIB_COMM_THREAD_H_
#define SRC_FRONTEND_INTERPOSELIB_COMM_THREAD_H_

#include <pthread.h>
#include <signal.h>
#include <queue>
#include <utility>

#include "uds_client.h"
#include "opus_lock.h"

class CommThread
{
    public:
        enum Event { START, STOP };

        static CommThread* get_instance();
        static void reset_instance();

        // Thread handler
        static void* poll_mailbox(void* args);

        bool start_thread();
        void shutdown_thread();

        bool enqueue_msg(void* msg, size_t msg_size);
        bool dequeue_msg(std::pair<void*, size_t>*);
        void add_to_write_batch(const std::pair<void*, size_t>& msg_pair,
                                    char*& batch_buf, bool force_flush);

        bool is_stop_event_set() const;
        void set_thread_event(const CommThread::Event);

        void send_message(const std::pair<void*, size_t>& msg_pair);
        void flush_remaining_msgs();

    private:
        static CommThread *comm_thread;
        UDSCommClient *uds_comm_obj;

        pthread_t comm_tid;
        pthread_attr_t attr;

        OPUSLock *queue_lock;
        std::queue<std::pair<void*, size_t> > msg_queue;
        volatile sig_atomic_t thread_event;

        CommThread();
        CommThread(const CommThread& copy_obj);
        CommThread& operator=(const CommThread& copy_obj);
        ~CommThread();
};

#endif // SRC_FRONTEND_INTERPOSELIB_COMM_THREAD_H_
