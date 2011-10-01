import iso8601
import datetime

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
