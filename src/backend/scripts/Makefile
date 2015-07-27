MF=Makefile

SUBDIRS :=	workflow

include $(PROJ_HOME)/Maketmpl/dir.mk

all:
	ln -sf "$(PROJ_HOME)/src/backend/scripts/opusctl.py" "$(PROJ_HOME)/bin/opusctl"
	ln -sf "$(PROJ_HOME)/src/backend/scripts/last.py" "$(PROJ_HOME)/bin/last"
	ln -sf "$(PROJ_HOME)/src/backend/scripts/env_diff_client.py" "$(PROJ_HOME)/bin/env_diff_client"

clean:
	rm "$(PROJ_HOME)/bin/opusctl"
	rm "$(PROJ_HOME)/bin/last"
	rm "$(PROJ_HOME)/bin/env_diff_client"
