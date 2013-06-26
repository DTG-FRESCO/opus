include     $(TOP)/Maketmpl/shlib.defs.mk

INSDIR      := $(TOP)

LIBNAME     := override

NULLSTRING :=
INTERPOSE_ON_FLAG := -DVFORK_INTERPOSE
UNAME := $(shell uname -m)

ifeq ($(UNAME), x86_64)
    VFORK_WRAPPER  := opus_vfork_wrapper_x86_64.S
else
    ifeq ($(UNAME), i686)
        VFORK_WRAPPER  := opus_vfork_wrapper_x86_32.S
    else
        INTERPOSE_ON_FLAG := $(NULLSTRING)
        VFORK_WRAPPER := $(NULLSTRING)
    endif
endif

CFLAGS2 := $(CFLAGS2) -fPIC -O2 -Wall -shared -DDEBUG
CFLAGS2 := $(CFLAGS2) $(INTERPOSE_ON_FLAG)
CFLAGS2 := $(CFLAGS2) -std=gnu++0x
CFLAGS2 := $(CFLAGS2) -I$(PROJ_INCLUDE) -I$(PROTO_INC_PATH)

LFLAGS  := $(LFLAGS) -L$(PROTO_LIB_PATH)
LFLAGS  := $(LFLAGS) -ldl -lrt -lprotobuf -lssl -lcrypto -lpthread


SRCS    :=  log.C \
            opus_lock.C \
            lock_guard.C \
            proc_utils.C \
            uds_client.C \
            uds_msg.pb.cc \
            functions.C \
            io_functions.C \
            process_functions.C \
            signal_handler.C \
            signal_utils.C \
            main.C \
            opus_vfork.C \
            $(VFORK_WRAPPER)

HDRS    :=  log.h \
            opus_lock.h \
            lock_guard.h \
            proc_utils.h \
            uds_comm_exception.h \
            uds_client.h \
            functions.h \
            signal_handler.h \
            signal_utils.h \
            main.h \
            opus_vfork.h

include        $(TOP)/Maketmpl/shlib-NEW.mk
