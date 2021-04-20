# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
This module is a wrapper around the py-moneyed module to handle storing,
maniuplating, and formatting money and currencies.
"""
from functools import partial
from decimal import Decimal

from moneyed.classes import Money
from moneyed.localization import CurrencyFormatter

def from_amount_and_currency(amount_pennies, currency):
    """
    Return a moneyed.Money object constructed from the given amount of 'pennies' and the
    currency string, e.g. 100 and 'USD'.
    NOTE: The amount is in 'pennies', so 100 will become 1.00 when stored as a decimal
    inside of a Money object. Another version of this function might be required if
    amount is defined in other currencies.

    >>> from_amount_and_currency(1, 'USD')
    0.01 USD
    >>> from_amount_and_currency(100, 'USD')
    1 USD
    >>> from_amount_and_currency(123, 'USD')
    1.23 USD
    >>> from_amount_and_currency(-1234, 'USD')
    -12.34 USD
    """
    amount_dollars = Decimal(amount_pennies) / 100
    return Money(amount=amount_dollars, currency=currency)

def to_pennies(money):
    """
    Return an integer of the amount of pennies contained within the given moneyed.Money object
    NOTE: The amount is in 'pennies', so a Money object of '1.00 USD' will return 100.
    Another version of this function might be required if amount is defined in other currencies.

    >>> to_pennies(Money('12.34', 'USD'))
    1234
    >>> to_pennies(from_amount_and_currency(1, 'USD'))
    1
    >>> to_pennies(from_amount_and_currency(0, 'USD'))
    0
    >>> to_pennies(from_amount_and_currency(123, 'USD'))
    123
    >>> to_pennies(from_amount_and_currency(-1234, 'USD'))
    -1234
    """
    return int(money.amount.shift(2))

def format_money(money):
    """
    Return a string representation of this money object, suitable for displaying to a user.
    NOTE: Currently the output assumes a 'en_US' locale, so USD is shown as $, not US$

    >>> format_money(Money('12.34', 'USD'))
    u'$12.34'
    >>> format_money(Money('12.34', 'CAD'))
    u'12.34 CAD'
    >>> format_money(Money('.34', 'USD'))
    u'$0.34'
    """
    return _format_money_en_us(money)

# Define our own _format_money_en_us similar to the moneyed modules but with
# the en_US locale set instead of 'default'.
_FORMATTER = CurrencyFormatter()
_format_money_en_us = partial(_FORMATTER.format, locale='en_US')

def nearest_dime(money):
    """
    Return a Money object which is the given money object rounded to the nearest 'dime'.

    >>> nearest_dime(from_amount_and_currency(1234, 'USD'))
    12.30 USD
    >>> nearest_dime(from_amount_and_currency(1235, 'USD'))
    12.40 USD
    >>> nearest_dime(from_amount_and_currency(-1234, 'USD'))
    -12.30 USD
    """
    return money - Money(money.amount.remainder_near(Decimal('0.10')), money.currency)

def discount_from_credit_up_to_dime(initial_money, credit_money, percentage):
    """
    Discount an initial amount of money by a percentage of the credited amount of money.
    Returns the result as a Money object.
    e.g. $20 is discounted by 75% of $8.50
    :param percentage: is an integer, not a float (e.g. 75 not 0.75 for 75%)
    NOTE: The returned discounted amount of money will never be below 0.

    >>> i = from_amount_and_currency(2000, 'USD')
    >>> c = from_amount_and_currency(850, 'USD')
    >>> discount_from_credit_up_to_dime(i, c, 75)
    13.600 USD
    >>> discount_from_credit_up_to_dime(c, i, 75)
    0 USD
    >>> discount_from_credit_up_to_dime(Money('11.23', 'USD'), Money('3.42', 'USD'), 75)
    8.700 USD
    """
    discount = percentage % credit_money
    result = nearest_dime(initial_money - discount)
    return max(Money(0, initial_money.currency), result)
