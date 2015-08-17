MF=Makefile

SUBDIRS :=	workflow

include $(PROJ_HOME)/Maketmpl/dir.mk

all:
	ln -sf "$(PROJ_HOME)/src/backend/scripts/opusctl.py" "$(PROJ_HOME)/bin/opusctl"
	ln -sf "$(PROJ_HOME)/src/backend/scripts/last_cmd.py" "$(PROJ_HOME)/bin/last_cmd"
	ln -sf "$(PROJ_HOME)/src/backend/scripts/env_diff.py" "$(PROJ_HOME)/bin/env_diff"

clean:
	rm "$(PROJ_HOME)/bin/opusctl"
	rm "$(PROJ_HOME)/bin/last_cmd"
	rm "$(PROJ_HOME)/bin/env_diff"
