all:
	$(PYTHON) gen_boiler.py func-def.yaml gen_functions.C
	cp gen_functions.C ${PROJ_HOME}/src/frontend/interposelib
	cp func_ptr_types.h ${PROJ_HOME}/src/frontend/interposelib

clean:
	rm gen_functions.C func_ptr_types.h
