# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from collections import namedtuple
import stripe

from front.backend.shop import stripe_gateway

# Mock the stripe_gateway module with the MockStripeGateway object in this class.
# NOTE: Be sure to call unmock_gateway when finished.
def mock_gateway_with_charge(charge):
    stripe_gateway._override_default_gateway(MockStripeGateway(charge))

# Unmock the stripe_gateway module, restoring the original implementation.
def unmock_gateway():
    stripe_gateway._restore_default_gateway()

# This string is inserted in the fake Stripe id values to flag them as fake.
FAKE_MARKER = "FaKe"
# A few normal looking but actually fake Stripe id values for testing without requiring the live Stripe API.
FAKE_CHARGE_ID_1 = 'ch_FaKeRnOfeB' + FAKE_MARKER
FAKE_CHARGE_ID_2 = 'ch_FaKefeBRnO' + FAKE_MARKER
FAKE_CUSTOMER_ID = "cus_FaKeoWALcB" + FAKE_MARKER
FAKE_TOKEN_ID = "tok_FaKeJTGaQW" + FAKE_MARKER
# Fake, but valid, credit card information.
FAKE_CARD_NUMBER = "4242424242424242"
FAKE_CARD_TYPE = "Visa"
FAKE_CARD_LAST4 = FAKE_CARD_NUMBER[-4:]
FAKE_CARD_EXP_MONTH = "1"
FAKE_CARD_EXP_YEAR = "2016"
FAKE_CARD_NAME = "Homer Simpson"

# A mock object which conforms to the StripeGateway interface but returns fake data from the API calls.
class MockStripeGateway(object):
    def __init__(self, dummy_charge, dummy_customer_id=FAKE_CUSTOMER_ID, dummy_token_id=FAKE_TOKEN_ID):
        self.dummy_charge = dummy_charge
        fake_card = FakeStripeCard(FAKE_CARD_TYPE, FAKE_CARD_LAST4, FAKE_CARD_EXP_MONTH, FAKE_CARD_EXP_YEAR, FAKE_CARD_NAME)
        self.dummy_customer = FakeStripeCustomer(dummy_customer_id, fake_card)
        self.dummy_token_id = FakeStripeToken(dummy_token_id)

    def pending_charge(self, customer_id, token_id):
        return self.dummy_charge

    def create_customer_with_token(self, token_id, email, description):
        return self.dummy_customer

    # Deleting always succeeds.
    def delete_customer(self, customer_id):
        return

    def create_fake_stripe_token(self, **kwargs):
        return self.dummy_token_id

# A named tuple to hold the Stripe charge object fields actually used in stripe_gateway.
FakeStripeCharge = namedtuple('FakeStripeCharge', ['paid', 'id', 'amount', 'currency'])

# A named tuple to hold the Stripe token object fields actually used in stripe_gateway.
FakeStripeToken = namedtuple('FakeStripeToken', ['id'])

# A named tuple to hold the Stripe customer object fields actually used in stripe_gateway.
FakeStripeCustomer = namedtuple('FakeStripeCustomer', ['id', 'active_card'])
FakeStripeCard = namedtuple('FakeStripeCard', ['type', 'last4', 'exp_month', 'exp_year', 'name'])

# This StripeCharge subclass always returns success with a dummy charge object.
class ChargeAlwaysSuccess(stripe_gateway._StripeCharge):
    def __init__(self, charge_id):
        self.charge_id = charge_id
        super(ChargeAlwaysSuccess, self).__init__()

    def create_stripe_charge(self, invoice, description):
        return FakeStripeCharge(True, self.charge_id, invoice.total_amount, invoice.currency)

# This StripeCharge subclass is used to raise stripe.CardErrors for testing.
class ChargeCardError(stripe_gateway._StripeCharge):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super(ChargeCardError, self).__init__()

    def create_stripe_charge(self, invoice, description):
        err = {'code':self.code, 'type':'card_error', 'message':self.message}
        e = stripe.CardError(err['message'], None, err['code'], json_body={'error':err})
        raise e
