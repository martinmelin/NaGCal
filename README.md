# About

NaGCal is a way to keep your on call schedule in Google Calendar and look up
contact details to the person who is currently on call from Google Contacts.
It was built for use with Nagios, the network monitoring system.

# How to install

It should be fairly easy to install NaGCal. These are the general steps:

1. Download a release
2. Run python setup.py install to download dependencies
3. Copy the example configuration file to your config directory
4. Run nagcal --sync to set up a Google OAuth authentication token

When this is done, you can use the provided mail-to-oncall script as a
notification command in Nagios. It has been written to behave like /bin/mail,
with the exception that it sends email to the currently on call person if
there is one. If there is noone on call or an error occurs, it sends mail
to the address that was provided as an argument instead.

## Dependencies

NaGCal is written in Python and depends on a few other Python packages.
Running python setup.py install should download and install these for you.

- gdata
- iso8601
- httplib2
- oauth2client
- python-gflags

If you do not have an Internet connection, you also need the distribute package.

# Configuration

For a reliable NaGCal installation, you need to configure three things:

1. Your on-call Nagios contact notification command
2. Nagios checks of the NaGCal log
3. A crontab entry running nagcal --sync periodically

## Notification command

For each Nagios contact definition, you can provide a notification_command
that is executed to notify that particular contact.

You can use the default Nagios notification command, but instead of piping to
/bin/mail you pipe to /usr/bin/mail-to-oncall.

The mail-to-oncall script runs NaGCal to get the current on call email address.
If NaGCal exits with a non-zero exit code, the script uses the email address
that was provided on the command line instead ($CONTACTEMAIl in this case)

Because of this it is very important that the email address set for your
on-call Nagios contact is a working, monitored email address, preferably
an alias that addresses your whole on call group. If anything goes wrong
with NaGCal (either a bug or, more likely, a problem with your on call calendar)
the fallback address will receive alerts.

## Nagios checks of the NaGCal log

Nagios does not handle notification command failures gracefully, which is why
NaGCal uses a wrapper script to ensure that _someone_ always receives an email
even if there is a problem with NaGCal itself.

However, like any part of your environment, you should monitor NaGCal itself
to quickly discover when something goes wrong.

NaGCal logs WARNING and ERROR messages to whatever log_file is set to in nagcal.cfg.
Use one of the many available Nagios plugins for checking log files to monitor
this file for new entries.

## Periodically syncing with cron

NaGCal maintains a cache of calendar and contact data on disk, used only when either:

1. less than 60 seconds have passed between invocations of NaGCal
2. an exception occurs when connecting to Google (network problems for instance)

You should add an entry to your Nagios crontab running nagcal --sync, which will
update the on-disk cache with the latest calendar and contact data.

This ensures that even if a week passes between Nagios alerts, you do not get
week-old calendar data if whatever issue is to be alerted also affects connectivity
to Google.
