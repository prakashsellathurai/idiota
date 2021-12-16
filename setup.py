#!/usr/bin/env python3

from setuptools import setup

with open('README.md', encoding="utf8") as f:
    long_description = f.read()

setup(name='idiota',
      version='1.1.0',
      packages=['idiota'],
      entry_points={
           'console_scripts': [
               'idiota = idiota.cli:main'
           ]
      },


      author='Prakash Sellathurai',
      author_email='prakashsellathurai@gmail.com',
      description='idiota is a minimal version control system built on python',
      long_description=long_description,
      long_description_content_type='text/markdown',  # This is important!

      url='https://github.com/prakashsellathurai/idiota',

      )
