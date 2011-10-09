#!/usr/bin/env python
CONFIGURATION_FILE = "nagcal.cfg"

import os
import sys
import logging
import datetime
import ConfigParser
from nagcal import ShiftCalendar, UTC
from optparse import OptionParser

if __name__ == "__main__":
    EMAIL = 0
    PHONE = 1
    SYNC = 2
    CURRENT = 3
    LAST = 4

    config = ConfigParser.ConfigParser()
    config.read(CONFIGURATION_FILE)

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
                filename=config.get('nagcal', 'log_file'),
                format='%(asctime)s %(levelname)s %(message)s')


    oauth_settings = {
            'credentials_file': config.get('nagcal', 'credentials_file'),
            'user_agent': config.get('oauth', 'user_agent'),
            'display_name': config.get('oauth', 'display_name'),
            'client_id': config.get('oauth', 'client_id'),
            'client_secret': config.get('oauth', 'client_secret'),
            }

    shift_calendar = ShiftCalendar(
            config.get('nagcal', 'calendar_url'),
            config.get('nagcal', 'calendar_file'),
            config.get('nagcal', 'contacts_file'),
            oauth_settings,
            phone_type_preference = config.get('nagcal', 'phone_types'))

    if options.action != SYNC and not shift_calendar.credentials_ok():
        print >> sys.stderr, "Bad credentials, run --sync for initial setup!"
        sys.exit(os.EX_CONFIG)

    if options.action == SYNC:
        GOOGLE_CALENDAR_URL = config.get('nagcal', 'calendar_url')
        if not shift_calendar.credentials_ok():
            success = shift_calendar.setup_credentials()
            if not success:
                print >> sys.stderr, "OAuth setup failed, check settings!"
                sys.exit(os.EX_CONFIG)
        if GOOGLE_CALENDAR_URL is None or \
                len(GOOGLE_CALENDAR_URL) == 0:
            print "No calendar URL configured! " + \
                    "Please set calendar_url to " + \
                    "one of the URLs from the below list:\n"
            calendars = []
            calendar_feed = shift_calendar.get_calendar_feed()
            for calendar in calendar_feed.entry:
                print "%s\n%s\n%s\n" % (
                        calendar.title.text,
                        "-" * len(calendar.title.text),
                        calendar.content.src)
            print >> sys.stderr, "calendar_url is not set!"
            sys.exit(os.EX_CONFIG)
        count = shift_calendar.sync()
        if options.verbose:
            print "Wrote %s shifts to %s" % (count, config.get('nagcal', 'calendar_file'))
            print "Discovered contacts written to %s" % config.get('nagcal', 'contacts_file')

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
