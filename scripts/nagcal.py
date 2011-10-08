#!/usr/bin/env python
import os
import sys
import logging
import datetime
import settings
from nagcal import ShiftCalendar, UTC
from optparse import OptionParser

if __name__ == "__main__":
    EMAIL = 0
    PHONE = 1
    SYNC = 2
    CURRENT = 3
    LAST = 4

    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--sync", action="store_const", const=SYNC,
            dest="action", help="sync calendar and contacts from Google")
    parser.add_option("-c", "--current", action="store_const", const=CURRENT,
            dest="action", help="use with --email or --phone")
    parser.add_option("-l", "--last-shift", action="store_const", const=LAST,
            dest="action", help="echo no. of days until last known shift's end")
    parser.add_option("-e", "--email", action="store_const", const=EMAIL,
            dest="value", help="echo current shift's email")
    parser.add_option("-p", "--phone", action="store_const", const=PHONE,
            dest="value", help="echo current shift's phone number")
    parser.add_option("-o", "--stdout", action="store_true", default=False,
            dest="stdout", help="redirect logging to stdout")
    parser.add_option("-v", "--verbose", action="store_true",
            dest="verbose", help="make script a bit more talkative")
    (options, args) = parser.parse_args(sys.argv)

    if options.action is None:
        parser.print_help()
        sys.exit(os.EX_USAGE)

    if options.stdout:
        logging.basicConfig(format='%(levelname)s %(message)s')
    else:
        logging.basicConfig(
                filename=settings.LOG_FILE,
                format='%(asctime)s %(levelname)s %(message)s')

    shift_calendar = ShiftCalendar(
            settings.GOOGLE_CALENDAR_URL,
            settings.CALENDAR_FILE,
            settings.CONTACTS_FILE,
            settings.OAUTH_SETTINGS)

    if options.action != SYNC and not shift_calendar.credentials_ok():
        print >> sys.stderr, "Bad credentials, run --sync for initial setup!"
        sys.exit(os.EX_CONFIG)

    if options.action == SYNC:
        if not shift_calendar.credentials_ok():
            success = shift_calendar.setup_credentials()
            if not success:
                print >> sys.stderr, "OAuth setup failed, check settings!"
                sys.exit(os.EX_CONFIG)
        if settings.GOOGLE_CALENDAR_URL is None or \
                len(settings.GOOGLE_CALENDAR_URL) == 0:
            print "No calendar URL configured! " + \
                    "Please set settings.GOOGLE_CALENDAR_URL to " + \
                    "one of the URLs from the below list:\n"
            calendars = []
            calendar_feed = shift_calendar.get_calendar_feed()
            for calendar in calendar_feed.entry:
                print "%s\n%s\n%s\n" % (
                        calendar.title.text,
                        "-" * len(calendar.title.text),
                        calendar.content.src)
            print >> sys.stderr, "settings.GOOGLE_CALENDAR_URL is not set!"
            sys.exit(os.EX_CONFIG)
        count = shift_calendar.sync()
        if options.verbose:
            print "Wrote %s shifts to %s" % (count, settings.CALENDAR_FILE)
            print "Discovered contacts written to %s" % settings.CONTACTS_FILE

    if options.action == CURRENT:
        current_person = shift_calendar.get_current_person()
        if current_person is None:
            print >> sys.stderr, "Error: There is no current person!"
            sys.exit(os.EX_DATAERR)
        if options.value == EMAIL:
            print current_person.email
        elif options.value == PHONE:
            print current_person.phone
        else:
            parser.print_help()
            sys.exit(os.EX_USAGE)

    if options.action == LAST:
        last_known_shift = shift_calendar.get_last_shift()
        current_time = datetime.datetime.now(UTC())
        time_left = last_known_shift.end - current_time
        print time_left.days
        if options.verbose:
            last_person = Person(last_known_shift.title)
            last_person.update(shift_calendar.get_contacts_client())
            print "Person: %s" % last_person.query
            print "E-mail: %s" % last_person.email
            print "Phone#: %s" % last_person.phone
            print "Ends in %s" % time_left
