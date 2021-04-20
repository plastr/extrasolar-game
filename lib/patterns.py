# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Contains regex patterns and can be used for validation.
import re

# Match an email address.
# Pattern lifted from: https://github.com/madisonmay/CommonRegex/blob/master/commonregex.py
EMAIL = u"([a-z0-9!#$%&'*+\/=?^_`{|.}~-]+@(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)"
def is_email_address(value):
    """
    Validates an email address.

    >>> is_email_address("test@example.com")
    True
    >>> is_email_address("test.this@long.domain.example.me")
    True
    >>> is_email_address("test.gmail.style+tag@gmail.com")
    True
    >>> is_email_address("invalid@domain")
    False
    >>> is_email_address("invalid&domain.com")
    False
    >>> is_email_address("test@.domain.com") # Actually seen in production
    False
    >>> is_email_address("test@domain..com") # Actually seen in production
    False
    """
    return _COMPILED[EMAIL].match(value) != None

# Compile all the regexes and place them in a map.
_COMPILED = {
    EMAIL: re.compile(EMAIL, re.IGNORECASE)
}
