include     $(TOP)/Maketmpl/shlib.defs.mk

INSDIR      := $(TOP)

LIBNAME     := $(OPUS_LIB_NAME)

NULLSTRING :=
INTERPOSE_ON_FLAG := $(NULLSTRING)
VFORK_WRAPPER := $(NULLSTRING)
ARCH := $(shell uname -m)

ifeq ($(ARCH), $(filter $(ARCH), x86_64 i686))
    VFORK_WRAPPER := $(ARCH)/vfork_wrapper.S
    INTERPOSE_ON_FLAG := -DVFORK_INTERPOSE
endif

CFLAGS2 := $(CFLAGS2) -O2 -Wall -shared -fPIC -g
CFLAGS2 := $(CFLAGS2) $(INTERPOSE_ON_FLAG)
CFLAGS2 := $(CFLAGS2) -DCAPTURE_SIGNALS
CFLAGS2 := $(CFLAGS2) -DDEBUG_LOGGING
CFLAGS2 := $(CFLAGS2) -DCOMPUTE_GIT_HASH
CFLAGS2 := $(CFLAGS2) -std=gnu++0x
CFLAGS2 := $(CFLAGS2) -I$(PROJ_INCLUDE)

LFLAGS  := $(LFLAGS) -Wl,-Bstatic -lprotobuf -lcrypto -Wl,-Bdynamic -lpthread -lrt -ldl 

SRCS    :=  log.C \
            opus_lock.C \
            lock_guard.C \
            proc_utils.C \
            comm_client.C \
            uds_msg.pb.cc \
            functions.C \
            io_functions.C \
            process_functions.C \
            signal_handler.C \
            signal_utils.C \
            main.C \
            opus_vfork.C \
            $(VFORK_WRAPPER) \
            memory_functions.C \
            aggr_msg.C \
            sys_util.C \
            file_hash.C

HDRS    :=  log.h \
            opus_lock.h \
            lock_guard.h \
            proc_utils.h \
            comm_exception.h \
            comm_client.h \
            functions.h \
            signal_handler.h \
            signal_utils.h \
            main.h \
            opus_vfork.h \
            track_errno.h \
            aggr_msg.h \
            sys_util.h \
            file_hash.h

include     $(TOP)/Maketmpl/shlib-NEW.mk
