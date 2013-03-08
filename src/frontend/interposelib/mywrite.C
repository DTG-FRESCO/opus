#include <stdio.h>
#include <string.h>
#ifndef __USE_GNU
 #define __USE_GNU
 #define __USE_GNU_DEFINED
#endif
#include <dlfcn.h>
#ifdef __USE_GNU_DEFINED
 #undef __USE_GNU
 #undef __USE_GNU_DEFINED
#endif
#include <unistd.h>
#include <stdlib.h>
#include <stdarg.h>

#include <iostream>
#include <string>
#include <unordered_map>

#include <stdint.h>
#include <errno.h>
#include <assert.h>

#include "log.h"
#include "uds_client.h"
#include "uds_msg.pb.h"
#include "proc_utils.h"


UDSCommClient* comm_ptr = NULL;
std::unordered_map<long, void*> funcMap;

void initialize(void) __attribute__((constructor));
void deinitialize(void) __attribute__((destructor));

typedef ssize_t (*LIBC_WRITE)(int fd, const void *buf, size_t len);
typedef ssize_t (*LIBC_FWRITE)(const void *ptr, size_t size, size_t nmemb, FILE *stream);
typedef int (*LIBC_PRINTF)(const char *format, ...);
typedef int (*LIBC_VPRINTF)(const char *format, va_list ap);
typedef int (*LIBC_PUTS)(const char *s);

typedef ::fresco::opus::IPCMessage::StartupMessage StartupMessage;
typedef ::fresco::opus::IPCMessage::Header HeaderMessage;
typedef ::google::protobuf::Message Message;

void checkError(const char* fileName, const int lineNum, void* ptr, const std::string& funcName)
{
    std::string errorMsg = "Pointer null for " + funcName;
    if(!ptr) throw(errorMsg.c_str());
}

static void exitHandler(void)
{
    //do cleanup work
}


//All libc function wrappers go here...
extern "C" ssize_t write(int fd, const void *buf, size_t len)
{
    uint64_t start_time = ProcUtils::get_time();

    ssize_t ret = ((LIBC_WRITE)funcMap[(long)write])(fd,buf,len);
    int error_value = errno;

    uint64_t end_time = ProcUtils::get_time();


}

extern "C" int printf(const char *format, ...)
{
    va_list list;

    va_start(list, format);
    int ret = ((LIBC_VPRINTF)funcMap[(long)vprintf])(format, list);
    va_end(list);

    return ret;
}

extern "C" int puts(const char *s)
{
    return ((LIBC_PUTS)funcMap[(long)puts])(s);
}

extern "C" size_t fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream)
{
    //if global is set, call function and return
    //else set global

    //Get current time
    int ret = ((LIBC_FWRITE)funcMap[(long)fwrite])(ptr, size, nmemb, stream);
    //capture ret and errno
    //Get end time

    //construct protobuf header message
    //Construct payload message using args and other data
    //Send

    return ret;
}

void updateMap(const std::string& funcName, const long funcAddr)
{
    try
    {
        void* fptr = dlsym(RTLD_NEXT, funcName.c_str());
        checkError(__FILE__,__LINE__,fptr, funcName);

        funcMap[funcAddr] = fptr;
    }
    catch(const char* msg)
    {
        std::cerr << msg << std::endl;
    }
}

void deinitialize()
{
    UDSCommClient::get_instance()->shutdown();
}


void serialize_and_send_data(const Message& msg_obj)
{
    int size = msg_obj.ByteSize();

    void* buf = malloc(size);
    if(NULL == buf)
    {
        DEBUG_LOG("[%s:%d]: Failed to allocate buffer\n",__FILE__,__LINE__);
        return;
    }

    msg_obj.SerializeToArray(buf, size);

    if(false == comm_ptr->send_data(buf, size))
    {
        DEBUG_LOG("[%s:%d]: Sending data failed\n",__FILE__,__LINE__);
        free(buf);
        return;
    }

    free(buf);
}

void send_startup_message()
{

    StartupMessage start_msg_obj;
    start_msg_obj.set_exec_name("foobar");
    start_msg_obj.set_cwd("/tmp/foo");
    start_msg_obj.set_cmd_line_args("-f null");
    start_msg_obj.set_user_name("nb466");
    start_msg_obj.set_group_name("nb466");
    start_msg_obj.set_ppid(getppid());

    const uint64_t msg_size = start_msg_obj.ByteSize();

    //Note: Should we store header message globally
    //and avoid reconstructing it each time?
    uint64_t current_time = ProcUtils::get_time();

    HeaderMessage hdr_msg_obj;
    hdr_msg_obj.set_timestamp(current_time);
    hdr_msg_obj.set_pid((uint64_t)getpid());
    hdr_msg_obj.set_start_msg_len(msg_size);
    hdr_msg_obj.set_lib_msg_len((uint64_t)0);
    hdr_msg_obj.set_func_msg_len((uint64_t)0);

    //Note: Should we make comm_ptr part of the
    //process utils class
    comm_ptr = UDSCommClient::get_instance();

    std::string uds_path = "./demo_socket";

    if(false == comm_ptr->connect(uds_path))
    {
        DEBUG_LOG("[%s:%d]: Socket connect failed\n",__FILE__,__LINE__);
        return;
    }

    serialize_and_send_data(hdr_msg_obj);
    serialize_and_send_data(start_msg_obj);

}

void initialize()
{

    /* Setup an exit handler */
    atexit(exitHandler);

    updateMap("write", (long)write);
    updateMap("fwrite", (long)fwrite);
    updateMap("printf", (long)printf);
    updateMap("vprintf", (long)vprintf);
    updateMap("puts", (long)puts);

    send_startup_message();

}
