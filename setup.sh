#! /bin/bash

PYTHON=python2.7

WARN="\x1b[1;31m"
SUCC="\x1b[1;32m"
ENDCOL="\x1b[0m"


GIT_REPO="git@gitlab.dtg.cl.cam.ac.uk:fresco-projects/opus.git"

PY_MODULES=(google.protobuf.internal jinja2 yaml psutil prettytable neo4j pkg_resources)

C_LIBS=(libcrypto.so libprotobuf.so)

PKG_LIST="build-essential python python-yaml python-protobuf libprotobuf8 protobuf-compiler libprotobuf-dev libssl-dev python-jinja2 python-psutil python-prettytable python-jpype python-pip python-dev openjdk-7-jre libprotobuf-c1"

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

which "apt-get" >/dev/null

if [ $? -eq 0 ]
then
	sudo apt-get update
	sudo apt-get install $PKG_LIST
	sudo pip install neo4j-embedded
else

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
fi

make

$PYTHON bin/opusctl conf -i

cat /tmp/install-opus >> $HOME/.bashrc
