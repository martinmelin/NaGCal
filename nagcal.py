#!python
from lib import Shift, ShiftCalendar, UTC
import settings
import datetime

sc = ShiftCalendar(settings.GOOGLE_CALENDAR_URL, settings.CALENDAR_FILE, settings.OAUTH_SETTINGS)
if not sc.credentials_ok():
    print >> sys.stderr, "Invalid credentials, run setup!"
    sys.exit(5)

current_shift = sc.get_current_shift()
if current_shift is None:
    print "Error, no active shift at %s" % now
    sys.exit(3)

print "Current shift is: %s" % current_shift
