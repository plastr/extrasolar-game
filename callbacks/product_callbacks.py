# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import gift_types
from front.lib import db, money, utils
from front.data import validate_dict
from front.models import voucher as voucher_module
from front.models import gift as gift_module
from front.models import invite as invite_module

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def product_is_available(cls, product_key, user, can_repurchase, cannot_purchase_after):
        """
        A callback which returns whether the given product_key should be available in the shop.
        If True is returned, the product_key will be added to available_products as an AvailableProduct instance.
        :param product_key: The product_key of the product.
        :param user: The User who this product would be for.
        :param can_repurchase: bool, whether this product can be purchased more than once, from the product definition.
        :param cannot_purchase_after: set, list of product_keys which cannot be purchased with or after this product,
            from the product definition.
        NOTE: If overriding this method in a product specific callback subclass, it is recommended to call this
        baseclass implementation if appropriate.
        e.g. return BaseCallbacks.product_is_available(product_key, user, can_repurchase)
        """
        # If the product cannot be purchased after a product that has already been purchased,
        # then it should not be available for purchased.
        for p_key in cannot_purchase_after:
            if user.shop.purchased_products.has_product_key(p_key):
                return False

        # If this product can be repurchased, then it is still available.
        if can_repurchase:
            return True

        purchased = user.shop.purchased_products.by_product_key(product_key)
        # Otherwise, if the product has not been purchased at all, it is available.
        if len(purchased) == 0:
            return True
        # Else the product has been purchased and cannot be repurchased so it is no longer available.
        else:
            return False

    @classmethod
    def product_current_price(cls, product_key, user, initial_price, currency):
        """
        A callback which returns the current price, in pennies, for this product. The price may change for example
        based on other products purchased (discounted for instance) or other criteria.
        Returns an integer.
        :param product_key: The product_key of the product.
        :param user: The User who this product would be for.
        :param initial_price: int, the initial_price for this product, from the product definition.
        :param currency: str, the currency for this product, e.g. 'USD'.
        """
        return initial_price

    @classmethod
    def can_purchase_product_with(cls, product, user, product_keys):
        """
        A callback which validates that the given product is allowed to be purchased at this moment.
        This is a failsafe, the client and/or available vs purchased products should never present products
        to the user which they are not permitted to purchase at this moment.
        Returns True or False, and if False, an error message (which could be put into an exception).
        :param product: The AvailableProduct about to be purchased.
        :param user: The User who this product would be for.
        :param product_keys: list, the list of all product keys being purchased with this product, including itself.
        """
        # Verify any non-repurchasable products in the list appear only once.
        if not product.can_repurchase():
            if product_keys.count(product.product_key) != 1:
                return False, "Non-repurchasable products can only be purchased once %s [%s]" %\
                    (product.product_key, user.user_id)

        # Verify that if this product cannot be purchased after another product has been purchased, that
        # that product has not been purchased and is not being purchased with this product.
        for p_key in product.cannot_purchase_after:
            if p_key in product_keys or user.shop.purchased_products.has_product_key(p_key):
                return False, "An attempt was made to purchase a product that cannot be purchased with or\
                     after another product [%s][%s]" % (product.product_key, p_key)

        return True, None

    @classmethod
    def validate_product_specifics(cls, ctx, user, product, product_specifics):
        """
        A callback which is called before a product is purchased to validate any product_specifics data which
        will be used to deliver the product after purchase. This callback might modify the product_specifics values
        to make them valid if it can, otherwise it will return None and an error indicating invalid data.
        Returns the product_specifics dictionary, possibly modified if valid, otherwise returns None and
        a user facing error message.
        :param ctx: The database context.
        :param user: The User who purchased the product.
        :param product: The PurchasedProduct which was just purchased.
        :param product_specifics: dict Any product_specifics data used to deliver this product. The contents are
            product specific and subclasses should implement product specific code.
        """
        return product_specifics, None

    @classmethod
    def product_was_purchased(cls, ctx, user, product, **product_specifics):
        """
        A callback which is called after a product has been purchased. Can be used to deliver any resulting
        game objects or similar, e.g. a voucher.
        Returns nothing.
        :param ctx: The database context.
        :param user: The User who purchased the product.
        :param product: The PurchasedProduct which was just purchased.
        :param product_specifics: dict All other keyword arguments will be passed through to the product_was_purchased
            for this particular product as the specific data used to deliver whatever this product purchases. It is
            intended that on specific BaseCallbacks subclasses the required arguments will be listed by name
            and **product_specifics will not be defined as a catch-all. This provides a runtime check that all
            required arguments were passed through.
        """
        return

class VoucherPass(BaseCallbacks):
    NO_OVERRIDE = ['product_is_available', 'product_was_purchased']
    REQUIRED_NOT_NONE = ['VOUCHER_KEY']

    # Set this to the VCH_ key string that this specific subclass should deliver on purchase.
    VOUCHER_KEY = None

    @classmethod
    def product_is_available(cls, product_key, user, can_repurchase, cannot_purchase_after):
        # If the voucher that is delivered for this product is already owned by the user, for instance if it was
        # already delivered via a gift, or is otherwise not available (e.g. ALL superseeds S1), then this product
        # is no longer available.
        if not voucher_module.is_voucher_key_available(cls.VOUCHER_KEY, user):
            return False
        # Otherwise perform the usual base class behavior.
        else:
            return BaseCallbacks.product_is_available(product_key, user, can_repurchase, cannot_purchase_after)

    @classmethod
    def product_was_purchased(cls, ctx, user, product):
        with db.conn(ctx) as ctx:
            voucher_module.deliver_new_voucher(ctx, user, cls.VOUCHER_KEY)

class GiftVoucher(BaseCallbacks):
    NO_OVERRIDE = ['validate_product_specifics', 'product_was_purchased']
    REQUIRED_NOT_NONE = ['GIFT_TYPE']

    # Set this to the GFT_ type string that this specific subclass should deliver on purchase.
    GIFT_TYPE = None

    @classmethod
    def validate_product_specifics(cls, ctx, user, product, product_specifics):
        # Validate all of the required fields for the invite are present.
        product_specifics, error = validate_dict(product_specifics, required={
            'send_invite': bool,
            'recipient_email': unicode,
            'recipient_first_name': unicode,
            'recipient_last_name': unicode,
            'recipient_message': unicode
        })
        if product_specifics is None:
            return None, error

        if product_specifics['send_invite'] != True:
            return None, utils.tr("Expected send_invite to be true.")

        params, error = invite_module.validate_invite_params(user,
            product_specifics['recipient_email'], product_specifics['recipient_first_name'],
            product_specifics['recipient_last_name'], product_specifics['recipient_message'], attaching_gift=True)
        # If the invite data is invalid, return the error.
        if params is None:
            return None, error

        # Replace any invite fields in the product_specifics with the potentially modified
        # values from the invite validation function.
        product_specifics.update(params)
        return product_specifics, None

    @classmethod
    def product_was_purchased(cls, ctx, user, product, send_invite,
                              recipient_email, recipient_first_name, recipient_last_name, recipient_message):
        assert send_invite == True

        # Create the gift and pass that to the new invitation.
        gift = gift_module.create_new_gift(ctx, user, cls.GIFT_TYPE, 'Invite from: %s' % user.user_id)

        # Create the new invitation and send an email to the recipient with the attached gift.
        invite_module.create_new_invite(ctx, user, recipient_email, recipient_first_name,
                                        recipient_last_name, recipient_message, gift=gift)


## Pass products
class SKU_S1_PASS_Callbacks(VoucherPass):
    VOUCHER_KEY = 'VCH_S1_PASS'

class SKU_ALL_PASS_Callbacks(VoucherPass):
    VOUCHER_KEY = 'VCH_ALL_PASS'

    @classmethod
    def product_current_price(cls, product_key, user, initial_price, currency):
        # If the S1 pass has already been purchased, then the ALL pass is discounted by 75% of the price
        # of the S1 pass at the time the player purchased it, crediting them the money they have already spent.
        purchased = user.shop.purchased_products.by_product_key('SKU_S1_PASS')
        assert len(purchased) < 2
        if len(purchased) == 1:
            initial_money = money.from_amount_and_currency(initial_price, currency)
            discounted_price = money.discount_from_credit_up_to_dime(initial_money, purchased[0].money, 75)
            return money.to_pennies(discounted_price)
        else:
            return initial_price

## Gift voucher products
class SKU_S1_PASS_GIFT_Callbacks(GiftVoucher):
    GIFT_TYPE = gift_types.GFT_S1_PASS

class SKU_ALL_PASS_GIFT_Callbacks(GiftVoucher):
    GIFT_TYPE = gift_types.GFT_ALL_PASS
