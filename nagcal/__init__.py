"""A way to keep on-call schedules in Google Calendar and resolve email/phone number to current person on call from Google Contacts."""
import os
import sys
import gflags
import logging
import httplib2
import datetime
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
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow

class ShiftCalendar:
    """ShiftCalendar interfaces with Google Data APIs to sync one calendar and multiple contacts."""
    default_scope = "https://www.google.com/calendar/feeds/ https://www.google.com/m8/feeds"

    def __init__(self, calendar_url, calendar_file, contacts_file, oauth_settings):
        """Initialize a new ShiftCalendar

        Arguments:
        calendar_url -- URL to the Google Calendar to work with
        calendar_file -- path to file where calendar contents should be cached
        contacts_file -- path to file where contacts discovered from calendar should be cached
        oauth_settings -- a dictionary with settings for the OAuth 2.0 authentication with Google:
            'credentials_file': path to file where OAuth credentials should be stored after authentication
            'user_agent': what User-Agent to present to Google
            'display_name': what name Google should use to identify this script
            'client_id': app ID from Google's API Console
            'client_secret': app secret from Google's API console
            'scope': (optional) scope for which to request access from Google
        """
        self.calendar_url = calendar_url
        self.cache_files = { 'calendar': calendar_file, 'contacts': contacts_file }
        if 'scope' not in oauth_settings:
            oauth_settings['scope'] = ShiftCalendar.default_scope
        self.oauth = oauth_settings
        self.oauth['token'] = None
        self.oauth['credentials'] = Storage(oauth_settings['credentials_file']).get()
        self.have_synced = False
        self.shifts = None
        self.people = {}

    def credentials_ok(self):
        """Return True if stored OAuth credentials are present and valid, False otherwise."""
        if self.oauth['credentials'] is None or \
                self.oauth['credentials'].invalid == True:
            return False
        return True

    def setup_credentials(self):
        """Run interactive OAuth 2.0 setup dance and return True on success, False otherwise."""
        gflags.FLAGS.auth_local_webserver = False
        storage = Storage(self.oauth['credentials_file'])
        flow = OAuth2WebServerFlow(
                client_id = self.oauth['client_id'],
                client_secret = self.oauth['client_secret'],
                scope = self.oauth['scope'],
                user_agent = self.oauth['user_agent'],
                xoauth_displayname = self.oauth['display_name'])
        self.oauth['credentials'] = oauth2client.tools.run(flow, storage)
        return not self.oauth['credentials'].invalid

    def get_token(self):
        """Return a OAuth2Token that can be used with gdata client objects."""
        if self.oauth['credentials'].access_token_expired:
            self.oauth['credentials']._refresh(httplib2.Http().request)
            self.oauth['token'] = None # need a new token after refreshing
        if self.oauth['token'] is None:
            self.oauth['token'] = gdata.gauth.OAuth2Token(
                    self.oauth['client_id'],
                    self.oauth['client_secret'],
                    self.oauth['scope'],
                    self.oauth['user_agent'],
                    access_token = self.oauth['credentials'].access_token,
                    refresh_token = self.oauth['credentials'].refresh_token)
        return self.oauth['token']

    def get_contacts_client(self):
        """Return an authenticated gdata.contacts.client.ContactsClient object."""
        client = gdata.contacts.client.ContactsClient(
                source=self.oauth['user_agent'])
        client.auth_token = self.get_token()
        return client

    def get_calendar_client(self):
        """Return an authenticated gdata.calendar.client.CalendarClient object."""
        client = gdata.calendar.client.CalendarClient(
                source=self.oauth['user_agent'])
        client.auth_token = self.get_token()
        return client

    def sync(self):
        """Download calendar and look up all contacts found in the calendar.

        Returns:
            number of shifts discovered on first run, True on subsequent runs."""
        if self.have_synced: # only sync once per instance
            return True

        use_cache = False
        calendar_file = open(self.cache_files['calendar'], 'r')
        cached_shifts = []
        for line in calendar_file:
            cached_shifts.append(Shift.loads(line))

        contacts_file = open(self.cache_files['contacts'], 'r')
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
        except Exception as exc: # pylint: disable=W0703
            # We don't really care what happened, we just know we can't trust
            # whatever we managed to sync from Google.
            use_cache = True
            logging.error("Exception when syncing: %s", exc)

        if use_cache:
            self.shifts = cached_shifts
            self.people = cached_people
            logging.error("Using cached data due to sync exception!")
        else: # we have synced successfully, so cache to disk
            # sort shifts according to start date (feed order not guaranteed)
            self.shifts = sorted(shifts, key=attrgetter('start'))

            # persist synced calendar to disk cache
            calendar_file = open(self.cache_files['calendar'], 'w')
            for shift in self.shifts:
                calendar_file.write("%s\n" % (shift.dumps()))
            calendar_file.close()

            # persist synced contacts to disk cache
            contacts_file = open(self.cache_files['contacts'], 'w')
            for person in self.people.values():
                contacts_file.write("%s\n" % (person.dumps()))
            contacts_file.close()

        self.have_synced = True
        return len(self.shifts)

    def get_person(self, query):
        """Given a text query, fetch and return a Person object. Caches results per query."""
        if query in self.people:
            person = self.people[query]
        else:
            person = Person(query)
        client = self.get_contacts_client()
        person.update(client)
        self.people[query] = person
        return person

    def get_current_shift(self):
        """Return the Shift object that overlaps with now, i.e. is current. Will sync if we haven't already."""
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
            logging.error("Was unable to find a shift overlapping with %s", now)
        return current_shift

    def get_last_shift(self):
        """Return the Shift object that is last in current calendar. Will sync if we haven't already."""
        if not self.have_synced:
            self.sync()
        last_shift = None
        last_shift = self.shifts.pop()
        if last_shift is None:
            logging.error("Was asked for last shift, but there are no shifts!")
        return last_shift

    def get_current_person(self):
        """Return the Person object associated with the Shift that is considered current. Will sync if haven't already."""
        if not self.have_synced:
            self.sync()
        current_shift = self.get_current_shift()
        if current_shift is None:
            logging.error("Asked for on call person, but no current shift!")
            return None
        return self.get_person(current_shift.title)

    def get_calendar_feed(self):
        """Return a raw calendar feed from Google Calendar.

        This is used by initial setup to show choices for CALENDAR_URL."""
        client = self.get_calendar_client()
        return client.GetAllCalendarsFeed()

class Shift:
    """Represents a single shift with a start and end time."""
    def __init__(self, title, start, end):
        self.title = title
        self.start = start
        self.end = end

    def __repr__(self):
        return repr((self.title, self.start, self.end))

    def dumps(self):
        """Return a representation of this object as a string."""
        return "%s\t%s\t%s" % (self.start, self.end, self.title)

    @staticmethod
    def loads(string):
        """Given a representation of an object of this class as a string, initialize and return the object."""
        string = string.split("\t")
        return Shift(string[2], parse_date(string[0]), parse_date(string[1]))

class Person:
    """Represents a person that can be responsible for multiple Shifts."""
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
        """Search for Person.query on Google Contacts and set email and phone number from first match.
        
        Will only sync once per instance."""
        if not self.have_synced:
            query = gdata.contacts.client.ContactsQuery()
            query.text_query = self.query
            feed = client.GetContacts(q = query)
            entry = None
            if len(feed.entry) == 1:
                entry = feed.entry[0]
            elif len(feed.entry) > 1:
                entry = feed.entry[0]
                logging.warning("Calendar title '%s' is too broad, matches %d contacts.", self.query, len(feed.entry))
            if entry is None:
                logging.error("Current shift does not match any contact! Query was: '%s'", self.query)
                sys.exit(os.EX_DATAERR)
            person = {'email': None, 'phone': None}
            for email in entry.email:
                if email.primary and email.primary == 'true':
                    person['email'] = email.address
            phone_numbers = {}
            for phone in entry.phone_number:
                # rel example: http://schemas.google.com/g/2005#mobile
                rel = phone.rel.split("#").pop()
                phone_numbers[rel] = phone.text
            for rel in settings.PHONE_TYPE_PREFERENCE:
                if rel in phone_numbers:
                    person['phone'] = phone_numbers[rel]

            self.email = person['email']
            self.phone = person['phone']
            self.have_synced = True

    def dumps(self):
        """Return a representation of this object as a string."""
        return "%s\t%s\t%s" % (self.query, self.email, self.phone)

    @staticmethod
    def loads(string):
        """Given a representation of an object of this class as a string, initialize and return the object."""
        string = string.split("\t")
        return Person(string[0], string[1], string[2])

class UTC(datetime.tzinfo):
    """Class representing the UTC "timezone". Necessary to work with timezone-aware datetime objects."""
    def utcoffset(self, _):
        return datetime.timedelta(0)

    def tzname(self, _):
        return "UTC"

    def dst(self, _):
        return datetime.timedelta(0)
