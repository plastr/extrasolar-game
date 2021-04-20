# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

import stripe

from front.lib import xjson, utils
from front.models import user as user_module
from front.backend.shop import stripe_gateway
from front.resource import json_success_with_chips, json_bad_request, json_bad_request_with_chips, decode_json

import logging
logger = logging.getLogger(__name__)

class StripeParentNode(resource.Resource):
    def __init__(self, request):
        self.user = user_module.user_from_request(request)

    @resource.child()
    def purchase_products(self, request, segments):
        return PurchaseProductsNode(request, self.user), segments

    @resource.child()
    def remove_saved_card(self, request, segments):
        return RemoveSavedCardNode(request, self.user), segments

class PurchaseProductsNode(resource.Resource):
    def __init__(self, request, user):
        self.user = user

    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        # stripe_token_id is not required.
        body, error = decode_json(request, required={
            'product_keys': list,
            'product_specifics_list': list
        })
        if body is None: return error

        # stripe_token_id can be None, if stripe_save_card is missing, it will be False.
        stripe_token_id        = body.get('stripe_token_id')
        stripe_save_card       = body.get('stripe_save_card', False)
        product_keys           = body['product_keys']
        product_specifics_list = body['product_specifics_list']

        try:
            if stripe_save_card:
                assert stripe_token_id is not None, "Must have stripe_token_id when saving card."
                self.user.shop.stripe_save_card(stripe_token_id)

            # If the user has a saved card, charge that, otherwise perform a one time charge.
            charge = stripe_gateway.pending_charge(self.user.shop.stripe_customer_id, stripe_token_id)

            # Buy the products with the Stripe charge object.
            invoice, error = self.user.shop.buy_product_keys_with_charge(product_keys, product_specifics_list, charge)
            # If an validation error happened when trying to make the purchase, return that error to the user.
            if invoice is None:
                return json_bad_request_with_chips(request, error)

        # An error occurred with the card itself, which we will show to the user in hopes that they can resolve it.
        # See https://stripe.com/docs/api/python#errors
        except stripe.CardError, e:
            err = e.json_body['error']

            # Log a warning with specific information to aid in production diagnostics.
            logger.warn("Stripe charge request resulted in card error, returning error to user. [%s][%s][%s]",
                self.user.user_id, self.user.shop.stripe_customer_id, err)

            # By default, return the apparently helpful message from Stripe. Override below as appropriate.
            # NOTE: Most of these potential card errors should have handled by stripe.js and the client, so this is
            # merely a safety net.
            # FUTURE: The Stripe error messages should be internationalized.
            error = err['message']

            # If the user had previously saved this card for reuse, wipe the card from the customer object as
            # it is clearly no longer valid and send a chip to the client removing the card.
            if self.user.shop.has_stripe_saved_card():
                self.user.shop.stripe_remove_saved_card()
                # If the card error was an expired card, be specific about the error message.
                if err['code'] == 'expired_card':
                    error = utils.tr("Your saved credit card has expired, please try again with your current card information.")

            # Return the hopefully helpful error message to the user.
            return json_bad_request_with_chips(request, error)

        # NOTE: The Stripe API might also raise InvalidRequestError, AuthenticationError, APIConnectionErrors, or
        # other generic StripeError exceptions but we will let those bubble up as additional recovery by the user seems
        # unlikely and we'll let the top level exception handler deal with them (rollback the transaction, return 500).

        return json_success_with_chips(request)

class RemoveSavedCardNode(resource.Resource):
    def __init__(self, request, user):
        self.user = user

    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        # Return a user friendly error message if requested to remove a saved card that has already been removed.
        if not self.user.shop.has_stripe_saved_card():
            return json_bad_request(utils.tr("No saved credit card to remove."))
        self.user.shop.stripe_remove_saved_card()
        return json_success_with_chips(request)
