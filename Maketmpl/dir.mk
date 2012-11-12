#======================================================================
# Title: Makefile Template for a Directory
#
# Description:
#
# This makefile template is used to make and install a directory
# containing other component directories
#
# TARGETS Supported:
#
#   all		Builds and installs all sub-directories
#
#   install	Null target.  Provided for consistency
#
#   hdrz	Builds and installs only headers
#
#   clean	Removes by products of the build (except config info
#		like dependancies).  Cleans out install directories
#
#
#======================================================================

#======================================================================
# Default target
#======================================================================
all:		$(SUBDIRS)

#======================================================================
# Rule for building a sub-directory
#======================================================================
$(SUBDIRS):
		$(MAKE) -C $@ all

#======================================================================
# Rules for building headers
#======================================================================
hdrz:		$(SUBDIRS:%=%.hdrz)

%.hdrz:
		$(MAKE) -C $* $(subst $*.,,$@)

#======================================================================
# Rules for performing clean
#======================================================================
clean:		$(SUBDIRS:%=%.clean)

%.clean:
		$(MAKE) -C $* $(subst $*.,,$@)

#======================================================================
# Phony targets
#======================================================================
.PHONY:         all hdrz install installonly clean selfclean tags $(SUBDIRS) 

install:	all
