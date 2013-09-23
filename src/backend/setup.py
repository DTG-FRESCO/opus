#!/usr/bin/env python2.7

import os
from distutils.core import setup, Extension

setup(name='OPUS',
      version='0.0.1',
      description='Observational Provenance in User Space',
      author='Thomas Bytheway, Nikilesh Balakrishnan',
      author_email='tb403@cam.ac.uk, nb466@cam.ac.uk',
      url='',
      ext_modules=[Extension('opuspb',
      sources=['ext_src/opuspb.c','proto_cpp_src/uds_msg.pb.cc', 'proto_cpp_src/prov_db.pb.cc'],
      include_dirs = [os.environ['PROTO_INC_PATH'], os.environ['PROJ_INCLUDE']],
      libraries=['protobuf'],
      library_dirs=[os.environ['PROTO_LIB_PATH']])],
     )
