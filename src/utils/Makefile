
OPUS_LIB_LOCATION=$(PROJ_HOME)/lib/lib$(OPUS_LIB_NAME).so

.PHONY: opus-on opus-off

all: opus-on opus-off
	chmod +x ./startup.sh
	chmod +x ./opus-off
	chmod +x ./opus-on
	ln -s $(PROJ_HOME)/src/utils/startup.sh "$(PROJ_HOME)/bin/"
	ln -s $(PROJ_HOME)/src/utils/opus-off "$(PROJ_HOME)/bin/"
	ln -s $(PROJ_HOME)/src/utils/opus-on "$(PROJ_HOME)/bin/"

opus-on:
	echo '#!/bin/bash' > opus-on
	echo 'export OPUS_UDS_PATH=$(OPUS_UDS_PATH)' >> opus-on
	echo 'export LD_PRELOAD="$$LD_PRELOAD $(OPUS_LIB_LOCATION)"' >> opus-on

opus-off:
	echo '#!/bin/bash' > opus-off
	echo 'export LD_PRELOAD=$${LD_PRELOAD#" $(OPUS_LIB_LOCATION)"}' >> opus-off

clean:
	rm "$(PROJ_HOME)/bin/opus-on"
	rm "$(PROJ_HOME)/bin/opus-off"
	rm "$(PROJ_HOME)/bin/startup.sh"
