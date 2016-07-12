MF=Makefile

SUBDIRS :=	scripts

include $(PROJ_HOME)/Maketmpl/dir.mk

.PHONY: opuspb

all: opuspb
	$(PYTHON) setup.py install --install-lib=$(PROJ_HOME)/lib --install-scripts=$(PROJ_HOME)/bin
	rm -rf build

clean: opuspb
	rm -f $(PROJ_HOME)/lib/opuspb.so
	rm -f proto_cpp_src/*.pb.cc

lint:
	@echo "=============================\nPylint\n============================="
	@-pylint --rcfile=$(PROJ_HOME)/.pylintrc opus
	@echo "==============================\nPEP8\n=============================="
	@-pep8 --config=$(PROJ_HOME)/.pep8rc opus
