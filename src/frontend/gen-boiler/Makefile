all:
	python gen_boiler.py func-def functions
	cp functions.C ${PROJ_HOME}/src/frontend/interposelib
	cp functions.h ${PROJ_HOME}/src/frontend/interposelib

clean:
	rm functions.C
	rm functions.h
