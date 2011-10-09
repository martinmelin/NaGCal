#!/usr/bin/env python

from distutils.core import setup

setup(name='NaGCal',
        version='0.1.0',
        description='On Call Schedules in Google Calendar for Nagios',
        author='Martin Melin',
        author_email='nagcal@martinmelin.se',
        packages=['nagcal'],
        scripts=['scripts/mail-to-oncall.sh', 'scripts/nagcal-bin.py'],
        data_files=[('config', ['cfg/nagcal.cfg'])],
        )
