
.PHONY: opuspb

all: opuspb
	$(PYTHON) setup.py install --install-lib=$(PROJ_HOME)/lib
	rm -rf build

clean: opuspb
	rm -f $(PROJ_HOME)/lib/opuspb.so
	rm -f proto_cpp_src/*.pb.cc
