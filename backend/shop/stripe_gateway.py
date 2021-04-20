# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
import stripe

from front.backend.shop import transaction as transaction_module

def init_module(stripe_secret_key):
    stripe.api_key = stripe_secret_key

# A singleton for this module as a convenience. Initialized to a StripeGateway instance.
_default_gateway = None

# Module singleton convenience wrappers.
def pending_charge(customer_id, token_id): return _default_gateway.pending_charge(customer_id, token_id)
def create_customer_with_token(token_id, email, description): return _default_gateway.create_customer_with_token(token_id, email, description)
def delete_customer(customer_id): return _default_gateway.delete_customer(customer_id)
# NOTE: Only use this function in testing or development, never production.
def _create_fake_stripe_token(*args, **kwargs): return _default_gateway.create_fake_stripe_token(*args, **kwargs)

class StripeGateway(object):
    @classmethod
    def pending_charge(cls, customer_id, token_id):
        """ Return a StripeCharge subclass object based on whether there is a saved customer_id or a one time token.
            The returned charge object is ready to pay an invoice.
            NOTE: Either customer_id or token_id must be None. """
        if customer_id is not None:
            return StripeCustomerCharge(customer_id)
        else:
            return StripeCardTokenCharge(token_id)

    @classmethod
    def create_customer_with_token(cls, token_id, email, description):
        """ Create a Stripe Customer object using the given token_id, so that the user can be charged
            in the future without requiring them to enter the credit card details again.
            Returns the Stripe Customer object, see Stripe API for details. Contains at least an 'id' field
            which is the customer_id and an active_card describing the credit card saved for this customer.
            NOTE: email and description are only used as metadata for the customer object to aid in searching. """
        customer = stripe.Customer.create(
            email=email,
            description=description,
            card=token_id
        )
        return customer

    @classmethod
    def delete_customer(cls, customer_id):
        """ Clear any saved credit card information attached to the existing Stripe Customer object and
            delete that object. """
        customer = stripe.Customer.retrieve(customer_id)
        customer.delete()

    @classmethod
    def create_fake_stripe_token(cls, card_number=4242424242424242, exp_month=12, exp_year=2020, cvc=123, name=None):
        """ This function generates a testing Stripe token using a dummy card that always works.
            The default values will create a token that will always allow a charge.
            NOTE: Only use this function in testing or development, never production. """
        card = {
            "number"    : card_number,
            "exp_month" : exp_month,
            "exp_year"  : exp_year,
            "cvc"       : cvc,
            "name"      : name
        }
        return stripe.Token.create(card=card)

# FUTURE: This class implies a base charge.Charge object, with
# pay_invoice(ctx, user, invoice) at least as part of its interface but
# we will not create that empty module until we have a second charge type.
class _StripeCharge(object):
    def __init__(self):
        # Set after pay_invoice is called.
        self._stripe_charge_id = None

    # Return the stripe.Charge object appropriate for the specific subclass.
    def create_stripe_charge(self, invoice, description):
        raise NotImplementedError

    def pay_invoice(self, ctx, user, invoice):
        assert self._stripe_charge_id is None, "A charge can only be used to pay an invoice once."
        assert invoice.total_amount > 0, "A charge cannot be used to pay an invoice with no amount."
        assert invoice.currency is not None

        # Create the charge with Stripe (paying the invoice). Include the user's email address
        # in case their user is ever deleted.
        description = "invoice_id: %s user_id: %s email: %s products: %s" %\
            (invoice.invoice_id, user.user_id, user.email, [str(p.product_key) for p in invoice.products])
        stripe_charge = self.create_stripe_charge(invoice, description)
        # Be sure the charge was paid.
        assert stripe_charge.paid, "Stripe charge failed to be marked paid %s" % stripe_charge.id
        self._stripe_charge_id = stripe_charge.id

        # Save the transaction record and return it to the invoice which called this method.
        # NOTE: The transaction fields are derived from the actual Stripe Charge object wherever possible
        # in case there is a discrepancy this should help with a auditing.
        gateway_data = {transaction_module.gateway_data_keys.STRIPE_CHARGE_ID: self._stripe_charge_id}
        return transaction_module.create_transaction(ctx, invoice, transaction_module.types.PAYMENT,
            stripe_charge.amount, stripe_charge.currency, transaction_module.gateways.STRIPE, gateway_data)

class StripeCustomerCharge(_StripeCharge):
    """ Used to pay an invoice using a saved Stripe customer object. """
    def __init__(self, customer_id):
        assert customer_id is not None
        self.customer_id = customer_id
        super(StripeCustomerCharge, self).__init__()

    def create_stripe_charge(self, invoice, description):
        return stripe.Charge.create(
            customer=self.customer_id,
            amount=invoice.total_amount,
            currency=invoice.currency,
            description=description
        )

class StripeCardTokenCharge(_StripeCharge):
    """ Used to pay an invoice using a single use Stripe token representing a credit card. """
    def __init__(self, token_id):
        assert token_id is not None
        self.token_id = token_id
        super(StripeCardTokenCharge, self).__init__()

    def create_stripe_charge(self, invoice, description):
        return stripe.Charge.create(
            card=self.token_id,
            amount=invoice.total_amount,
            currency=invoice.currency,
            description=description
        )

# Override the default gateway for testing.
def _override_default_gateway(gateway):
    global _default_gateway
    _default_gateway = gateway

# Call this to restore the original gateway functionality after testing.
def _restore_default_gateway():
    global _default_gateway
    _default_gateway = StripeGateway()

# Use the original gateway functionality by default.
_restore_default_gateway()
