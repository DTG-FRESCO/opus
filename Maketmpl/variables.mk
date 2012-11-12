#==================================================
# set up java compilation variables
#  Set them up before including platform overrides
#==================================================


# this is the wrong place for the jars, but will work for now
#JARDIR=$(HOME)/jars

#JAVAC	:= javac
#JFLAGS	:= -nowarn -d $(PROJ_CLASS)
#DOC	:= javadoc -J-Xms150m -J-Xmx150m -splitindex -classpath $CLASSPATH
#JAR	:= true


#============================================================
#
# variables.mk
#
#============================================================

ifndef PROJ_HOME
PROJ_HOME       := $(shell ( cd $(TOP); pwd; ))
endif

PROJ_BIN        := $(PROJ_HOME)/bin
PROJ_SRC        := $(PROJ_HOME)/src
#ifndef PROJ_BUILDTOOLS
#PROJ_BUILDTOOLS := $(PROJ_HOME)/buildtools
#endif

ifndef COMP
COMP        := g++
endif

ifndef PLATFORM
PLATFORM	:= $(shell uname)
endif
# include platform and compiler specific flags 
include $(TOP)/Maketmpl/variables.$(PLATFORM)-$(COMP).mk

#==================================================
#
#         Directory Names!
#
#==================================================

SRC := $(PROJ_HOME)/src
#ETC :=$(PROJ_HOME)/etc
LIB :=$(PROJ_HOME)/lib#:$(CEM_HOME)/lib
BIN :=$(PROJ_HOME)/bin

#TEMPLATES   := $(SRC)/templates
#LIBSRC      := $(SRC)/libsrc
#ENVUTIL     := $(LIBSRC)/envutil
#DATASTRUCT  := $(LIBSRC)/datastruct
#OBJECTSPACE := $(LIBSRC)
#CODEBASE    := $(LIBSRC)/codebase
#INCLUDE     := $(SRC)/include
#LIBINCLUDE  := $(SRC)/libsrc/include
#DBINCLUDE   := $(SRC)/db/include
#ISPINCLUDE  := $(SRC)/isp/include
#SYSADM      := $(SRC)/sysadm
#SM          := $(SRC)/sm
#RELAY       := $(SRC)/relay
#LOGGER      := $(SRC)/logger



#==================================================
#
#    Variables common to all platforms!
#
#==================================================

# For now install just does a straight copy.  
CP:=cp $@ $(BIN)

# define an RM target just in case.
RM:=rm

# define PYTHON
#PYTHON	:= python

# This variable should be blank if make is to be in verbose mode 
#DPY = @  

#ALLINCLS  := -I$(DBINCLUDE) -I$(INCLUDE) -I$(ESQLC_INCLUDE)

#OSFLAGS   := $(CC_FLAGS) $(CC_DEFINES) $(CC_EH) $(CC_MT)
#OSFLAGS	  := $(strip $(OSFLAGS))

#CFLAGS    := -c $(OPTIM) $(PORT)
#CFLAGS	  := $(strip $(CFLAGS))

#CFLAGS2   := -c $(OPTIM) $(PORT) $(CONFIGFLAG) $(OSFLAGS) $(THREAD_CFLAGS)
#CFLAGS2	  := $(strip $(CFLAGS2))

# linker flags
#LFLAGS = $(strip $(CC_DEFINES) $(CC_EH) $(PLATFORM_LFLAGS) $(THREAD_LFLAGS))
