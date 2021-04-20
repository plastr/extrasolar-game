# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
from front import models
from front.lib import db, urls, xjson
from front.models import chips
from front.models import product as product_module
from front.backend.shop import stripe_gateway
from front.backend.shop import invoice as invoice_module
from front.callbacks import run_callback, SHOP_CB

STRIPE_PUBLISHABLE_KEY = None
def init_module(stripe_publishable_key):
    global STRIPE_PUBLISHABLE_KEY
    STRIPE_PUBLISHABLE_KEY = stripe_publishable_key

# This is the id field value for this shop object. There is only one shop object
# per user (which is the parent) so this key identifies this one instance in
# the chip path hierarchy.
SHOP_ID = 'shop'

class Shop(chips.Model, models.UserChild):
    """
    Holds the parameters for the singleton shop instance.

    :param shop_id: The unique identifier for this single shop instance, required for the chip path.
    :param stripe_customer_id: The Stripe customer_id value, used to charge a user's card without requiring the
        card details to be reentered. Can be None if no card has been saved by the user.
    :param stripe_has_saved_card: An integer boolean which indicates whether this user has a saved Stripe card on
        file. This value exists so it can be safely shared with the client, rather than exposing the customer_id.
    """
    id_field = 'shop_id'
    # stripe_customer_data is a dict holding at least card_type, card_last4, card_exp_month, card_exp_year and
    # card_name values (e.g. 'Visa', '4242', '1', '2014', 'Homer Simpson').
    # If stripe_has_saved_card is 0 then stripe_customer_data will be None. It is persisted as a JSON string.
    fields = frozenset(['stripe_customer_id', 'stripe_customer_data', 'stripe_has_saved_card', 'stripe_publishable_key'])
    collections = frozenset(['available_products', 'purchased_products'])
    server_only_fields = frozenset(['stripe_customer_id'])
    # Not a chips.Collection, just a lazy loaded server side only list of sorted Invoice objects.
    invoices  = chips.LazyField("invoices", lambda m: m._load_user_invoices())

    # user_id is a database only field.
    def __init__(self, stripe_customer_id, stripe_customer_data, user_id=None):
        # Decode the JSON serialized stripe customer data, if present.
        if stripe_customer_data is not None:
            stripe_customer_data = xjson.loads(stripe_customer_data)
        stripe_has_saved_card = 1 if stripe_customer_id is not None else 0
        super(Shop, self).__init__(shop_id=SHOP_ID,
                                   stripe_customer_id=stripe_customer_id,
                                   stripe_customer_data=stripe_customer_data,
                                   stripe_has_saved_card=stripe_has_saved_card,
                                   stripe_publishable_key=STRIPE_PUBLISHABLE_KEY,
                                   available_products=AvailableProductCollection.load_later('available_products', self._load_available_products),
                                   purchased_products=PurchasedProductCollection.load_later('purchased_products', self._load_purchased_products))

    @property
    def user(self):
        # self.parent is user
        return self.parent

    def has_stripe_saved_card(self):
        return self.stripe_has_saved_card == 1

    def buy_product_keys_with_charge(self, product_keys, product_specifics_list, charge):
        """ Purchase the given list of product_keys using the provided charge object.
            All of the provided product keys must be present in the available_products collection.
            Returns the Invoice object that encapsulates all purchased products and transactions. """
        # Be sure all available products are loaded so their availability and price values can be
        # compared pre and post product purchasing, as they might change and require a chip.
        self.available_products.available_and_price_prepare_refresh()

        # Create the pending invoice and then pay it with the charge, sending any chips.
        with db.conn(self.ctx) as ctx:
            invoice, error = invoice_module.start_pending_invoice_for_products(self.user, product_keys, product_specifics_list)
            # If the invoice failed to be created because of a validation error most likely from user supplied
            # data then return None and the error message.
            if invoice is None:
                return None, error
            invoice.pay_with_charge(ctx, charge)

        # New purchased products means that an available product which is using purchased products to determine
        # availability state or price might now have new values.
        self.available_products.available_and_price_refresh()

        # Inform the callbacks that this invoice was paid.
        run_callback(SHOP_CB, "invoice_was_paid", ctx=self.ctx, user=self.user, invoice=invoice)

        return invoice, None

    def stripe_save_card(self, stripe_token_id):
        """ Save the user's credit card with Stripe using the given token_id and store the resulting Stripe
            customer_id in the stripe_customer_id field.
            NOTE: Though the API supports replacing a customer card, currently this method requires
            that the shop has no saved customer_id when it is called. """
        assert self.stripe_customer_id is None, "Must not have customer_id when saving card."
        assert not self.has_stripe_saved_card()
        # Save the customer via the Stripe API.
        description = "Customer for %s, user_id: %s" % (self.user.email, self.user.user_id)
        customer = stripe_gateway.create_customer_with_token(stripe_token_id, self.user.email, description)
        # Save all the Stripe customer data into the shop model and database row.
        self.stripe_customer_id = customer.id
        self.stripe_customer_data = {
            'card_type': customer.active_card.type,
            'card_last4': customer.active_card.last4,
            'card_exp_month': str(customer.active_card.exp_month),
            'card_exp_year': str(customer.active_card.exp_year),
            'card_name': customer.active_card.name
        }
        self.stripe_has_saved_card = 1
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'shop/update_users_shop_stripe', user_id=self.user.user_id,
                stripe_customer_id=self.stripe_customer_id, stripe_customer_data=xjson.dumps(self.stripe_customer_data))
            self.send_chips(ctx, self.user)

    def stripe_remove_saved_card(self):
        """ Remove the user's saved credit card from Stripe and also clear out the stripe_customer_id field.
            NOTE: Must have a saved stripe_customer_id when calling this method. """
        assert self.stripe_customer_id is not None, "Must have customer_id when clearing card."
        # Delete the customer via the Stripe API.
        stripe_gateway.delete_customer(self.stripe_customer_id)
        # Clear all the Stripe customer data from the shop model and database row.
        self.stripe_customer_id = None
        self.stripe_customer_data = None
        self.stripe_has_saved_card = 0
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'shop/update_users_shop_stripe', user_id=self.user.user_id,
                stripe_customer_id=self.stripe_customer_id, stripe_customer_data=self.stripe_customer_data)
            self.send_chips(ctx, self.user)

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'stripe_purchase_products':urls.shop_stripe_purchase_products(),
                'stripe_remove_saved_card':urls.shop_stripe_remove_saved_card()
            }
        return struct

    ## Lazy load attribute methods.
    def _load_user_invoices(self):
        return invoice_module.load_all_invoices_for_user(self.ctx, self.user)

    ## Lazy load collection methods.
    def _load_available_products(self):
        products = []
        for product_key in product_module.all_product_definitions():
            if product_module.is_product_available(product_key, self.user):
                products.append(product_module.AvailableProduct(product_key=product_key, user=self.user))
        return products

    def _load_purchased_products(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'shop/select_purchased_products_by_user_id', user_id=self.user.user_id)
        return rows

class AvailableProductCollection(chips.Collection):
    model_class = product_module.AvailableProduct

    def available_and_price_prepare_refresh(self):
        """
        Call this before making any gamestate changes which might show up when available_and_price_refresh
        is called. e.g. a purchase which would change the available or the price values of an available product.
        This forces all of the available products to be lazy loaded and get their 'current' available
        and price values so any changes can be tracked and chips sent.
        """
        len(self)

    def available_and_price_refresh(self):
        """
        Call this after making any gamestate changes which might change the availability or price
        value of an available product. e.g. a purchase was made.
        NOTE: Be sure to call available_and_price_prepare_refresh before making any of the
        relevant gamestate changes so that all available products have been lazy loaded and any changes
        can be tracked and chips sent.
        """
        # Copy the values as elements might be deleted/made not available during the iteration.
        for p in self.values():
            p.available_and_price_refresh()

class PurchasedProductCollection(chips.Collection):
    model_class = product_module.PurchasedProduct

    def by_product_key(self, product_key):
        """
        Return all the PurchasedProducts of the given product_key type.
        Returns empty list if no product matches.
        """
        assert product_module.is_known_product_key(product_key)
        return [p for p in self.itervalues() if p.product_key == product_key]

    def has_product_key(self, product_key):
        """ Return True if the given product_key has been purchased at least once. """
        purchased = self.by_product_key(product_key)
        return len(purchased) > 0
