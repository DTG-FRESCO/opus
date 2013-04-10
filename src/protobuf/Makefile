MF= Makefile

CC=protoc
CFLAGS=--cpp_out=. --python_out=.


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
		cp -f *.py $(PROJ_HOME)/src/backend/opus

clean:
		rm -f *.pb.h *.pb.cc *.py
