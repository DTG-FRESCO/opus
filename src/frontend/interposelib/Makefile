include     $(TOP)/Maketmpl/shlib.defs.mk

INSDIR      := $(TOP)

LIBNAME     := override

CFLAGS2 := $(CFLAGS2) -O2 -Wall -DDEBUG -g -shared -fPIC
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
            comm_thread.C \
            main.C

HDRS    :=  log.h \
            opus_lock.h \
            lock_guard.h \
            proc_utils.h \
            uds_comm_exception.h \
            uds_client.h \
            functions.h \
            signal_handler.h \
            signal_utils.h \
            comm_thread.h \
            main.h

include        $(TOP)/Maketmpl/shlib-NEW.mk
