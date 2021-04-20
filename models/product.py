# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
import uuid
import pkg_resources

from front import models
from front.lib import get_uuid, db, gametime, money
from front.data import load_json, schemas
from front.models import chips
from front.callbacks import run_callback, PRODUCT_CB

# The path relative to this package where the product data is stored.
PRODUCT_DEFINITIONS = pkg_resources.resource_filename('front', 'data/product_definitions.json')

class BaseProduct(chips.Model, models.UserChild):
    @property
    def shop(self):
        # self.parent is shop.products, the parent of that is the shop itself
        return self.parent.parent

    @property
    def user(self):
        return self.shop.parent

    def can_repurchase(self):
        return self.repurchaseable == 1

class AvailableProduct(BaseProduct):
    """
    Holds the parameters for a single available product in the shop catalog.
    """
    id_field = 'product_key'
    # All of these fields come from the product definitions JSON file.
    fields = frozenset(['name', 'description', 'price', 'currency', 'price_display', 'initial_price', 'initial_price_display',
                        'icon', 'sort', 'repurchaseable', 'cannot_purchase_after'])
    price_display = chips.LazyField("price_display", lambda m: m._load_price_display())

    def __init__(self, product_key, user):
        definition = get_product_definition(product_key)
        params = {}
        for field in self.fields:
            if field in ['price_display', 'initial_price_display']:
                continue
            if field == 'price':
                value = _available_product_current_price(product_key, user, definition['initial_price'], definition['currency'])
            else:
                value = definition[field]
            params[field] = value

        super(AvailableProduct, self).__init__(product_key=product_key, **params)

    @property
    def money(self):
        """ Return a Money object representing the price and currency of this product. """
        return money.from_amount_and_currency(self.price, self.currency)

    @property
    def initial_price_display(self):
        """ Return a string representing the initial price for display to a user. """
        return money.format_money(money.from_amount_and_currency(self.initial_price, self.currency))

    def record_purchased_by_invoice(self, invoice, product_specifics):
        """ Record that this AvailableProduct has been purchased, by creating and persisting a
            PurchasedProduct. """
        purchased = PurchasedProduct.create_from_available_product(self, invoice, product_specifics, self.user)
        # Now that this product has been purchased, it is possible its availablity or price has changed,
        # for instance if it is a product that can only be purchased once, so check to see if those
        # need to be refresh and chips sent.
        self.available_and_price_refresh()
        return purchased

    def can_purchase_with(self, product_keys):
        """ Returns True if this product can be purchased with the given list of product_keys, False otherwise.
            See product_callbacks for full documentation and implementations. """
        return run_callback(PRODUCT_CB, "can_purchase_product_with", self.product_key, product=self,
            user=self.user, product_keys=product_keys)

    def validate_product_specifics(self, product_specifics):
        """ Validate the given product_specifics for this product. Returns the product_specifics dict which might
            have been modified by the validation code or None and an error message if the data was invalid. """
        return run_callback(PRODUCT_CB, "validate_product_specifics", self.product_key, ctx=self.ctx, user=self.user,
                            product=self, product_specifics=product_specifics)

    def available_and_price_refresh(self):
        """
        If this product is no longer available or its price has changed (as determined by callbacks) then
        update the instance values and issue a chip. This method must be called whenever a gamestate change occurs
        which might affect the availability or price values of a product, e.g. a product was purchased.
        """
        # If the product is currently in the available products but no longer available, then issue the DELETE chip.
        is_available = self in self.user.shop.available_products
        current_available = is_product_available(self.product_key, self.user)
        if is_available and not current_available:
            self.delete()
            with db.conn(self.ctx) as ctx:
                self.send_chips(ctx, self.user)
        # There's no point checking to see if the price changed as this product is not available.
        if not current_available:
            return
        # If the price has changed, then issue a MOD chip.
        current_price = _available_product_current_price(self.product_key, self.user, self.initial_price, self.currency)
        if current_price != self.price:
            self.price = current_price
            # Update the price_display value as well as it will have changed.
            self.price_display = self._load_price_display()
        with db.conn(self.ctx) as ctx:
            self.send_chips(ctx, self.user)

    ## Lazy load attribute methods.
    def _load_price_display(self):
        return money.format_money(self.money)

class PurchasedProduct(BaseProduct):
    """
    Holds the parameters for a single purchased product.
    """
    id_field = 'product_id'
    fields = frozenset(['product_key', 'name', 'description', 'price', 'currency', 'price_display', 'icon', 'sort',
                        'repurchaseable', 'purchased_at', 'cannot_purchase_after', 'invoice_id'])
    computed_fields = {
        'purchased_at_date': models.EpochDatetimeField('purchased_at')
    }
    server_only_fields = frozenset(['invoice_id'])

    # user_id and created are a database only fields.
    def __init__(self, product_id, invoice_id, product_key, price, currency, purchased_at, user_id=None, created=None):
        product_id = get_uuid(product_id)
        invoice_id = get_uuid(invoice_id)
        definition = get_product_definition(product_key)
        # These fields are not stored in the database.
        definition_params = {
            'name':                  definition['name'],
            'description':           definition['description'],
            'icon':                  definition['icon'],
            'sort':                  definition['sort'],
            'repurchaseable':        definition['repurchaseable'],
            'cannot_purchase_after': definition['cannot_purchase_after']
        }
        super(PurchasedProduct, self).__init__(product_id=product_id, product_key=product_key,
                                               price=price, currency=currency, purchased_at=purchased_at,
                                               invoice_id=invoice_id, **definition_params)

    @classmethod
    def create_from_available_product(cls, available_product, invoice, product_specifics, user):
        params = {}
        params['product_id']   = uuid.uuid1()
        params['product_key']  = available_product.product_key
        params['price']        = available_product.price
        params['currency']     = available_product.currency
        params['purchased_at'] = user.epoch_now
        params['invoice_id']   = invoice.invoice_id

        with db.conn(user.ctx) as ctx:
            created = gametime.now()
            db.run(ctx, "shop/insert_purchased_product", user_id=user.user_id, created=created, **params)
            purchased = user.shop.purchased_products.create_child(**params)
            purchased.send_chips(ctx, user)
            # Inform the callbacks that this product was purchased.
            run_callback(PRODUCT_CB, "product_was_purchased", purchased.product_key, ctx=ctx, user=user,
                         product=purchased, **product_specifics)
        return purchased

    @property
    def money(self):
        """ Return a Money object representing the price and currency of this product. """
        return money.from_amount_and_currency(self.price, self.currency)

    @property
    def price_display(self):
        """ Return a string representing the price for display to a user. """
        return money.format_money(self.money)

def is_product_available(product_key, user):
    can_repurchase = bool(get_product_definition(product_key)['repurchaseable'])
    cannot_purchase_after = get_product_definition(product_key)['cannot_purchase_after']
    return run_callback(PRODUCT_CB, "product_is_available", product_key, product_key=product_key,
        user=user, can_repurchase=can_repurchase, cannot_purchase_after=cannot_purchase_after)

def is_known_product_key(product_key):
    """ Returns True if the given product_key was defined in the product definitions. """
    return product_key in all_product_definitions()

def _available_product_current_price(product_key, user, initial_price, currency):
    return run_callback(PRODUCT_CB, "product_current_price", product_key, product_key=product_key,
        user=user, initial_price=initial_price, currency=currency)

def get_product_definition(product_key):
    """
    Return the product definition as a dictionary for the given product key.

    :param product_key: str key for this product definition e.g PRD_*. Defined in
    product_definitions.json
    """
    return all_product_definitions()[product_key]

def all_product_definitions():
    """ Return the product definitions as loaded from the JSON data file. """
    return _g_product_definitions

_g_product_definitions = None
def init_module():
    global _g_product_definitions
    if _g_product_definitions is not None: return

    _g_product_definitions = load_json(PRODUCT_DEFINITIONS, schema=schemas.PRODUCT_DEFINITIONS)
    # Verify every product_key listed in cannot_purchase_after is known/valid and is unique.
    # Also, a given product_key cannot appear in its own cannot_purchase_after list.
    for product_key, definition in _g_product_definitions.iteritems():
        cannot_purchase_after = definition['cannot_purchase_after']
        for p_key in cannot_purchase_after:
            if not p_key in _g_product_definitions:
                raise Exception("product_key is not known in product definition cannot_purchase_after [%s][%s]" % (product_key, p_key))
            if cannot_purchase_after.count(p_key) > 1:
                raise Exception("Duplicate product_key in product definition cannot_purchase_after [%s][%s]" % (product_key, p_key))
            if p_key == product_key:
                raise Exception("product_key cannot appear in its own product definition cannot_purchase_after [%s][%s]" % (product_key, p_key))
        # Convert the JSON list into a Python set.
        definition['cannot_purchase_after'] = set(cannot_purchase_after)
