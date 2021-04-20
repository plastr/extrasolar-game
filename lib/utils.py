# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Contains useful standalone utilities. Please doctest all functions.
from datetime import datetime, timedelta
import calendar
import math
import zlib

def tr(msg):
    """ This function is a placeholder for real i18n translation code, acting as an
        annotation for a string that will need to be translated."""
    return msg

def from_ts(val):
    """
    Returns a datetime value from a string in our timestamp format.
    :param val: A string representing a UNIX-like timestamp (seconds since epoch).

    >>> from_ts("0")
    datetime.datetime(1970, 1, 1, 0, 0)
    >>> from_ts("1297751612")
    datetime.datetime(2011, 2, 15, 6, 33, 32)
    >>> from_ts("1297751612.123")
    datetime.datetime(2011, 2, 15, 6, 33, 32)
    >>> from_ts(to_ts(datetime(2011, 2, 15, 6, 33, 32, 123000)))
    datetime.datetime(2011, 2, 15, 6, 33, 32)
    >>> from_ts(to_ts(datetime(2011, 2, 15, 6, 33, 32, 999999)))
    datetime.datetime(2011, 2, 15, 6, 33, 32)
    >>> from_ts(to_ts(datetime(2011, 2, 15, 6, 33, 32)))
    datetime.datetime(2011, 2, 15, 6, 33, 32)
    >>> from_ts(to_ts(datetime(2011, 3, 17, 16, 33, 32))) # Testing timezone bug.
    datetime.datetime(2011, 3, 17, 16, 33, 32)
    """
    return datetime.utcfromtimestamp(int(float(val)))

def to_ts(val):
    """
    Serializes a datetime to an int expressing a UNIX-like timestamp
    (seconds since epoch) e.g 1297751612
    :param val: A datetime object in UTC

    >>> to_ts(datetime(1970, 1, 1, 0, 0))
    0
    >>> to_ts(from_ts('1297751612.123'))
    1297751612
    >>> to_ts(from_ts('1297751612.123000'))
    1297751612
    >>> to_ts(from_ts('1300401280.068')) # Testing timezone bug.
    1300401280
    """
    return int(calendar.timegm(val.timetuple()))

## These usec_ functions are converters for our microsecond timestamp format.
#  This format allows for timestamps which count the number of microseconds since
#  the 1/1/1970 epoch to be safely passed between the database, Python, and Javascript.
#  The 'wire' format is always a string, the database format is bigint, and the Python
#  format is datetime objects, all with microsecond precision.

def usec_dt_from_js(val):
    """
    Returns a datetime value from a string in our JSON microsecond timestamp format.
    :param val: A string representing a UNIX-like timestamp (seconds since epoch) with microseconds.

    >>> usec_dt_from_js("0")
    datetime.datetime(1970, 1, 1, 0, 0)
    >>> usec_dt_from_js("123456")
    datetime.datetime(1970, 1, 1, 0, 0, 0, 123456)
    >>> usec_dt_from_js("3670123456")
    datetime.datetime(1970, 1, 1, 1, 1, 10, 123456)
    >>> usec_dt_from_js("1297751612123456")
    datetime.datetime(2011, 2, 15, 6, 33, 32, 123456)
    >>> usec_dt_from_js("1297751612999999")
    datetime.datetime(2011, 2, 15, 6, 33, 32, 999999)
    >>> usec_dt_from_js("1297751612123000")
    datetime.datetime(2011, 2, 15, 6, 33, 32, 123000)
    >>> usec_dt_from_js(1297751612999999)
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-string to datetime.
    """
    if not isinstance(val, basestring):
        raise TypeError("Cannot convert non-string to datetime.")
    (seconds, micros) = (val[:-6], val[-6:])
    if len(seconds) == 0: seconds = "0"
    return datetime.utcfromtimestamp(int(seconds)) + timedelta(microseconds=int(micros))

def usec_dt_from_db(val):
    """
    Returns a datetime value from an int in our database microsecond timestamp format.
    :param val: An int representing a UNIX-like timestamp (seconds since epoch) with microseconds.

    >>> usec_dt_from_db(0)
    datetime.datetime(1970, 1, 1, 0, 0)
    >>> usec_dt_from_db(123456)
    datetime.datetime(1970, 1, 1, 0, 0, 0, 123456)
    >>> usec_dt_from_db(3670123456)
    datetime.datetime(1970, 1, 1, 1, 1, 10, 123456)
    >>> usec_dt_from_db(1297751612123456)
    datetime.datetime(2011, 2, 15, 6, 33, 32, 123456)
    >>> usec_dt_from_db(1297751612999999)
    datetime.datetime(2011, 2, 15, 6, 33, 32, 999999)
    >>> usec_dt_from_db("1297751612999999")
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-int or long to datetime.
    >>> usec_dt_from_db(-100)
    Traceback (most recent call last):
      ...
    ValueError: Cannot convert negative number to datetime.
    """
    if not isinstance(val, (int,long)):
        raise TypeError("Cannot convert non-int or long to datetime.")
    if val < 0:
        raise ValueError("Cannot convert negative number to datetime.")
    s = str(val).rjust(7, '0')
    return usec_dt_from_js(s)

def usec_js_from_db(val):
    """
    Returns a JSON value from an int in our database microsecond timestamp format.
    :param val: A string representing a UNIX-like timestamp (seconds since epoch) with microseconds.

    >>> usec_js_from_db(0)
    '0'
    >>> usec_js_from_db(123456)
    '123456'
    >>> usec_js_from_db(3670123456)
    '3670123456'
    >>> usec_js_from_db(1297751612123456)
    '1297751612123456'
    >>> usec_js_from_db("1297751612123456")
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-int or long to JSON.
    """
    if not isinstance(val, (int,long)):
        raise TypeError("Cannot convert non-int or long to JSON.")
    return str(val)

def usec_js_from_dt(val):
    """
    Serializes a datetime to a string expressing a UNIX-like timestamp
    (seconds since epoch) and including the microseconds e.g 1297751612123456
    which is the JSON format for our microsecond timestamps.
    :param val: A datetime object in UTC

    >>> usec_js_from_dt(datetime(1970, 1, 1, 0, 0, 0))
    '0'
    >>> usec_js_from_dt(datetime(1970, 1, 1, 0, 0, 0, 123456))
    '123456'
    >>> usec_js_from_dt(datetime(1970, 1, 1, 1, 1, 10, 123456))
    '3670123456'
    >>> usec_js_from_dt(usec_dt_from_js('1297751612123000'))
    '1297751612123000'
    >>> usec_js_from_dt(usec_dt_from_js('1297751612123456'))
    '1297751612123456'
    >>> usec_js_from_dt(usec_dt_from_js('1300401280000068')) # Testing timezone bug.
    '1300401280000068'
    """
    seconds = calendar.timegm(val.timetuple())
    micros = val.microsecond
    return str((seconds * 1000000) + micros)

def usec_db_from_dt(val):
    """
    Serializes a datetime to an int expressing a UNIX-like timestamp
    (seconds since epoch) and including the microseconds e.g 1297751612123456
    which is the database format for our microsecond timestamps.
    :param val: A datetime object in UTC

    >>> usec_db_from_dt(datetime(1970, 1, 1, 0, 0, 0))
    0
    >>> usec_db_from_dt(datetime(1970, 1, 1, 0, 0, 0, 123456))
    123456
    >>> long(usec_db_from_dt(datetime(1970, 1, 1, 1, 1, 10, 123456))) # long() as Linux makes long
    3670123456L
    >>> long(usec_db_from_dt(usec_dt_from_db(1297751612123456)))
    1297751612123456L
    """
    return int(usec_js_from_dt(val))

def constant_time_compare(val1, val2):
    """
    Returns True if the two strings are equal, False otherwise.
    The time taken is independent of the number of characters that match.
    Lifted from: http://code.djangoproject.com/svn/django/trunk/django/utils/crypto.py

    >>> constant_time_compare("ABC", "ABC")
    True
    >>> constant_time_compare("ABC", "ABD")
    False
    >>> constant_time_compare("ABC", "ABCD")
    False
    """
    if len(val1) != len(val2):
        return False
    result = 0
    for x, y in zip(val1, val2):
        result |= ord(x) ^ ord(y)
    return result == 0

BASE_62 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
def int_to_base62(n):
    """
    Encode an int or long into a 'base62' string (lower and upper letters and digits).

    >>> int_to_base62(100)
    '1c'
    >>> int_to_base62(1000000000000000000000000000000000000)
    '1Q0wbBCZxbBEnr2alT9t2'
    >>> base62_to_int(int_to_base62(1000))
    1000
    >>> int_to_base62("string")
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-int or long to base.
    >>> int_to_base62(-100)
    Traceback (most recent call last):
      ...
    ValueError: Cannot convert negative number.
    """
    return _int_to_base_alphabet(n, BASE_62)

def base62_to_int(s):
    """
    Decode a string encoded as a 'base62' string (lower and upper letters and digits) into an int or long.

    >>> base62_to_int('1c')
    100
    >>> base62_to_int('1Q0wbBCZxbBEnr2alT9t2')
    1000000000000000000000000000000000000L
    >>> int_to_base62(base62_to_int('1c'))
    '1c'
    >>> base62_to_int(100)
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-string from base to int.
    """
    return _base_alphabet_to_int(s, BASE_62)

BASE_32 = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
def int_to_base32(n):
    """
    Encode an int or long into a 'base62' string (lower and upper letters and digits).

    >>> int_to_base32(100)
    '56'
    >>> int_to_base32(1000000000000000000000000000000000000)
    'S4DWWYYB2WCV8LWZ42222222'
    >>> base32_to_int(int_to_base32(1000))
    1000
    >>> int_to_base32("string")
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-int or long to base.
    >>> int_to_base32(-100)
    Traceback (most recent call last):
      ...
    ValueError: Cannot convert negative number.
    """
    return _int_to_base_alphabet(n, BASE_32)

def base32_to_int(s):
    """
    Decode a string encoded as a 'base62' string (lower and upper letters and digits) into an int or long.

    >>> base32_to_int('56')
    100
    >>> base32_to_int('S4DWWYYB2WCV8LWZ42222222')
    1000000000000000000000000000000000000L
    >>> int_to_base32(base32_to_int('56'))
    '56'
    >>> base62_to_int(100)
    Traceback (most recent call last):
      ...
    TypeError: Cannot convert non-string from base to int.
    """
    return _base_alphabet_to_int(s, BASE_32)

def keycode_for_namespace(namespace, *args):
    """
    For a given 'namespace' string and set of string-able arguments return a base32 encoded
    hash useable as a 'keycode' for the provided values.
    NOTE: This function should NOT be used for anything that is critically secure. It uses
    a non-secure hash. The results are sufficient for game related secrets though.

    >>> keycode_for_namespace('first.namespace', 'd675ba88-18c9-11e2-929a-12313f008a78')
    '5T87TFC'
    >>> keycode_for_namespace('other.namespace', 'd675ba88-18c9-11e2-929a-12313f008a78')
    '5AB3Z4K'
    >>> keycode_for_namespace('nonnegative.namespace', 'value')
    '3MDVMPV'
    """
    value = "".join([unicode(a) for a in args]) + namespace
    hashed = zlib.crc32(value)
    # If the hash is negative (signed) convert to signed as our encoders only work with positive ints.
    if hashed < 0:
        hashed = hashed & 0xFFFFFFFF
    return int_to_base32(hashed)

def seconds_between_datetimes(dt1, dt2):
    """
    Return the number of seconds between two datetime objects as an integer, truncating microseconds.

    >>> seconds_between_datetimes(datetime(2011, 2, 15, 6, 33, 0), datetime(2011, 2, 15, 6, 33, 30))
    30
    >>> seconds_between_datetimes(datetime(2011, 2, 15, 6, 33, 30), datetime(2011, 2, 15, 6, 33, 0))
    -30
    >>> seconds_between_datetimes(datetime(2011, 2, 15, 6, 33, 0), datetime(2011, 2, 16, 6, 33, 30))
    86430
    >>> seconds_between_datetimes(datetime(2011, 2, 16, 6, 33, 30), datetime(2011, 2, 15, 6, 33, 0))
    -86430
    >>> seconds_between_datetimes(datetime(2011, 2, 15, 6, 33, 0, 123000), datetime(2011, 2, 15, 6, 33, 30))
    29
    >>> seconds_between_datetimes(datetime(2011, 2, 15, 6, 33, 0, 999999), datetime(2011, 2, 15, 6, 33, 30))
    29
    """
    delta = dt2 - dt1
    return delta.days*86400 + delta.seconds  # Microseconds were discarded.

def in_seconds(days=0, hours=0, minutes=0, seconds=0):
    """
    Tiny helper that is similar to the timedelta API that turns the keyword arguments into
    seconds. Most useful for calculating the number of seconds relative to an epoch.

    >>> in_seconds()
    0
    >>> in_seconds(hours=1.5)
    5400
    >>> in_seconds(hours=3)
    10800
    >>> in_seconds(minutes=30)
    1800
    >>> in_seconds(hours=3, minutes=30, seconds=10)
    12610
    >>> in_seconds(days=1)
    86400
    >>> in_seconds(days=3, hours=10)
    295200
    """
    return int((days * 86400) + (hours * 3600) + (minutes * 60) + seconds)

def utc_date_in_pst(dt_utc):
    """
    Return the given datetime object in UTC converted to PST.

    >>> utc = datetime(2013, 8, 8, 12, 0, 0)
    >>> utc_date_in_pst(utc)
    datetime.datetime(2013, 8, 8, 4, 0)
    """
    return dt_utc - timedelta(hours=8)

def format_time_approx(seconds):
    """
    Format the provided number of elapsed seconds as a user friendly string.

    >>> format_time_approx(0)
    'just now'
    >>> format_time_approx(10)
    'just now'
    >>> format_time_approx(60)
    'one minute'
    >>> format_time_approx(70)
    'one minute'
    >>> format_time_approx(70)
    'one minute'
    >>> format_time_approx(220)
    '3 minutes'
    >>> format_time_approx(280)
    '4 minutes'
    >>> format_time_approx(3600)
    '60 minutes'
    >>> format_time_approx(3660)
    'one hour'
    >>> format_time_approx(4000)
    'one hour'
    >>> format_time_approx(8000)
    '2 hours'
    >>> format_time_approx(86400)
    '24 hours'
    >>> format_time_approx(90000)
    'one day'
    >>> format_time_approx(90000*2)
    '2 days'
    >>> format_time_approx(90000*10)
    '10 days'
    """
    # NOTE: These strings need to be localized using utils.tr
    time_in_minutes = seconds/60
    if (time_in_minutes < 1.0):  return 'just now'
    if (time_in_minutes < 1.5):  return 'one minute'
    if (time_in_minutes < 60.5): return '%d minutes' % math.floor(time_in_minutes+0.5)

    time_in_hours = seconds/3600
    if (time_in_hours < 1.5):    return 'one hour'
    if (time_in_hours < 24.5):   return '%d hours' % math.floor(time_in_hours+0.5)

    time_in_days = seconds/86400
    if (time_in_days < 2.0):     return 'one day'
    return '%d days' % math.floor(time_in_days)

class NoOverrideMetaClass(type):
    """
    Meta-class for which protects subclasses from overridding any method listed in NO_OVERRIDE.

    >>> class Base(object):
    ...     __metaclass__ = NoOverrideMetaClass
    ...     NO_OVERRIDE = ['no_override_base']

    >>> class ChildNormal(Base):
    ...     def different_method(): pass

    >>> class ChildCannotOverride(Base):
    ...     def no_override_base(): pass
    Traceback (most recent call last):
      ...
    Exception: Cannot override methods in subclass [ChildCannotOverride] overridden=['no_override_base']

    >>> class ChildAddToOverride(Base):
    ...     NO_OVERRIDE = ['no_override_child']

    >>> class GrandChildCannotOverrideBase(ChildAddToOverride):
    ...     def no_override_base(): pass
    Traceback (most recent call last):
      ...
    Exception: Cannot override methods in subclass [GrandChildCannotOverrideBase] overridden=['no_override_base']

    >>> class GrandChildCannotOverrideChild(ChildAddToOverride):
    ...     def no_override_child(): pass
    Traceback (most recent call last):
      ...
    Exception: Cannot override methods in subclass [GrandChildCannotOverrideChild] overridden=['no_override_child']
    """
    def __init__(cls, name, bases, dct):
        super(NoOverrideMetaClass, cls).__init__(name, bases, dct)
        # If this specific class (not subclasses) provides a NO_OVERRIDE list, then it is a
        # base class which is using this metaclass to protect its methods from being overriden.
        # Add any of _its_ base class NO_OVERRIDE values to its NO_OVERRIDE list to emulate inheritence for the
        # NO_OVERRIDE field and skip enforcement on this class since it is not the implementing class.
        if 'NO_OVERRIDE' in cls.__dict__:
            for o in reduce(lambda x,y: x+y, [getattr(b, 'NO_OVERRIDE', []) for b in bases]):
                if o not in cls.__dict__['NO_OVERRIDE']:
                    cls.__dict__['NO_OVERRIDE'].append(o)
        # Otherwise this is an 'implementing' subclass and should have its methods checked against NO_OVERRIDE.
        else:
            if not hasattr(cls, 'NO_OVERRIDE'):
                return
            overridden = [override for override in cls.__dict__ if override in cls.NO_OVERRIDE]
            if len(overridden) > 0:
                raise Exception("Cannot override methods in subclass [%s] overridden=%s" % (name, overridden))

class RequiredNotNoneMetaClass(type):
    """
    Meta-class for which enforces all fields listed in REQUIRED_NOT_NONE are defined and not None in subclasses.

    >>> class Base(object):
    ...     __metaclass__ = RequiredNotNoneMetaClass
    ...     REQUIRED_NOT_NONE = ['not_none_base']

    >>> class ChildNormal(Base):
    ...     not_none_base = True

    >>> class ChildHasMissing(Base): pass
    Traceback (most recent call last):
      ...
    Exception: Some class fields cannot be None [ChildHasMissing] fields=['not_none_base']

    >>> class ChildDefinedNone(Base):
    ...     not_none_base = None
    Traceback (most recent call last):
      ...
    Exception: Some class fields cannot be None [ChildDefinedNone] fields=['not_none_base']

    >>> class ChildAddToNotNone(Base):
    ...     REQUIRED_NOT_NONE = ['not_none_child']

    >>> class GrandChildMissingBase(ChildAddToNotNone):
    ...     not_none_child = True
    Traceback (most recent call last):
      ...
    Exception: Some class fields cannot be None [GrandChildMissingBase] fields=['not_none_base']

    >>> class GrandChildMissingChild(ChildAddToNotNone):
    ...     not_none_base = True
    Traceback (most recent call last):
      ...
    Exception: Some class fields cannot be None [GrandChildMissingChild] fields=['not_none_child']
    """
    def __init__(cls, name, bases, dct):
        super(RequiredNotNoneMetaClass, cls).__init__(name, bases, dct)
        # If this specific class (not subclasses) provides a REQUIRED_NOT_NONE list, then it is a
        # base class which is using this metaclass to protect its fields from being None.
        # Add any of _its_ base class REQUIRED_NOT_NONE values to its REQUIRED_NOT_NONE list to emulate inheritence
        # for the REQUIRED_NOT_NONE field and skip enforcement on this class since it is not the implementing class.
        if 'REQUIRED_NOT_NONE' in cls.__dict__:
            for o in reduce(lambda x,y: x+y, [getattr(b, 'REQUIRED_NOT_NONE', []) for b in bases]):
                if o not in cls.__dict__['REQUIRED_NOT_NONE']:
                    cls.__dict__['REQUIRED_NOT_NONE'].append(o)
        # Otherwise this is an 'implementing' subclass and should have its fields checked against REQUIRED_NOT_NONE.
        else:
            if not hasattr(cls, 'REQUIRED_NOT_NONE'):
                return
            is_none = [f for f in cls.REQUIRED_NOT_NONE if f not in cls.__dict__ or cls.__dict__[f] == None]
            if len(is_none) > 0:
                raise Exception("Some class fields cannot be None [%s] fields=%s" % (name, is_none))

class NoOverrideRequiredNotNoneMetaClass(NoOverrideMetaClass, RequiredNotNoneMetaClass):
    """ Cannot do multiple inheritence from __metaclass__ directly so build a special metaclass to combine these. """
    pass

## Internal utilities.
def _int_to_base_alphabet(n, alphabet):
    """
    Encode an int or long into a base alphabet.
    """
    if not isinstance(n, (int,long)):
        raise TypeError("Cannot convert non-int or long to base.")
    if n < 0:
        raise ValueError("Cannot convert negative number.")
    encoded = ''
    while n > 0:
        n, r = divmod(n, len(alphabet))
        encoded = alphabet[r] + encoded
    return encoded

def _base_alphabet_to_int(s, alphabet):
    """
    Decode a string encoded in a given base alphabet into an int or long.
    """
    if not isinstance(s, basestring):
        raise TypeError("Cannot convert non-string from base to int.")
    decoded = 0
    while len(s) > 0:
        decoded = decoded * len(alphabet) + alphabet.find(s[0])
        s = s[1:]
    return decoded
