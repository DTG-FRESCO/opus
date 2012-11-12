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
#include <signal.h>

#include <iostream>
#include <string>
#include <unordered_map>

std::unordered_map<long, void*> funcMap;

void initialize(void) __attribute__((constructor));
typedef ssize_t (*LIBC_WRITE)(int fd, const void *buf, size_t len);
typedef int (*LIBC_PRINTF)(const char *format, ...);
typedef int (*LIBC_VPRINTF)(const char *format, va_list ap);
typedef int (*LIBC_PUTS)(const char *s);
typedef void (*LIBC__EXIT)(int status);
typedef pid_t (*LIBC_FORK)(void);

void checkError(const char* fileName, const int lineNum, void* ptr, const std::string& funcName)
{
    std::string errorMsg = "Pointer null for " + funcName;
    if(!ptr) throw(errorMsg.c_str());
}

static void exitHandler(void)
{
    printf("Inside exit handler\n");
    //do cleanup work
}

//All libc function wrappers go here...
extern "C" ssize_t write(int fd, const void *buf, size_t len)
{
   // Do our stuff here

    return ((LIBC_WRITE)funcMap[(long)write])(fd,buf,len);
}

extern "C" int printf(const char *format, ...)
{
    va_list list;
    va_start(list, format);

    // Do other work
    //int ret = ((LIBC_PRINTF)funcMap[(long)printf])(format, list);
    int ret = ((LIBC_VPRINTF)funcMap[(long)vprintf])("mystuff", list);

    va_end(list);

    return ret;
}

extern "C" int puts(const char *s)
{
   // Do our stuff here
   return ((LIBC_PUTS)funcMap[(long)puts])("foobar");
}

extern "C" pid_t fork(void)
{
    printf("Inside my fork\n");
    return ((LIBC_FORK)funcMap[(long)fork])();
}

extern "C" void _exit(int status)
{
    printf("Inside our _exit\n");
    ((LIBC__EXIT)funcMap[(long)_exit])(status);
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

// Setup handler for SIGSEGV
static void handleSegv(int sig, siginfo_t *si, void *unused)
{
    printf("Got SIGSEGV at address: 0x%lx\n",(long) si->si_addr);
    exit(1);
}

void setSignalHandler()
{
    struct sigaction sa;

    sa.sa_flags = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);
    sa.sa_sigaction = handleSegv;

    if(sigaction(SIGSEGV, &sa, NULL) < 0)
        perror("sigaction");
}


void initialize(void)
{
    //printf("Inside initialize\n");
    atexit(exitHandler);

    setSignalHandler();

    updateMap("write", (long)write);
    updateMap("printf", (long)printf);
    updateMap("vprintf", (long)vprintf);
    updateMap("puts", (long)puts);
    updateMap("signal", (long)signal);
    updateMap("fork", (long)fork);
    updateMap("_exit", (long)_exit);
    updateMap("exit", (long)exit);
}
