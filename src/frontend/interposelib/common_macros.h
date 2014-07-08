#ifndef SRC_FRONTEND_INTERPOSELIB_COMMON_MACROS_H_
#define SRC_FRONTEND_INTERPOSELIB_COMMON_MACROS_H_

#define CALL_FUNC(ret_type, ret_name, func_ptr, ...)    \
    errno = 0;                                          \
    ret_type ret_name = func_ptr(__VA_ARGS__);          \
    err_obj = errno

#define CALL_FUNC_VOID(func_ptr, ...)                   \
    errno = 0;                                          \
    func_ptr(__VA_ARGS__);                              \
    err_obj = errno

#endif  // SRC_FRONTEND_INTERPOSELIB_COMMON_MACROS_H_
