#======================================================================
# if a filespec is specified, use it to define SRCS
#======================================================================
ifneq	($(strip $(FILESPEC)),)
SRCS		:= $(shell cat $(FILESPEC))
endif

.SUFFIXES:

#======================================================================
# Compute C related files
#======================================================================
C_SRCS		:= $(filter %.c,$(SRCS))
C_DEPS		:= $(C_SRCS:.c=.d)
C_OBJS		:= $(C_SRCS:.c=.o)

#======================================================================
# Compute C++ related files
#======================================================================
CXX_SRCS	:= $(filter %.C,$(SRCS))
CXX_DEPS	:= $(CXX_SRCS:.C=.d)
CXX_OBJS	:= $(CXX_SRCS:.C=.o)

#======================================================================
# Protobuf C++ related files
#======================================================================
PB_CXX_SRCS	:= $(filter %.pb.cc,$(SRCS))
PB_CXX_DEPS	:= $(PB_CXX_SRCS:.pb.cc=.pb.d)
PB_CXX_OBJS	:= $(PB_CXX_SRCS:.pb.cc=.pb.o)

#======================================================================
# Assembly files .S extension
#======================================================================
AS_SRCS := $(filter %.S,$(SRCS))
AS_DEPS := $(AS_SRCS:.S=.d)
AS_OBJS := $(AS_SRCS:.S=.o)

#=====================================================================
# Compute .l (lex ) related files
#==================================================================
#LEX_SRCS	:= $(filter %.l,$(SRCS))
#LEX_C		:= $(LEX_SRCS:.l=.c)
#LEX_DEPS	:= $(LEX_C:.c=.d)
#LEX_OBJS	:= $(LEX_C:.c=.o)

#======================================================================
# Compute Pro*C/C++ (embedded SQL) related files
#======================================================================
#PROC_SRCS   := $(filter %.pc,$(SRCS))
#PROC_C      := $(PROC_SRCS:.pc=.c)
#PROC_CC     := $(PROC_C:.c=.cc)
#PROC_DEPS   := $(PROC_CC:.cc=.d)
#PROC_OBJS   := $(PROC_CC:.cc=.o)

#======================================================================
# Compute ec (embedded SQL) related files
#======================================================================
#ESQL_SRCS	:= $(filter %.ec,$(SRCS))
#ESQL_C		:= $(ESQL_SRCS:.ec=.c)
#ESQL_CC		:= $(ESQL_C:.c=.cc)
#ESQL_DEPS	:= $(ESQL_CC:.cc=.d)
#ESQL_OBJS	:= $(ESQL_CC:.cc=.o)


#======================================================================
# Compute auto generated dependencies
#======================================================================
DEPS	:=	$(C_DEPS) \
		$(CXX_DEPS) \
		$(PB_CXX_DEPS) \
        $(AS_DEPS)
#		$(LEX_DEPS) \
#		$(PROC_DEPS) \
#		$(ESQL_DEPS) 


# strip extra white space
DEPS	:= $(strip $(DEPS))



#======================================================================
# Compute java classes
#   Note: java compilation, may use a filespec to define srcs
#======================================================================
#VPATH		:= $(PROJ_CLASS)/$(PACKAGE)
#JAVA_SRCS	:= $(filter %.java, $(SRCS))
#CLASSES		:= $(strip $(JAVA_SRCS:.java=.class))

# if any classes are defined, we must build them
#ifneq ($(CLASSES),)
#all	: $(CLASSES)

#======================================================================
# pattern rule to compile java
#======================================================================
#%.class	: %.java
#	$(JAVAC) $(JFLAGS) $<


# rule to build enum files for java
#%.java	: %.data
#	$(PROJ_BUILDTOOLS)/gen_enum.pl -j $<


#ifneq ($(strip $(JARFILE)),)

#JARFILE	:= $(CLIENTTOP)/$(JARFILE)

#$(JARFILE) :
#	touch $(JARFILE).dummy
#	$(JAR) -cv0f $(JARFILE) $(JARFILE).dummy
#	$(RM) $(JARFILE).dummy

#jar	: $(JARFILE)
#	cd $(CLIENTTOP); $(JAR) -cv0f $(JARFILE) $(CLASSES)
#endif				# $(JARFILE)


#endif				# $(CLASSES)



#======================================================================
# Generate C include dependencies
#======================================================================
#%.d:		%.c
#		@echo "Generating dependencies for $<..."
#		@echo "" >$@.tmp
#		@$(CXXDPND) $(INCPATHSW) $(PORT) -f$@.tmp $< 2>/dev/null
#		@cat $@.tmp | sed -e 's/$(<:.c=.o):/$@ $(<:.c=.o):/' > $@
#		@rm -f $@.tmp $@.tmp.bak

#======================================================================
# Generate C++ include dependencies
#======================================================================
#%.d:		%.C
#		@echo "Generating dependencies for $<..." 
#		@echo "" >$@.tmp
#		@$(CXXDPND) $(INCPATHSW) $(PORT) -f$@.tmp $< 2>/dev/null
#		@cat $@.tmp | sed -e 's/$(<:.C=.o):/$@ $(<:.C=.o):/' > $@
#		@rm -f $@.tmp $@.tmp.bak

#======================================================================
# Generate protobuf C++ include dependencies
#======================================================================
#%.d:		%.pb.cc
#		@echo "Generating dependencies for $<..." 
#		@echo "" >$@.tmp
#		@$(CXXDPND) $(INCPATHSW) $(PORT) -f$@.tmp $< 2>/dev/null
#		@cat $@.tmp | sed -e 's/$(<:.pb.cc=.o):/$@ $(<:.pb.cc=.o):/' > $@
#		@rm -f $@.tmp $@.tmp.bak

#======================================================================
# Generated Pro*C/C++ SQL include dependencies
#======================================================================
#%.d:		%.pc
#		@echo "Generating dependencies for $<..."
#		@echo "" >$@.tmp
#		@$(CXXDPND) $(INCPATHSW) $(PORT) -f$@.tmp $(<)  2>/dev/null
#		@cat $@.tmp | sed -e 's/$(<:.pc=.o):/$@ $(<:.pc=.o):/' > $@
#		@rm -f $@.tmp $@.tmp.bak

#======================================================================
# Generate Embedded SQL include dependencies
#======================================================================
#%.d:		%.ec
#		@echo "Generating dependencies for $<..."
#		@echo "" >$@.tmp
#		@$(CXXDPND) $(INCPATHSW) $(PORT) -f$@.tmp $(<)  2>/dev/null
#		@cat $@.tmp | sed -e 's/$(<:.ec=.o):/$@ $(<:.ec=.o):/' > $@
#		@rm -f $@.tmp $@.tmp.bak

# Generate LEX include dependencies
#======================================================================
#%.d:		%.l
#		@echo "Generating dependencies for $<..."
#		@echo "" >$@.tmp
#		@$(CXXDPND) $(INCPATHSW) $(PORT) -f$@.tmp $(<)  2>/dev/null
#		@cat $@.tmp | sed -e 's/$(<:.l=.o):/$@ $(<:.l=.o):/' > $@
#		@rm -f $@.tmp $@.tmp.bak

#======================================================================
# Compute full object list
#======================================================================
OBJS	:=	$(C_OBJS) \
		$(CXX_OBJS) \
		$(PB_CXX_OBJS) \
        $(AS_OBJS)
#		$(PROC_OBJS) \
#		$(ESQL_OBJS) \
#		$(LEX_OBJS)

#======================================================================
# Compute general file search path
#======================================================================
#FINDSRCHPATH=	SrchPath=; \
#		Level="."; \
#		for DotDot in $(subst /, ,$(TOP)); do \
#		Level=$${Level}"/"$${DotDot}; \
#		SrchPath=$${SrchPath}" "$${Level}; \
#		done; \
#		echo $${SrchPath}
#
#SRCHPATH	:= $(shell $(FINDSRCHPATH))
#SRCHPATH is should be set at the environment by differnt projects
#depending on what component they want. eg 
#$(TOP) $(CEM_HOME) etc. By default it is set to $(TOP)
#

ifndef SRCHPATH
SRCHPATH	:= $(TOP)
endif

#======================================================================
# Compute include file search path
#======================================================================
INCPATH		:= $(SRCHPATH:%=%/include) $(XINCPATH)
INCPATHSW	:= $(INCPATH:%=-I%) $(EXTINCSSW)

### The following section is from prog-NEW.mk
#======================================================================
# Compute library file search path
#======================================================================
LIBPATH		:= $(SRCHPATH:%=%/lib) $(XLIBPATH)
LIBPATHSW	:= $(LIBPATH:%=-L%)

### The following section is from prog-NEW.mk
#======================================================================
# Compute library flags
#======================================================================
ARLIBS		:= $(filter-out $(SHLIBS),$(LIBS))
ARLIBDEPS	:= $(ARLIBS:%=lib%.a)
SHLIBDEPS	:= $(SHLIBS:%=lib%$(SHLIBEXT))
LIBDEPS		:= $(ARLIBDEPS)
LIBSSW		:= $(LIBS:%=-l%)
ALLLIBSSW	:= $(LIBSSW) $(EXTLIBSSW)

### The following section is from prog-NEW.mk
#======================================================================
# Compute library file dependency search paths
#======================================================================
vpath %.a
vpath %.a $(LIBPATH)
vpath %$(SHLIBEXT)
vpath %$(SHLIBEXT) $(LIBPATH)

#======================================================================
# Define installation directories
#======================================================================
INSINCDIR	:= $(INSDIR)/include
INSLIBDIR	:= $(INSDIR)/lib
### The following line is from prog-NEW.mk
INSBINDIR	:= $(INSDIR)/bin

#======================================================================
# Compute destination file lists
#======================================================================
DSTHDRS		= $(HDRS:%=$(INSINCDIR)/%)

# use late macro resolution !!!
DSTLIB		= $(LIBRARY:%=$(INSLIBDIR)/%)

### The following line is from prog-NEW.mk
DSTBIN		= $(PROGRAM:%=$(INSBINDIR)/%)

#======================================================================
# C compliation rule
#======================================================================
%.o:		%.c
		$(DPY)$(CXX) $(INCPATHSW) $(CFLAGS2) -c $<

#======================================================================
# C++ compliation rule
#======================================================================
%.o:		%.C
		$(DPY)$(CXX) $(INCPATHSW) $(CFLAGS2) -c $< -o $(<:.C=.o)

#======================================================================
# protobuf C++ compliation rule
#======================================================================
%.pb.o:		%.pb.cc
		$(DPY)$(CXX) $(INCPATHSW) $(CFLAGS2) -c $<

#======================================================================
# Assembly files compliation rule
#======================================================================
%.o:		%.S
		$(DPY)$(CXX) $(INCPATHSW) $(CFLAGS2) -c $< -o $(<:.S=.o)

#======================================================================
# Pro*C/C++ SQL (pc) compilation rules
#======================================================================
#%.o:		%.pc
#		@echo $(PROC)  `echo $(INCPATHSW) | sed -e 's/-I/include=/g'` $(PROC_SYS_INC) $(PROCPPFLAGS) $<
#		@$(PROC) `echo $(INCPATHSW) | sed -e 's/-I/include=/g'` $(PROC_SYS_INC) $(PROCPPFLAGS) $<
#		$(CXX) $(STDC) $(INCPATHSW) $(CFLAGS2) $(PROC_INCLUDE) $(PROC_FLAGS) -c $(<:.pc=.cc)
#		$(POSTPC_CLEANUP)

#======================================================================
# Embedded SQL (ec) compliation rules
#======================================================================
#%.o:		%.ec
#		@echo $(ESQL) $(ESQL_LOCAL) $(INCPATHSW) $(CFLAGS2) $<
#		@$(ESQL) $(ESQL_LOCAL) $(INCPATHSW) $(CFLAGS2) $<
#		-egrep -v '#define const' $(<:.ec=.c) > $(<:.ec=.cc)
#		rm -f $(<:.ec=.c)
#		$(CXX) $(STDC) $(INCPATHSW) $(CFLAGS2) $(ESQL_FLAGS) -c $(<:.ec=.cc)
#		$(POSTEC_CLEANUP)

#======================================================================
#  LEX Compilation rules
#======================================================================
%.o:		%.l
		@echo $(LEX)  $<
		@$(LEX)  -t $< >$(<:.l=.c)
		$(CXX) $(STDC) $(INCPATHSW) $(CFLAGS2) -c $(<:.l=.c)
		rm -f $(<:.l=.c)

#======================================================================
# Python Forced compilation rules
#======================================================================

#%.pyc	: %.py
#	echo import $* | $(PYTHON)



#======================================================================
# Default target
#======================================================================
install:	all

hdrz:

#======================================================================
# Remove build artifacts (not config if any)
#======================================================================
.PHONY: all installonly install realclean clean selfclean hdrz unlink ec_clean pc_clean
#.PHONE: class_clean

clean : selfclean

realclean : selfclean rm_deps ec_clean unlink

#class_clean :
#ifneq ($(strip $(CLASSES)),)
#	$(RM) -f $(patsubst %.java, %*.class, $(JAVA_SRCS))
#	$(RM) -f $(VPATH)/*.class
#endif


rm_deps :
ifneq ($(DEPS),)
		rm -f $(DEPS)
endif

unlink:

#ec_clean:
#ifneq ($(strip $(ESQL_OBJS)),)
#	$(RM) -f $(ESQL_OBJS) $(ESQL_CC) $(ESQL_C) 
#endif

#pc_clean:
#ifneq ($(strip $(PROC_OBJS)),)
#	$(RM) -f $(PROC_OBJS) $(PROC_CC) $(PROC_C) 
#endif

#======================================================================
# Include generated dependency files
#======================================================================
ifneq ($(DEPS),)
ifeq ($(filter realclean clean selfclean hdrz unlink pc_clean ec_clean, $(MAKECMDGOALS)),)
-include $(DEPS)
endif
endif
