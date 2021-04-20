# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import datetime

_now_override = None
_now_delta = None

def now():
    """ Return the current UTC time as a datetime object unless the test suites
    have overriden this value. """
    # If the value of now has been frozen, use that, otherwise use the wallclock.
    if _now_override:
        n = _now_override
    else:
        n = datetime.utcnow()

    # If a delta has been set, apply that to the 'now' value.
    if _now_delta:
        return n + _now_delta
    else:
        return n

def set_now(dt):
    """
    Freeze the gametime to the provide datetime value.
    NOTE: Any existing frozen 'now' or 'delta' are cleared by this function.
    This should ONLY BE USED BY TEST SUITES, never in game code.
    :param dt: datetime to set now to.

    >>> frozen = datetime(2016, 2, 15, 6, 33, 0)
    >>> now() == frozen
    False
    >>> set_now(frozen)
    >>> now() == frozen
    True
    >>> unset_now()
    >>> now() == frozen
    False
    """
    global _now_override
    unset_now()
    _now_override = dt

def restore_tick():
    """
    Assuming the gametime has been frozen before a call to this function, calculate the delta
    between actual wallclock time and the frozen gametime value and store that as a delta using
    set_now_delta. Then restore the clock ticking as normal, but now() will factor in that
    delta into its value.
    It is an error to call this function more than once between calls to set_now().

    >>> from datetime import timedelta
    >>> original_now = now()
    >>> frozen = original_now + timedelta(hours=2, minutes=10)
    >>> set_now(frozen)
    >>> now() == frozen
    True
    >>> now() == frozen
    True
    >>> restore_tick()
    >>> restore_tick()
    Traceback (most recent call last):
      ...
    AssertionError
    >>> now() == frozen
    False
    >>> (now() - frozen) < timedelta(seconds=1)
    True
    >>> unset_now()
    """
    assert _now_override is not None # Must call set_now() before calling restore_tick again.
    delta = _now_override - datetime.utcnow()
    unset_now()
    _set_now_delta(delta)

def unset_now():
    """
    Un-freeze the gametime, restoring it to ticking wallclock time.
    This also removes any delta value applied by set_now_delta.
    This should ONLY BE USED BY TEST SUITES, never in game code.
    """
    global _now_override, _now_delta
    _now_override = None
    _now_delta = None

## Private API
def _set_now_delta(time_delta):
    """
    Apply the given timedelta to the result from every call to gametime.now().
    This means that gametime.now() will still tick forward with the wallclock but it will
    have a delta always applied.
    This should ONLY BE USED BY TEST SUITES, never in game code.
    :param time_delta: timedelta object to add to every now() call.

    >>> from datetime import timedelta
    >>> delta = timedelta(hours=2, minutes=10)
    >>> original_now = now()
    >>> _set_now_delta(delta)
    >>> ((now() - original_now) - delta) < timedelta(seconds=1)
    True
    >>> unset_now()
    >>> (now() - original_now) < timedelta(seconds=1)
    True
    """
    global _now_delta
    _now_delta = time_delta
