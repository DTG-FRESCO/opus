
all:
	chmod +x ./startup.sh
	chmod +x ./opus-off
	chmod +x ./opus-on
	ln -s $(PROJ_HOME)/src/utils/startup.sh "$(PROJ_HOME)/bin/"
	ln -s $(PROJ_HOME)/src/utils/opus-off "$(PROJ_HOME)/bin/"
	ln -s $(PROJ_HOME)/src/utils/opus-on "$(PROJ_HOME)/bin/"

clean:
	rm "$(PROJ_HOME)/bin/opus-on"
	rm "$(PROJ_HOME)/bin/opus-off"
	rm "$(PROJ_HOME)/bin/startup.sh"
