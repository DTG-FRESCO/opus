## Overall structure
List of function entries, each in the form of a dictionary.

## Function Entry

* _name_: Name of the function
* _ret_: Return type of the function
* _flags_: List of entries relating to various extra options several of which are listed below.
  * _fdprotect_: Guards against this function operating on the file descriptor used by OPUS.
  * _buffer_: This function is suitable to be buffered for aggregate transmission
  * _nogen_: Skip the generation of an interposition function for this entry.
  * _nofnptr_: Skip the generation of a function pointer typedef for this entry.
  * _vararg_: This function takes a set of variable length arguments.
* _fdprotect_: Section describing the file descriptor protection.
  * _arg_: The argument to the function that contains the file descriptor it operates on.
  * _errno_: The errno to report indicating what sort of error we are pretending has occurred.
* _real\_func_: If a function takes varargs it is presumed that there is an underlying v- variant that takes a var args structure as an argument that we can call. e.g. printf and vprintf
* _args_: Either a string containing the arguments (only permitted for nogen functions) or a structure describing the arguments and their properties.
  * _name_: Argument name
  * _type_: Argument type
  * _flags_: Flag values for individual arguments.
    * _read_: This arguments value should be recorded and transmitted to the provenance server.
    * _can_: This argument is a path and should be canonicalised.
    * _abs_: This argument is a path possibly to a symbolic link and should be converted to an absolute path.
    * _dirfd_: Allows for conversion of dirFD type arguments into path names.
