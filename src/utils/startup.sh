#! /bin/bash

CURRENT=$PWD

cd $(readlink -m $(dirname $(readlink -m $0))/../..)
. ./opus-setup

rebuild(){
	cd "$PROJ_HOME";
	make clean;
	make;
}

config_warning(){
	echo "##Example config updated!";
	echo "##Please check that your config file is still valid!.";
}

run(){
	echo "##Launching OPUS backend.";
	cd "$PROJ_HOME/src/backend";
	$PYTHON run_server.py;
}

echo "##Polling repository for updates."
git_status="$(git pull)"

version="$(git rev-parse --verify --short HEAD)"
echo "##Currently running version $version."

case "$git_status" in
	*"Already up-to-date."* ) run;;
	*"src/backend/config.yaml.example"* ) rebuild
										  config_warning;;
	* ) rebuild
		run;;
esac

cd $CURRENT
