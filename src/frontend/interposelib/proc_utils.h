#ifndef SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
#define SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_

#include <string>

class ProcUtils
{
    public:
        static uint64_t get_time();
        static bool test_and_set_flag(const bool value);

    private:
        static bool in_func_flag;
};

#endif  // SRC_FRONTEND_INTERPOSELIB_PROC_UTILS_H_
