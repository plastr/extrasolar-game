# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Contains useful standalone utilities. Please doctest all functions.
import time
import math
from datetime import datetime, timedelta
from front.lib import gametime

# Our cycle starts at midnight on June 6, 2010 UTC and has a 15.3-hour cycle.
PLANET_TIME_ORIGIN = datetime(2010, 6, 1, 0,0,0)
HOURS_PER_ERI = 15.3

# Calculate the current time in eris as a floating point value where the integer portion
# represents the day since our epoch and the fractional portion represents the time of 
# day (0=midnight, 0.25=sunrise, 0.5=noon, 0.75=sunset).
def time_in_eris():
    # Our time difference is of type timedelta
    time_since_origin = gametime.now() - PLANET_TIME_ORIGIN

    seconds_since_origin = time_since_origin.days*24*60*60 + time_since_origin.seconds
    return seconds_since_origin/(HOURS_PER_ERI*60*60)

# Convert a datetime object into a floating point value between 0.0 and 1.0 that
# represents the time of day on the planet (0=midnight, 0.25=sunrise, 0.5=noon).
def datetime_to_time_of_day(dt):
    # Our time difference is of type timedelta
    time_since_origin = dt - PLANET_TIME_ORIGIN

    seconds_since_origin = time_since_origin.days*24*60*60 + time_since_origin.seconds
    time_in_eris = seconds_since_origin/(HOURS_PER_ERI*60*60)
    return math.fmod(time_in_eris, 1.0)

# This function can be used to calculate the most recent sunrise or sunset events.
# event_threshold is a fractional floating point value representing
# the time of the event (0=midnight, 0.25=sunrise, 0.5=noon, 0.75=sunset)
# Return the number of hours since the event.
def hours_since_solar_event(event_threshold):
    """
    >>> hours_since_solar_event(0.5) >= 0
    True
    >>> hours_since_solar_event(0.5) <= HOURS_PER_ERI
    True
    """
    solar_position = time_in_eris()
    solar_event = math.floor(solar_position) + event_threshold
    while (solar_event >= solar_position):
        solar_event -= 1.0

    # Calculate the time difference, in eris, between the solar event and now.
    eris_since_event = solar_position - solar_event

    # Convert this difference into hours.
    return eris_since_event*HOURS_PER_ERI

def _local_time_offset(t=None):
    """Return offset of local zone from GMT, taking daylight savings into acount."""
    t = time.time()

    if time.localtime(t).tm_isdst and time.daylight:
        return time.altzone
    else:
        return time.timezone