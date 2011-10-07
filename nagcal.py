#!/usr/bin/env python
"""A way to keep on-call schedules in Google Calendar and resolve email/phone number to current person on call from Google Contacts."""
import os
import sys
import gflags
import httplib2
import datetime
import settings
import gdata.data
import gdata.gauth
import gdata.acl.data
import oauth2client.tools
import gdata.contacts.data
import gdata.calendar.data
import gdata.contacts.client
import gdata.calendar.client
from iso8601 import parse_date # pylint: disable=E0611
from operator import attrgetter
from optparse import OptionParser
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow

class ShiftCalendar:
    """ShiftCalendar interfaces with Google Data APIs to sync one calendar and multiple contacts."""
    def __init__(self, calendar_url, calendar_file, contacts_file, oauth_settings):
        """Initialize a new ShiftCalendar

        Arguments:
        calendar_url -- URL to the Google Calendar to work with.
        calendar_file -- path to file where calendar contents should be cached
        contacts_file -- path to file where contacts discovered from calendar should be cached
        oauth_settings -- a dictionary with settings for the OAuth 2.0 authentication with Google:
            'credentials_file': path to file where OAuth credentials should be stored after authentication
            'user_agent': what User-Agent to present to Google
            'display_name': what name Google should use to identify this script
            'client_id': app ID from Google's API Console
            'client_secret': app secret from Google's API console
        """
        self.storage = Storage(oauth_settings['credentials_file'])
        self.credentials = self.storage.get()
        gflags.FLAGS.auth_local_webserver = False
        oauth_settings['scope'] = "https://www.google.com/calendar/feeds/ https://www.google.com/m8/feeds"
        self.calendar_url = calendar_url
        self.calendar_file = calendar_file
        self.contacts_file = contacts_file
        self.oauth_settings = oauth_settings
        self.have_synced = False
        self.shifts = None
        self.people = {}
        self.token = None

    def credentials_ok(self):
        if self.credentials is None or self.credentials.invalid == True:
            return False
        return True

    def setup_credentials(self):
        flow = OAuth2WebServerFlow(
                client_id = self.oauth_settings['client_id'],
                client_secret = self.oauth_settings['client_secret'],
                scope = self.oauth_settings['scope'],
                user_agent = self.oauth_settings['user_agent'],
                xoauth_displayname = self.oauth_settings['display_name'])
        self.credentials = oauth2client.tools.run(flow, self.storage)
        return not self.credentials.invalid

    def get_token(self):
        if self.credentials.access_token_expired:
            self.credentials._refresh(httplib2.Http().request)
            self.token = None # need a new token after refreshing
        if self.token is None:
            self.token = gdata.gauth.OAuth2Token(
                    self.oauth_settings['client_id'],
                    self.oauth_settings['client_secret'],
                    self.oauth_settings['scope'],
                    self.oauth_settings['user_agent'],
                    access_token = self.credentials.access_token,
                    refresh_token = self.credentials.refresh_token)
        return self.token

    def get_contacts_client(self):
        client = gdata.contacts.client.ContactsClient(
                source=self.oauth_settings['user_agent'])
        client.auth_token = self.get_token()
        return client

    def get_calendar_client(self):
        client = gdata.calendar.client.CalendarClient(
                source=self.oauth_settings['user_agent'])
        client.auth_token = self.get_token()
        return client

    def sync(self):
        if self.have_synced: # only sync once per instance
            return True

        use_cache = False
        calendar_file = open(self.calendar_file, 'r')
        cached_shifts = []
        for line in calendar_file:
            cached_shifts.append(Shift.loads(line))

        contacts_file = open(self.contacts_file, 'r')
        cached_people = []
        for line in contacts_file:
            cached_people.append(Person.loads(line))

        try:
            client = self.get_calendar_client()
            shifts = []
            event_feed = client.GetCalendarEventFeed(uri=self.calendar_url)
            for event in event_feed.entry:
                shifts.append(
                        Shift(
                            event.title.text,
                            parse_date(event.when[0].start),
                            parse_date(event.when[0].end)
                        ))
                # download contact info the first time we see this title,
                # otherwise person will be grabbed from self.people
                self.get_person(event.title.text)
        except:
            use_cache = True

        if use_cache: # TODO: should log this as an error
            self.shifts = cached_shifts
            self.people = cached_people
        else: # we have synced successfully, so cache to disk
            # sort shifts according to start date (feed order not guaranteed)
            self.shifts = sorted(shifts, key=attrgetter('start'))

            # persist synced calendar to disk cache
            calendar_file = open(self.calendar_file, 'w')
            for shift in self.shifts:
                calendar_file.write("%s\n" % (shift.dumps()))
            calendar_file.close()

            # persist synced contacts to disk cache
            contacts_file = open(self.contacts_file , 'w')
            for person in self.people.values():
                contacts_file.write("%s\n" % (person.dumps()))
            contacts_file.close()

        self.have_synced = True
        return len(self.shifts)

    def get_person(self, query):
        if query in self.people:
            person = self.people[query]
        else:
            person = Person(query)
        client = self.get_contacts_client()
        person.update(client)
        self.people[query] = person
        return person

    def get_current_shift(self):
        if not self.have_synced:
            self.sync()
        current_shift = None
        now = datetime.datetime.now(UTC())
        # a bit ugly, but gets the job done
        for shift in self.shifts:
            if now <= shift.start:
                continue
            if now >= shift.end:
                continue
            current_shift = shift
            break
        if current_shift is None:
            pass # TODO: log warning when no current shift was found
        return current_shift

    def get_current_person(self):
        if not self.have_synced:
            self.sync()
        current_shift = self.get_current_shift()
        if current_shift is None:
            # TODO: log error, this is pretty fatal
            return None
        return self.get_person(current_shift.title)

    def get_calendar_feed(self):
        client = self.get_calendar_client()
        return client.GetAllCalendarsFeed()

class Shift:
    def __init__(self, title, start, end):
        self.title = title
        self.start = start
        self.end = end

    def __repr__(self):
        return repr((self.title, self.start, self.end))

    def dumps(self):
        return "%s\t%s\t%s" % (self.start, self.end, self.title)

    @staticmethod
    def loads(string):
        string = string.split("\t")
        return Shift(string[2], parse_date(string[0]), parse_date(string[1]))

class Person:
    def __init__(self, query, email = None, phone = None):
        self.query = query
        if email == "None":
            self.email = None
        else:
            self.email = email
        if phone == "None":
            self.phone = None
        else:
            self.phone = phone
        self.have_synced = False

    def __repr__(self):
        return repr((self.query, self.email, self.phone))

    def update(self, client):
        if not self.have_synced:
            query = gdata.contacts.client.ContactsQuery()
            query.text_query = self.query
            feed = client.GetContacts(q = query)
            entry = None
            if len(feed.entry) == 1:
                entry = feed.entry[0]
            elif len(feed.entry) > 1:
                entry = feed.entry[0]
                # TODO: log warning that calendar titles are too broad
            if entry is None:
                print "Fatal error: current shift does not match any person in contacts! Query was: '%s'" % self.query
                sys.exit(os.EX_DATAERR)
                # TODO: handle this better
            person = {'email': None, 'phone': None}
            for email in entry.email:
                if email.primary and email.primary == 'true':
                    person['email'] = email.address
            phone_numbers = {}
            for phone in entry.phone_number:
                # rel example: http://schemas.google.com/g/2005#mobile
                rel = phone.rel.split("#").pop()
                phone_numbers[rel] = phone.text
            if 'mobile' in phone_numbers: # TODO: this should be configurable
                person['phone'] = phone_numbers['mobile']
            elif 'work' in phone_numbers:
                person['phone'] = phone_numbers['work']

            self.email = person['email']
            self.phone = person['phone']
            self.have_synced = True

    def dumps(self):
        return "%s\t%s\t%s" % (self.query, self.email, self.phone)

    @staticmethod
    def loads(string):
        string = string.split("\t")
        return Shift(string[0], string[1], string[2])

class UTC(datetime.tzinfo):
    def utcoffset(self, _):
        return datetime.timedelta(0)

    def tzname(self, _):
        return "UTC"

    def dst(self, _):
        return datetime.timedelta(0)

if __name__ == "__main__":
    EMAIL = 0
    PHONE = 1
    SYNC = 2
    CURRENT = 4

    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)
    parser.add_option("-s", "--sync", action="store_const", const=SYNC,
            dest="action", help="sync calendar and contacts from Google")
    parser.add_option("-c", "--current", action="store_const", const=CURRENT,
            dest="action", help="use with --email or --phone")
    parser.add_option("-e", "--email", action="store_const", const=EMAIL,
            dest="value", help="echo current shift's email")
    parser.add_option("-p", "--phone", action="store_const", const=PHONE,
            dest="value", help="echo current shift's phone number")
    parser.add_option("-v", "--verbose", action="store_true",
            dest="verbose", help="Make script a bit more talkative")
    (options, args) = parser.parse_args(sys.argv)

    if options.action is None:
        parser.print_help()
        sys.exit(os.EX_USAGE)

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
