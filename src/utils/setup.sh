#! /bin/bash

PYTHON=python2.7
GIT=git

WARN="\x1b[1;31m"
SUCC="\x1b[1;32m"
ENDCOL="\x1b[0m"



GIT_REPO="git@gitlab.dtg.cl.cam.ac.uk:fresco-projects/opus.git"

PY_MODULES=(leveldb google.protobuf.internal jinja2 yaml)

C_LIBS=(libcrypto.so libprotobuf.so)

PYTHON_MOD_CHECK="import sys\ntry:\n\timport MOD\nexcept ImportError:\n\tsys.exit(1)"

check_lib(){
	echo -n "Checking for $1..."
	ldconfig -p | grep "$1" -q

	if [ $? -ne 0 ]
	then
		echo -e "${WARN}MISSING\n"\
				"Error: Library $1 not found.\n"\
				"Please install $1 and then try again.${ENDCOL}"
		exit 1
	else
		echo -e "${SUCC}FOUND${ENDCOL}"
	fi
}

check_mod(){
	echo -n "Checking for $1..."
	echo -e $PYTHON_MOD_CHECK | sed "s/MOD/$1/g"| $PYTHON -

	if [ $? -ne 0 ]
	then
		echo -e "${WARN}MISSING\n"\
				"Error: Python module $1 not found.\n"\
				"Please install $1 and then try again.${ENDCOL}"
		exit 1
	else
		echo -e "${SUCC}FOUND${ENDCOL}"
	fi
}

if [ $# -eq 0 ]
then
	export PROJ_HOME=$HOME/.opus
else
	export PROJ_HOME=$(readlink -m $1)
fi

which $PYTHON >/dev/null

if [ $? -ne 0 ]
then
	echo -e "${WARN}Error: Python 2.7 not found.\n"\
			"Please install Python 2.7 and try again.${ENDCOL}"
	exit 1
fi

echo "Checking for required C libraries."
for lib in ${C_LIBS[@]}
do
	check_lib $lib
done
echo -e "All required C libraries installed.\n"


echo "Checking for required python modules."
for mod in ${PY_MODULES[@]}
do
	check_mod $mod
done
echo -e "All required python modules found.\n"

$GIT clone $GIT_REPO $PROJ_HOME

cd $PROJ_HOME
. ./opus-setup
make

echo -e "\n\nBuild completed.\n"\
		"What to do now:\n"\
		"1. Copy $PROJ_HOME/src/backend/config.yaml.example\n"\
		"   to $PROJ_HOME/src/backend/config.yaml\n"\
		"2. Edit the config file to your own preferences.\n"\
		"3. Start the backed by using $PROJ_HOME/bin/startup.sh\n"\
		"4. Enable capture for a terminal with the command:\n"\
		"   . $PROJ_HOME/bin/opus-on\n"\
		"5. Disable capture by using either of the following commands:\n"\
		"   . $PROJ_HOME/bin/opus-off\n"\
		"   export LD_PRELOAD="
