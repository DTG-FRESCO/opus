#ifndef _PROC_UTILS_H
#define _PROC_UTILS_H

#include <string>

class ProcUtils
{
    public:
        static uint64_t get_time();
		static bool test_and_set_flag(const bool value);

	private:
		static bool in_func_flag;
};

#endif
