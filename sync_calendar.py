#!python
from lib import ShiftCalendar
import settings
import sys

if __name__ == "__main__":
    sc = ShiftCalendar(settings.GOOGLE_CALENDAR_URL, settings.CALENDAR_FILE, settings.OAUTH_SETTINGS)
    if not sc.credentials_ok():
        success = sc.setup_credentials()
        if not success:
            print >> sys.stderr, "Wasn't able to set up OAuth credentials correctly, bailing out."
            sys.exit(5)
    if settings.GOOGLE_CALENDAR_URL is None or len(settings.GOOGLE_CALENDAR_URL) == 0:
        print "No calendar URL configured! " + \
                "Please set settings.GOOGLE_CALENDAR_URL to one of the below URLs"
        calendars = []
        calendar_feed = sc.get_calendar_feed()
        for calendar in calendar_feed.entry:
            print "%s\n%s\n%s\n" % (
                    calendar.title.text,
                    "-" * len(calendar.title.text),
                    calendar.content.src)
        print >> sys.stderr, "Bailing out because settings.GOOGLE_CALENDAR_URL is not set."
        sys.exit(4)
    no_of_shifts = sc.sync()
    print "Wrote %s shifts to %s" % (no_of_shifts, settings.CALENDAR_FILE)
