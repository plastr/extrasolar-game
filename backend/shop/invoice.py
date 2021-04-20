# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
import uuid

from front.lib import get_uuid, db, gametime, money, urls
from front.backend.shop import transaction as transaction_module

def start_pending_invoice_for_products(user, product_keys, product_specifics_list):
    """
    Create a new pending invoice, which has not yet been paid and is ready for a charge object.
    A number of assertions are checked about the supplied product_keys relative to the users current gamestate
    to verify the supplied products are allowed to be purchased and any product_specifics are also validated.
    This function returns the invoice object if everything worked, otherwise it returns None and a user
    facing error message if some aspect of the invoice was invalid (for instance product_specifics).
    Use this function instead of creating _PendingInvoice objects directly.
    """
    assert len(product_keys) > 0

    # If product_specifics_list is empty, pad it out with empty {}'s as a convenience.
    if len(product_specifics_list) == 0:
        product_specifics_list = [{} for p in product_keys]
    # The product_specifics_list must be the same length as product_keys as only
    # the caller can be responsible for mapping the specifics to the product_key by index.
    if len(product_keys) != len(product_specifics_list):
        raise InvoiceError("product_specifics_list must be the same length as product_keys [%s][%s][%s]" %
            (product_keys, product_specifics_list, user.user_id))

    # Validate the provided product_keys and turn them into AvailableProducts objects.
    products = []
    for product_key in product_keys:
        # Verify the product is in the list of available products.
        product = user.shop.available_products.get(product_key, None)
        if product is None:
            raise InvoiceError("Attempted purchase of not available product %s [%s]" % (product_key, user.user_id))
        # Validate any additional product constraints by calling through to the product callback.
        ok, error = product.can_purchase_with(product_keys)
        if not ok:
            raise InvoiceError(error)
        products.append(product)

    # Ask each available product to validate any product_specifics. Note that the validate_product_specifics
    # might modify the product_specifics dictionary values as needed to make them valid. If it is unable to
    # fix a value, then None is returned and a user facing error message.
    for available, product_specifics in zip(products, product_specifics_list):
        product_specifics, error = available.validate_product_specifics(product_specifics)
        if product_specifics is None:
            return None, error

    # An invoice must have a single currency currently, so derive that currency from the
    # available products being purchased and assert it is unique.
    currency = None
    for product in products:
        if currency is None:
            currency = product.currency
        else:
            assert currency == product.currency,\
                "All products to purchase with Stripe must have the same currency %s %s" % (product.product_key, currency)
    assert currency is not None

    return _PendingInvoice(user, currency, products, product_specifics_list), None

def load_all_invoices_for_user(ctx, user):
    """ Return all saved Invoice objects for the given user. """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, "shop/select_invoices_by_user_id", user_id=user.user_id)
        invoices = []
        for r in rows:
            invoice_id = get_uuid(r['invoice_id'])
            products = (p for p in user.shop.purchased_products.itervalues() if p.invoice_id == invoice_id)
            # Sort the products in a predictable order, by product_key, since purchased_at is most
            # likely going to be identical if more than one product was purchased in the same invoice.
            products = sorted(products, key=lambda p: p.product_key)
            transactions = transaction_module.load_transactions_by_invoice_id(ctx, invoice_id)
            invoices.append(Invoice(products=products, transactions=transactions, **r))
        return invoices

class Invoice(object):
    """
    Holds the data associated with a purchase invoice for the shop.

    :param invoice_id: The UUID for this invoice.
    :param user_id: The UUID for the user who paid this invoice.
    :param user_current_email: str, the email address for the user when they purchased this invoice. Saved
        here in case user deletion is every allowed so an invoice is still searchable by email address.
    :param currency: str, the ISO currency for the money represented by this invoice, e.g  'USD'.
    :param products: list, The list of PurchasedProducts purchased by this invoice.
    :param transactions: list, The list of Transactions used to pay this invoice.
    :param created: datetime, When this invoice was created.

    Fields:
    :param total_amount: int, the total amount of money, in pennies. (derived from the products)
    """
    def __init__(self, invoice_id, user_id, user_current_email, currency, products, transactions, created):
        self.invoice_id = get_uuid(invoice_id)
        self.user_id = get_uuid(user_id)
        self.currency = currency
        self.total_amount = sum((p.price for p in products))
        self.products = products
        self.transactions = transactions
        self.created = created

    @property
    def money(self):
        """ Return a Money object representing the total amount and currency of this invoice. """
        return money.from_amount_and_currency(self.total_amount, self.currency)

    @property
    def total_amount_display(self):
        """ Return a string representing the total amount for display to a user. """
        return money.format_money(self.money)

    @property
    def created_display(self):
        """ Return a string representing the creation time for display to a user. """
        return self.created.strftime("%m/%d/%Y %H:%M:%S")

    @property
    def products_display(self):
        """ Return a string representing the product names for display to a user. """
        return ", ".join([p.name for p in self.products])

    def url_admin(self):
        return urls.admin_invoice(self.invoice_id)

class InvoiceError(Exception): pass

class _PendingInvoice(Invoice):
    """
    Holds the data associated with a new, unpaid pending invoice object ready to buy the list of
    product_keys which identify the AvailableProducts from the given user's shop.
    This PendingInvoice requires pay_with_charge to be called to pay it and populate and persist
    all of its fields (including PurchasedProducts and Transactions).
    NOTE: PendingInvoice is considered private API to this module (hence the leading _) because
    start_pending_invoice_for_products performs a number of critical validation steps in the invoice
    data before the PendingInvoice is instantiated.

    :param products: list, The list of AvailableProducts about to be purchased by this invoice.
    See Invoice for more documentation on other fields on this class, some of which are not populated
    until pay_with_charge is called, like transactions.
    NOTE: Currently all products must be in the same currency as an Invoice only supports a single currency.
    """
    def __init__(self, user, currency, products, product_specifics_list):
        invoice_id = uuid.uuid1()
        transactions = []
        created = gametime.now()
        self._product_specifics_list = product_specifics_list
        # Tuck away the user object so it can be passed to pay_invoice.
        self._user = user
        super(_PendingInvoice, self).__init__(invoice_id, user.user_id, user.email, currency, products, transactions, created)

    def pay_with_charge(self, ctx, charge):
        # Pay the invoice with the provided Charge object.
        transaction = charge.pay_invoice(ctx, self._user, self)
        # Append the Transaction to the Invoices list now that the transaction is complete.
        self.transactions.append(transaction)
        with db.conn(ctx) as ctx:
            db.run(ctx, "shop/insert_invoice", invoice_id=self.invoice_id, user_id=self.user_id,
                # The user's current email is stashed away in case user deletion is every supported
                # this would mean invoices and transactions could still be looked up by an email address
                # even if the original User record has been deleted.
                user_current_email=self._user.email,
                currency=self.currency, created=self.created)

        # Record every product purchased by creating a PurchasedProduct for every AvailableProduct.
        for index, available in enumerate(self.products):
            # Replace the available product in the products list with the purchased product
            # which is what a persisted invoice looks like.
            # Pass through any product_specifics that were supplied for this product index.
            product_specifics = self._product_specifics_list[index]
            purchased = available.record_purchased_by_invoice(self, product_specifics)
            self.products[index] = purchased
