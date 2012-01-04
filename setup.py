#!/usr/bin/env python

import distribute_setup
distribute_setup.use_setuptools()

from setuptools import setup

setup(name='NaGCal',
        version='0.1.3',
        description='On Call Schedules in Google Calendar for Nagios',
        author='Martin Melin',
        author_email='nagcal@martinmelin.se',
        packages=['nagcal'],
        scripts=['scripts/mail-to-oncall', 'scripts/nagcal'],
        data_files=[('config', ['cfg/nagcal.cfg.example'])],
        install_requires=[
            'gdata',
            'iso8601',
            'httplib2',
            'oauth2client',
            'python-gflags',
            ],
        )
