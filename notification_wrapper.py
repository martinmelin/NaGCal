#!/usr/bin/python
# This script is supposed to be used as a wrapper for any command,
# replacing certain arguments on the command line with dynamic values
# determined at runtime.
# To the calling and target programs the existence of this wrapper
# should be transparent except of course that arguments are different.
import sys
import subprocess

replacements = { 'ONCALL_EMAIL_ADDRESS': 'martin@martinmelin.se', }

script_name = sys.argv.pop(0)
new_argv = []
for argument in sys.argv:
    if argument in replacements:
        new_argv.append(replacements[argument])
    else:
        new_argv.append(argument)

# shell=True because Nagios expects command_line to be run by a shell
process = subprocess.Popen(new_argv, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(stdout_data, stderr_data) = process.communicate() # this buffers output in memory
return_code = process.returncode
sys.stdout.write(stdout_data)
sys.stderr.write(stderr_data)
sys.exit(return_code)
