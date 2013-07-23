#! /bin/bash

PYTHON=python2.7

check_lib(){
	echo -n "Checking for $1..."
	ldconfig -p | grep "$1" -q

	if [ $? -ne 0 ]
	then
		echo -e "\x1b[1;31mMISSING\x1b[0m"
		echo -e "\x1b[0;31mError: Library $1 not found.\x1b[0m"
		echo -e "\x1b[0;31mPlease install $1 and then try again.\x1b[0m"
		exit 1
	else
		echo -e "\x1b[1;32mFOUND\x1b[0m"
	fi
}

check_mod(){
	echo -n "Checking for $1..."
	echo -e "import sys\ntry:\n\timport $1\nexcept ImportError:\n\tsys.exit(1)"\
			| $PYTHON -

	if [ $? -ne 0 ]
	then
		echo -e "\x1b[1;31mMISSING\x1b[0m"
		echo -e "\x1b[0;31mError: Python module $1 not found.\x1b[0m"
		echo -e "\x1b[0;31mPlease install $1 and then try again.\x1b[0m"
		exit 1
	else
		echo -e "\x1b[1;32mFOUND\x1b[0m"
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
	echo -e "\x1b[0;31mError: Python 2.7 not found.\x1b[0m"
	echo -e "\x1b[0;31mPlease install Python 2.7 and try again.\x1b[0m"
	exit 1
fi

echo "Checking for required C libraries."
for lib in "libcrypto.so" "libprotobuf.so"
do
	check_lib $lib
done
echo -e "All required C libraries installed.\n"


echo "Checking for required python modules."
for mod in "leveldb" "google.protobuf.internal" "jinja2" "yaml"
do
	check_mod $mod
done
echo -e "All required python modules found.\n"

git clone "git@gitlab.dtg.cl.cam.ac.uk:fresco-projects/opus.git" $PROJ_HOME

cd $PROJ_HOME
. ./opus-setup
make

echo -e "\n\nBuild completed."
echo "What to do now:"
echo "1. Copy $PROJ_HOME/src/backed/config.yaml.example"
echo "   to $PROJ_HOME/src/backed/config.yaml"
echo "2. Edit the config file to your own preferences."
echo "3. Start the backed by using $PROJ_HOME/bin/startup.sh"
echo "4. Enable capture for a terminal with the command:"
echo "   . $PROJ_HOME/bin/opus-on"
echo "5. Disable capture by using either of the following commands:"
echo "   . $PROJ_HOME/bin/opus-off"
echo "   export LD_PRELOAD="