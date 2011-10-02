#!python
from lib import Shift
import settings

import sys
import json
import time
import gflags
import iso8601
import httplib2
import datetime
import atom.data
import gdata.gauth
import gdata.acl.data
import gdata.calendar.data
import gdata.calendar.client
from operator import attrgetter
from oauth2client.tools import run
from oauth2client.file import Storage
from oauth2client.client import OAuth2WebServerFlow
try:
    from xml.etree import ElementTree
except ImportError:
    from elementtree import ElementTree

storage = Storage(settings.NAGCAL_CREDENTIALS_FILE)
credentials = storage.get()
gflags.FLAGS.auth_local_webserver = False

if credentials is None or credentials.invalid == True:
    flow = OAuth2WebServerFlow(
            client_id = settings.GOOGLE_CLIENT_ID,
            client_secret = settings.GOOGLE_CLIENT_SECRET,
            scope = settings.GOOGLE_SCOPE,
            user_agent = settings.NAGCAL_USER_AGENT,
            xoauth_displayname = settings.NAGCAL_OAUTH_DISPLAYNAME)
    credentials = run(flow, storage)
if credentials.access_token_expired:
    credentials._refresh(httplib2.Http().request)

token = gdata.gauth.OAuth2Token(
        settings.GOOGLE_CLIENT_ID,
        settings.GOOGLE_CLIENT_SECRET,
        settings.GOOGLE_SCOPE,
        settings.NAGCAL_USER_AGENT,
        access_token = credentials.access_token,
        refresh_token = credentials.refresh_token)

client = gdata.calendar.client.CalendarClient(source=settings.NAGCAL_USER_AGENT)
client.auth_token = token

if settings.GOOGLE_CALENDAR_URL is None or len(settings.GOOGLE_CALENDAR_URL) == 0:
    print "No calendar URL configured! " + \
            "Please set settings.GOOGLE_CALENDAR_URL to one of the below URLs"
    calendars = []
    calendar_feed = client.GetAllCalendarsFeed()
    for calendar in calendar_feed.entry:
        print "%s\n%s\n%s\n" % (
                calendar.title.text,
                "-" * len(calendar.title.text),
                calendar.content.src)
    print >> sys.stderr, "Bailing out because settings.GOOGLE_CALENDAR_URL is not set."
    sys.exit(4)

shifts = []
event_feed = client.GetCalendarEventFeed(uri=settings.GOOGLE_CALENDAR_URL)
for event in event_feed.entry:
    shifts.append(Shift(event.title.text, iso8601.parse_date(event.when[0].start), iso8601.parse_date(event.when[0].end)))
# sort shifts according to start date/time (not guaranteed to be in order in feed)
shifts = sorted(shifts, key=attrgetter('start'))

calendar_file = open(settings.NAGCAL_CALENDAR_FILE, 'w')
for shift in shifts:
    calendar_file.write("%s\n" % (shift.dumps()))
calendar_file.close()

print "Wrote %s shifts to %s" % (len(shifts), settings.NAGCAL_CALENDAR_FILE)
