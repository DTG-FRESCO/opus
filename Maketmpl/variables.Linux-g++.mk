CPLUS           :=g++

#CXXVERSION      :=
#CXXDPND         :=/usr/X11R6/bin/makedepend $(CXXVERSION)
#POSTLIB_CLEANUP :=rm -f `echo *.ec ' '|sed 's/\**\.ec$ /.cc/g'`
#POSTEC_CLEANUP  =#rm -f $(<:.ec=.cc)
#TEMPLATE_CLEANUP:=rm -rf ti_files

#    Include Portability Flags 

PORT     := -DLINUX_GCC -DHAS_STD_NAMESPACE -D__EXTENSIONS__ -D_LINUX_SOURCE -D__GNU_LIBRARY__  #-I$(HOME)/gnu/include/g++-2 -I$(HOME)/gnu/include/g++-v3 
STDC     := -D__STDC__
LIBPORT  :=
LIBS     := -L$(LIB)
#ARCH    := ar vru
ARCH     := $(CPLUS) -o 
#ARCH1   := ranlib
#ARCH1    := @echo "Skipping: ranlib "
PIC      := -fPIC
PIC2     := -Lpic
SHLIB    := -shared
SHLIBEXT := .so
########### options shared libraries ############
#
########### options for profiling and analysis ############
#
########### options for debugging ############
#
########### options for advanced optimization ############
#
########### linker options ############
#
DEBUG         := -g
WARNING_FLAGS :=  #--remarks --strict
CXX           := $(CPLUS) $(DEBUG) $(CXXVERSION)
CXXFLAGS      := $(CXXFLAGS) $(PORT) 
CCFLAGS       := $(CXXFLAGS)
CPP           := $(CXX)
CC            := cc $(DEBUG)
#CFLAGS        := $(CXXFLAGS)
#CFLAGS        := -shared -fPIC -std=gnu++0x -ldl

#ARM_LIBS   :=-lARMed -larm
#ARM_DEFS   :=-DARMed
#SOCKET_LIB := -lnsl
#HLLAPI_DIR :=/opt/iocinst/Hllapi
#HLLAPI_LIB :=-L$(HLLAPI_DIR) -ltnhllapi -lnsl

# Oracle setup information
#PROC		:= proc
#PROC_LIBS_PATH	:= -L$(ORACLE_HOME)/lib
#PROC_SYS_INC	:= include=/usr/local/include/g++-3 include=/usr/include include=/usr/local/lib/gcc-lib/i686-pc-linux-gnu/2.95.2/include/
#PROCPPFLAGS := code=cpp cpp_suffix=cc hold_cursor=yes maxopencursor=50 mode=ansi parse=none close_on_commit=no threads=no release_cursor=no prefetch=100

#PROC_INCLUDE	:= -I$(ORACLE_HOME)/precomp/public
#PROC_LIBS	:= $(PROC_LIBS_PATH) -lclntsh -lsqlplus
#PROC_FLAGS  := -DSQLCA_STORAGE_CLASS=extern

#
# set up informix support variables
#

#THREADS		:= -thread
#THREAD_CFLAGS	:=-DIFX_THREAD -D_REENTRANT #-DIMPLEMENT_THREADS


# Informix setup information
#ESQL_LOCAL	:= -local
#INFORMIXINC   := $(INFORMIXDIR)/incl
#ESQL          := esql -e $(THREADS)
#ESQLC_INCLUDE := $(INFORMIXINC)/esql
#INFORMIXLIB   := $(INFORMIXDIR)/lib
#ESQL_LIBPATH  := -L$(INFORMIXLIB)/esql -L$(INFORMIXLIB)
#ESQL_FLAGS    := -I$(INFORMIXINC)/esql
#ESQL_GEN_LIBS := $(shell $(ESQL) -libs)
#ESQL_LIBS     := $(ESQL_LIBPATH) $(ESQL_GEN_LIBS)
#ALLINCLS      := -I$(ESQLC_INCLUDE)
#RUN_TIME_PATH := -R$(LD_LIBRARY_PATH)


# define a macro for linking with pthreads
#PTHREADS	:= -L/lib -lpthread

#PERL		:=perl
