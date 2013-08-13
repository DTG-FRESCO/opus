#! /bin/bash

GIT=git

cd $(readlink -m $(dirname $(readlink -m $0))/../..)
. ./opus-setup

rebuild(){
	cd "$PROJ_HOME" && make clean all
}

config_warning(){
	echo -e "##Example config updated!\n"\
			"##Please check that your config file is still valid!."
}

run(){
	echo "##Launching OPUS backend."
	cd "$PROJ_HOME/src/backend" && $PYTHON run_server.py
}

echo "##Polling repository for updates."
git_status="$($GIT pull --stat)"

version="$($GIT rev-parse --verify --short HEAD)"
echo "##Currently running version $version."

case "$git_status" in
	"Already up-to-date." )
		run;;
	"src/backend/config.yaml.example" ) 
		rebuild
		config_warning;;
	* )
		rebuild
		run;;
esac
