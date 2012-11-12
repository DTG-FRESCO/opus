#======================================================================
# Title: Makefile Template for a Shared Library
#
# Description:
#
# This makefile template is used to make and install a directory
# containing only headers.
#
# MACROS:
#
#   INSDIR	Required	Specified the relative path to the
#				point where the library and any
#				associated headers are installed.
#				This should be the directory that
#				contains the include and lib
#				directories
#
#   LIBNAME	Required	Specified the simple name of the
#				library (without 'lib' prefix or
#				any suffix).
#
#   HDRS	Optional	List of the headers within this
#				directory which should be installed
#
#   SRCS	Required	List of source files from which the
#				library is constructed.  Can include
#				C = ".c", C++ = ".C", and ESQL = ".ec"
#
#   XINCPATH	Optional	Relative path to addition internal
#				include paths. Internal files are part of
#				our source tree.  These are NOT
#				switched (ie no -I is required)
#
#   EXTINCSSW	Optional	Addition switched required for
#				external includes (usually 3rd
#				party software).  These are passed
#				on verbatim.
#
# TARGETS Supported:
#
#   all		Update dependencies and construct the shared library
#		locally (in this directory).
#
#   install	Installs shared library and the headers into the
#		install point
#
#   clean	Removes by products of the build (except config info
#		like dependancies)
#
#   realclean	Same as clean but also removes config info
#
#======================================================================

#CFLAGS2	+= $(PIC)

include $(TOP)/Maketmpl/std_rules.mk
.PRECIOUS: %.d

LIBRARY		:= lib$(LIBNAME)$(SHLIBEXT)

#======================================================================
# Default target
#======================================================================
all:		$(LIBRARY) $(XTARGETS) installonly 

installonly:	$(DSTHDRS) $(DSTLIB)

$(LIBRARY): 	$(OBJS)
		$(PURIFY) $(CPLUS) $(DEBUG) -o $@ $(SHLIB) $(LFLAGS) $(OBJS)
		$(POSTLIB_CLEANUP)

hdrz:		$(DSTHDRS)

selfclean:         
		rm -f $(OBJS) $(LIBRARY) $(DSTLIB)

clean:		selfclean

realclean:	clean
		$(RM) -f $(DEPS) $(DSTHDRS) 
		$(TEMPLATE_CLEANUP)

$(INSINCDIR)/%:	%
		cp -f $< $@
		chmod 444 $@

$(INSLIBDIR)/%:	%
		ln -f $< $@

unlink:
	$(RM) -f $(LIBRARY) $(DSTLIB)

.PHONY: all installonly install realclean clean selfclean hdrz unlink ec_clean
