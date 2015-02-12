# OPUS
## Introduction
OPUS is a system for tracking the effects programs have on your system and improving the productivity of your work. It captures the effects programs have using LD_PRELOAD based interposition and stitches this data together into a graph of all the interactions on the system. Then it provides a set of tools that let you query this graph for information.
## Installation
1. `git clone git@gitlab.dtg.cl.cam.ac.uk:fresco-projects/opus.git`
1. `./setup.sh`

## Common Tasks
Various common tasks you may want to perform with the different parts of the system.
### opusctl.py
* `opusctl enable`
  * Activates the provenance collection server.
* `opusctl launch $prog`
  * Launches a program under OPUS interposition.
  * If `$prog` is omitted then it launches a new copy of the current shell.
* `opusctl exclude $prog`
  * While in a shell which is under OPUS interposition this launches `$prog` free from interposition.

### op.py
* `op.py status`
  * Checks the status of a currently running provenance server.
* `op.py shutdown`
  * Sets the provenance server to shut down.
* `op.py ps`
  * Lists all the processes currently being interposed.
* `op.py kill $pid`
  * Deactivates interposition for the stated pid.

### Querying
* `env_diff_client`
* `last`

## Trouble Shooting

## Helpful Links
* http://www.cl.cam.ac.uk/research/dtg/fresco/