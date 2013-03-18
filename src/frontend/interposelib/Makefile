include 	$(TOP)/Maketmpl/shlib.defs.mk

INSDIR	:= $(TOP)

LIBNAME	:= override

CFLAGS2 := $(CFLAGS2) -DDEBUG -g -shared -fPIC
CFLAGS2 := $(CFLAGS2) -std=gnu++0x
CFLAGS2 := $(CFLAGS2) -I$(PROJ_INCLUDE) -I$(PROTO_INC_PATH)
#CFLAGS2 := $(CFLAGS2) -ldl -lrt -lprotobuf

LFLAGS  := $(LFLAGS) -L$(PROTO_LIB_PATH)
LFLAGS  := $(LFLAGS) -ldl -lrt -lprotobuf

SRCS	:= 	log.C \
			proc_utils.C \
			uds_client.C \
			uds_msg.pb.cc

HDRS	:=	log.h \
			proc_utils.h \
			uds_comm_exception.h \
			uds_client.h

include		$(TOP)/Maketmpl/shlib-NEW.mk
