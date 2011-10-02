#!python
from settings import * # only constants
from lib import Shift, UTC
import datetime

calendar_file = open(NAGCAL_CALENDAR_FILE, 'r')
shifts = []
for line in calendar_file:
    shifts.append(Shift.loads(line))

now = datetime.datetime.now(UTC())

# a bit ugly, but gets the job done
for shift in shifts:
    if now <= shift.start:
        continue
    if now >= shift.end:
        continue
    print "%s is %s away from ending!" % (shift.title, shift.end - now)
    current_shift = shift
    break

if current_shift is None:
    print "Error, no active shift at %s" % now
    sys.exit(3)
