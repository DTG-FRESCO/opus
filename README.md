# OPUS
## Introduction
OPUS is a system for tracking the effects programs have on your system and improving the productivity of your work. It captures the effects programs have using LD_PRELOAD based interposition and stitches this data together into a graph of all the interactions on the system. Then it provides a set of tools that let you query this graph for information.

## Installation
1. Download the latest release.
1. Extract the archive to the chosen install location.
1. Open a terminal inside the extracted location.
1. ./update_wrapper
1. bin/opusctl conf -i
1. cat /tmp/install-opus >> ~/.bashrc
1. Open a fresh shell.

## OPUS Control script
Various common tasks you may want to perform with the different parts of the system.

### Configuration
* `opusctl conf <$flag>`
  * Allows you to configure the OPUS environment.

### Server
* `opusctl server start`
  * Starts the provenance collection server.
* `opusctl server stop`
  * Stops the provenance collection server.
* `opusctl server ps`
  * Lists all processes currently being interposed.
* `opusctl server status`
  * Returns the status of each component in the provenance server.
  * Returns the count of number of messages in the provenance server queue.
* `opusctl server detach $pid`
  * Closes connection with the process identifier $pid.
* `opusctl server getan`
  * Returns the current provenance analyser type.
* `opusctl server setan $new_an`
  * Sets the provenance analyser to $new_an.

### Frontend
* `opusctl process launch <$prog>`
  * Launches $prog under OPUS if supplied, else launches a new shell session under OPUS.
* `opusctl process exclude $prog`
  * While in a shell which is under OPUS interposition this launches `$prog` free from interposition.

### Utilities
* `opusctl util ps-line`
  * Returns a colored indicator that tells you the backend and frontend status combination.


### Query Tools
* `env_diff_client $prog`
  * Compares the environment and other process context between two executions of $prog.

* `last_cmd`
  * Returns the last N commands executed on a file or from a specific directory.

* `gen_epsrc $file`
  * Generates a report and archive package on $file for the EPSRC open data compliance.

* `gen_script $file`
  * Generates a script that canonicalises the workflow used to produce $file.

* `gen_tree $file`
  * Renders a tree representation of the workflow used to produce $file.

## Trouble Shooting

## Helpful Links
* http://www.cl.cam.ac.uk/research/dtg/fresco/
* https://www.cl.cam.ac.uk/research/dtg/fresco/opus/
* https://github.com/DTG-FRESCO/opus

