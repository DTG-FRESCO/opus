#!/usr/bin/env python2.7

import os
from distutils.core import setup, Extension

inc_dirs = [os.environ['PROJ_INCLUDE']]

setup(name='OPUS',
      version=os.environ['VERSION'],
      description='Observational Provenance in User Space',
      author='Thomas Bytheway, Nikilesh Balakrishnan',
      author_email='tb403@cam.ac.uk, nb466@cam.ac.uk',
      url='',
      install_requires=["PyYAML", "neo4j-embedded==1.9.c2", "jinja2", "psutil",
                        "prettytable", "setuptools", "termcolor"],
      ext_modules=[Extension('opus.opuspb',
                             sources=['ext_src/opuspb.c',
                                      'proto_cpp_src/uds_msg.pb.cc'],
                             include_dirs=inc_dirs,
                             libraries=['protobuf'],)
                             ],
      packages=['opus',
                'opus.pvm',
                'opus.pvm.posix',
                'opus.query',
                'opus.scripts',
                'opus.opusctl',
                'opus.opusctl.cmds'],
      package_data={'opus.pvm.posix': ['pvm.yaml'],
                    'opus.scripts': ['epsrc.tmpl']},
      scripts=['scripts/env_diff.py', 'scripts/last_cmd.py', 'scripts/opusctl.py',
               'scripts/workflow/gen_epsrc.py', 'scripts/workflow/gen_tree.py',
               'scripts/workflow/gen_script.py'],
      )
