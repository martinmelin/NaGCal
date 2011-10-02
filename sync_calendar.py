#!python
from settings import * # only constants

from lib import Shift

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

storage = Storage(NAGCAL_CREDENTIALS_FILE)
credentials = storage.get()
FLAGS = gflags.FLAGS
FLAGS.auth_local_webserver = False

if credentials is None or credentials.invalid == True:
    flow = OAuth2WebServerFlow(
            client_id = GOOGLE_CLIENT_ID,
            client_secret = GOOGLE_CLIENT_SECRET,
            scope = GOOGLE_SCOPE,
            user_agent = NAGCAL_USER_AGENT,
            xoauth_displayname = NAGCAL_OAUTH_DISPLAYNAME)
    credentials = run(flow, storage)
if credentials.access_token_expired:
    credentials._refresh(httplib2.Http().request)

token = gdata.gauth.OAuth2Token(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_SCOPE, NAGCAL_USER_AGENT,
        access_token = credentials.access_token,
        refresh_token = credentials.refresh_token)

client = gdata.calendar.client.CalendarClient(source=NAGCAL_USER_AGENT)
client.auth_token = token

if GOOGLE_CALENDAR_URL is None or len(GOOGLE_CALENDAR_URL) == 0:
    print "No calendar URL configured! Please set GOOGLE_CALENDAR_URL to the URL of your on call calendar from the below list.\n"
    calendars = []
    calendar_feed = client.GetAllCalendarsFeed()
    for calendar in calendar_feed.entry:
        print "%s\n%s\n%s\n" % (calendar.title.text, "-" * len(calendar.title.text), calendar.content.src)
    sys.exit(4)

shifts = []
event_feed = client.GetCalendarEventFeed(uri=GOOGLE_CALENDAR_URL)
for event in event_feed.entry:
    shifts.append(Shift(event.title.text, iso8601.parse_date(event.when[0].start), iso8601.parse_date(event.when[0].end)))
# sort shifts according to start date/time (not guaranteed to be in order in feed)
shifts = sorted(shifts, key=attrgetter('start'))

calendar_file = open(NAGCAL_CALENDAR_FILE, 'w')
for shift in shifts:
    calendar_file.write("%s\n" % (shift.dumps()))
calendar_file.close()

print "Wrote %s shifts to %s" % (len(shifts), NAGCAL_CALENDAR_FILE)
