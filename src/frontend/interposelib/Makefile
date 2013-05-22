include 	$(TOP)/Maketmpl/shlib.defs.mk

INSDIR	:= $(TOP)

LIBNAME	:= override

CFLAGS2 := $(CFLAGS2) -Wall -DDEBUG -g -shared -fPIC
CFLAGS2 := $(CFLAGS2) -std=gnu++0x
CFLAGS2 := $(CFLAGS2) -I$(PROJ_INCLUDE) -I$(PROTO_INC_PATH)
#CFLAGS2 := $(CFLAGS2) -ldl -lrt -lprotobuf

LFLAGS  := $(LFLAGS) -L$(PROTO_LIB_PATH)
LFLAGS  := $(LFLAGS) -ldl -lrt -lprotobuf -lssl -lcrypto

SRCS	:= 	log.C \
			proc_utils.C \
			uds_client.C \
			uds_msg.pb.cc \
			functions.C \
			main.C

HDRS	:=	log.h \
			proc_utils.h \
			uds_comm_exception.h \
			uds_client.h \
			functions.h \
			main.h

include		$(TOP)/Maketmpl/shlib-NEW.mk
