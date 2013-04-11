# -*- coding: utf-8 -*-
import unittest
import gen_boiler

class TestGenBoiler(unittest.TestCase):
    
    def test_gather_regex(self):
        funcs = ["int foo(int a, int b);",
                 "#Testing comment",
                 "\n",
                 "off64_t lseek64(read int fd,"
                 " read off64_t offset, read int whence);",
                 "int close(read int fd);",
                 "int bar(void);",
                 "int dar();"]
        ret = gen_boiler.gather_funcs(funcs)
        self.assertEqual(ret,
                        [{'args': [{'name': 'a', 'read': False, 'type': 'int'},
                                   {'name': 'b', 'read': False, 'type': 'int'}],
                          'name': 'foo',
                          'ret': 'int'},
                         {'args': [{'name': 'fd', 'read': True, 'type': 'int'},
                         {'name': 'offset', 'read': True, 'type': 'off64_t'},
                         {'name': 'whence', 'read': True, 'type': 'int'}],
                          'name': 'lseek64',
                          'ret': 'off64_t'},
                         {'args': [{'name': 'fd', 'read': True, 'type': 'int'}],
                          'name': 'close',
                          'ret': 'int'},
                         {'args': [],
                          'name': 'bar',
                          'ret': 'int'},
                         {'args': [],
                          'name': 'dar',
                          'ret': 'int'}])
        
    def test_broken_def(self):
        func = "int foo int a, int b)"
        
        with self.assertRaises(gen_boiler.InvalidLineException):
            gen_boiler.match_func_in_line(func)
        
    def test_broken_args(self):
        args = "int a, b, glarg__! fet"
        
        with self.assertRaises(gen_boiler.InvalidArgumentException):
            gen_boiler.match_args_from_list(args)
