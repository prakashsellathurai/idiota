#!/usr/bin/env python3

from setuptools import setup

setup (name = 'idiota',
       version = '1.0',
       packages = ['idiota'],
       entry_points = {
           'console_scripts' : [
               'idiota = idiota.cli:main'
           ]
       })
