all:
	python gen_boiler.py func-def gen_functions.C
	cp gen_functions.C ${PROJ_HOME}/src/frontend/interposelib

clean:
	rm gen_functions.C
