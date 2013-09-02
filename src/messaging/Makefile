all: messages.yaml gen_msg.py c.tmpl py.tmpl
	./gen_msg.py messages.yaml
	cp messaging.h $(PROJ_INCLUDE)
	cp messaging.py $(PROJ_HOME)/src/backend/opus

clean: 
	rm $(PROJ_INCLUDE)/messaging.h
	rm $(PROJ_HOME)/src/backend/opus/messaging.py
	rm messaging.h
	rm messaging.py
