import sys
import json
import time
import gflags
import iso8601
import httplib2
import datetime
import atom.data
import gdata.data
import gdata.gauth
import gdata.acl.data
import oauth2client.tools
import gdata.contacts.data
import gdata.calendar.data
import gdata.contacts.client
import gdata.calendar.client
from operator import attrgetter
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow

class ShiftCalendar:
    def __init__(self, calendar_url, calendar_file, oauth_settings):
        self.storage = Storage(oauth_settings['credentials_file'])
        self.credentials = self.storage.get()
        gflags.FLAGS.auth_local_webserver = False
        self.calendar_url = calendar_url
        self.calendar_file = calendar_file
        self.oauth_settings = oauth_settings
        self.have_synced = False
        self.shifts = None
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
            self.token = None # need a new token if we had to refresh credentials
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

        try:
            client = self.get_calendar_client()
            shifts = []
            event_feed = client.GetCalendarEventFeed(uri=self.calendar_url)
            for event in event_feed.entry:
                shifts.append(
                        Shift(
                            event.title.text,
                            iso8601.parse_date(event.when[0].start),
                            iso8601.parse_date(event.when[0].end)
                        ))
        except:
            use_cache = True

        if use_cache:
            self.shifts = cached_shifts
        else:
            # sort shifts according to start date/time (not guaranteed to be in order in feed)
            self.shifts = sorted(shifts, key=attrgetter('start'))
            # persist synced calendar to disk cache
            calendar_file = open(self.calendar_file, 'w')
            for shift in self.shifts:
                calendar_file.write("%s\n" % (shift.dumps()))
            calendar_file.close()

        self.have_synced = True
        return len(self.shifts)

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
        current_shift = self.get_current_shift()
        client = self.get_contacts_client()
        query = gdata.contacts.client.ContactsQuery()
        query.text_query = current_shift.title
        feed = client.GetContacts(q = query)
        current_entry = None
        if len(feed.entry) == 1:
            current_entry = feed.entry[0]
        elif len(feed.entry) > 1:
            current_entry = feed.entry[0]
            # TODO: log warning that calendar titles are too broad
        if current_entry is None:
            print "Fatal error: current shift does not match any person in contacts! Query was: '%s'" % current_shift.title
            sys.exit(10)
            # TODO: handle this better
        person = {'email': None, 'phone': None}
        for email in current_entry.email:
            if email.primary and email.primary == 'true':
                person['email'] = email.address
        phone_numbers = {}
        for phone in current_entry.phone_number:
            rel = phone.rel.split("#").pop() # for example: http://schemas.google.com/g/2005#mobile
            phone_numbers[rel] = phone.text
        if 'mobile' in phone_numbers: # TODO: this should probably be configurable
            person['phone'] = phone_numbers['mobile']
        elif 'work' in phone_numbers:
            person['phone'] = phone_numbers['work']
        return person

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
        s = string.split("\t")
        return Shift(s[2], iso8601.parse_date(s[0]), iso8601.parse_date(s[1]))

class UTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return datetime.timedelta(0)
