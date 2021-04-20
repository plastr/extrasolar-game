# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
import uuid
from front.lib import get_uuid, db, gametime, urls, money

class types(object):
    PAYMENT = "PAYMENT"
    ALL = set([PAYMENT])

class gateways(object):
    STRIPE = "STRIPE"
    ALL = set([STRIPE])

class gateway_data_keys(object):
    STRIPE_CHARGE_ID = "TXN_STRIPE_CHARGE_ID"
    ALL = set([STRIPE_CHARGE_ID])

def create_transaction(ctx, invoice, transaction_type, amount, currency, gateway_type, gateway_data):
    """ Create a new Transaction object and persist it. See Transaction class for parameter documentation. """
    assert transaction_type in types.ALL
    assert gateway_type in gateways.ALL
    for k in gateway_data:
        assert k in gateway_data_keys.ALL
    params = {}
    params['transaction_id']   = uuid.uuid1()
    params['invoice_id']       = invoice.invoice_id
    params['user_id']          = invoice.user_id
    params['transaction_type'] = transaction_type
    params['amount']           = amount
    params['currency']         = currency
    params['gateway_type']     = gateway_type
    params['created']          = gametime.now()

    with db.conn(ctx) as ctx:
        db.run(ctx, "shop/insert_transaction", **params)
        for k, v in gateway_data.iteritems():
            db.run(ctx, "shop/insert_transaction_gateway_data", transaction_id=params['transaction_id'], key=k, value=v)
    return Transaction(gateway_data=gateway_data, **params)

def load_transactions_by_invoice_id(ctx, invoice_id):
    """ Return all Transaction objects associated with this invoice_id. """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, "shop/select_transactions_by_invoice_id", invoice_id=invoice_id)
        return [Transaction.from_db_row(ctx, r) for r in rows]

class Transaction(object):
    """
    Holds the data associated with a single shop transaction record.

    :param transaction_id: The UUID for this transaction.
    :param invoice_id: The UUID for the invoice which generated this transaction.
    :param user_id: The UUID for the user who created this invoice.
    :param transaction_type: str, the 'type' of this transaction, e.g. PAYMENT. See types in transaction module.
    :param amount: int, the amount of currency represented by this transaction (e.g. pennies for 'USD').
    :param currency: str, the ISO currency for the money represented by this transaction, e.g  'USD'.
    :param gateway_data: dict, the keys and values of any extra gateway metadata, e.g. a charge identifier.
    :param created: datetime, When this transaction was created.
    :param _email: str, Optionally the email address for the user might be provided when loading it as
        part of the database select is more efficient. Do not rely on this being not None unless you know how
        this Transaction was loaded.
    """
    def __init__(self, transaction_id, invoice_id, user_id, transaction_type, amount,
                 currency, gateway_type, gateway_data, created, _email=None):
        self.transaction_id = get_uuid(transaction_id)
        self.invoice_id = get_uuid(invoice_id)
        self.user_id = get_uuid(user_id)
        self.transaction_type = transaction_type
        self.currency = currency
        self.amount = amount
        self.gateway_type = gateway_type
        self.gateway_data = gateway_data
        self.created = created
        self._email = _email

    @classmethod
    def from_db_row(cls, ctx, db_row):
        """ Construct a Transaction object from the given transaction database row. """
        with db.conn(ctx) as ctx:
            gateway_data_rows = db.rows(ctx, "shop/select_transaction_gateway_data_by_transaction_id", transaction_id=db_row['transaction_id'])
            gateway_data = dict(((r['key'], r['value']) for r in gateway_data_rows))
            return cls(gateway_data=gateway_data, **db_row)

    @property
    def money(self):
        """ Return a Money object representing the amount and currency of this transaction. """
        return money.from_amount_and_currency(self.amount, self.currency)

    @property
    def amount_display(self):
        """ Return a string representing the amount for display to a user. """
        return money.format_money(self.money)

    def gateway_data_as_html(self):
        """ Return any gateway data formatted as HTML, e.g. a gateway charge id linked to the gateways admin system. """
        if self.transaction_type == types.PAYMENT and self.gateway_type == gateways.STRIPE:
            charge_id = self.gateway_data[gateway_data_keys.STRIPE_CHARGE_ID]
            return '<a href="%s">%s</a>' % (urls.admin_stripe_charge_info(charge_id), charge_id)
        else:
            raise Exception("Do not know how to format transaction for HTML [%s][%s]" % (self.transaction_type, self.gateway_type))

    def user_admin_as_html(self):
        """ Return the user associated with this transaction as HTML (an href).
            Uses _email if available otherwise the user_id for the href description. """
        if self._email is not None:
            return '<a href="%s">%s</a>' % (urls.admin_user(self.user_id), self._email)
        else:
            return '<a href="%s">%s</a>' % (urls.admin_user(self.user_id), self.user_id)
