MF= Makefile

CC=protoc
CFLAGS=--cpp_out=.


SRC= uds_msg.proto

.SUFFIXES:
.SUFFIXES: .proto .pb.cc

OBJ=    $(SRC:.proto=.pb.cc)

.proto.pb.cc:
			$(CC) $< $(CFLAGS)

all: $(OBJ)

$(OBJ): $(MF)

all:
		cp -f *.pb.h $(PROJ_INCLUDE)
		cp -f *.pb.cc $(PROJ_HOME)/src/frontend/interposelib

clean:
		rm -f *.pb.h *.pb.cc
