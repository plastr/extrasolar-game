# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import db, utils
from front.models import voucher as voucher_module

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def can_user_redeem_gift(cls, redeemer, gift):
        """
        Validate that the given user can redeem this gift.
        If a the gift cannot be redeemed by this user False and a user facing error message will be returned
        otherwise True and None will be returned.
        """
        return True, None

    @classmethod
    def gift_was_redeemed(cls, ctx, creator, redeemer, gift):
        """
        A callback which is called after a gift has been redeemed. Can be used to deliver any resulting
        game objects or similar, e.g. a voucher.
        Returns nothing.
        :param ctx: The database context.
        :param creator: The User who created the gift.
        :param redeemer: The User who redeemed the gift.
        :param gift: The Gift which was just redeemed. Note that this Gift object comes from the
            creator.gifts_created collection so gift.user == creator.
        """
        return

    @classmethod
    def gift_name(cls, gift):
        """
        A callback which returns the string name for this gift, which is meant to be user facing.
        This is a gift_type specific value, e.g. it could be the voucher name for a VoucherGift.
        Must be overriden in subclasses.
        """
        # Return a string in a subclass.
        raise NotImplementedError

    @classmethod
    def gift_description(cls, gift):
        """
        A callback which returns the string name for this gift, which is meant to be user facing.
        This is a gift_type specific value, e.g. it could be the voucher name for a VoucherGift.
        Must be overriden in subclasses.
        """
        # Return a string in a subclass.
        raise NotImplementedError

class VoucherGifts(BaseCallbacks):
    NO_OVERRIDE = ['gift_was_redeemed']
    REQUIRED_NOT_NONE = ['VOUCHER_KEY']

    # Set this to the VCH_ type string that this specific subclass should deliver on redemption.
    VOUCHER_KEY = None

    @classmethod
    def can_user_redeem_gift(cls, redeemer, gift):
        # If the voucher that is delivered for this gift is already owned by the user, for instance if it was
        # already delivered via a gift, or is otherwise not available (e.g. ALL superseeds S1), then this gift
        # cannot be redeemed by this user.
        if not voucher_module.is_voucher_key_available(cls.VOUCHER_KEY, redeemer):
            return False, utils.tr("You cannot redeem this gift. You have already been granted all of the access it offers.")
        return True, None

    @classmethod
    def gift_was_redeemed(cls, ctx, creator, redeemer, gift):
        with db.conn(ctx) as ctx:
            voucher_module.deliver_new_voucher(ctx, redeemer, cls.VOUCHER_KEY)

    @classmethod
    def gift_name(cls, gift):
        voucher_def = voucher_module.get_voucher_definition(cls.VOUCHER_KEY)
        return voucher_def['name']

    @classmethod
    def gift_description(cls, gift):
        voucher_def = voucher_module.get_voucher_definition(cls.VOUCHER_KEY)
        return voucher_def['description']

class GFT_S1_PASS_Callbacks(VoucherGifts):
    VOUCHER_KEY = "VCH_S1_PASS"

class GFT_ALL_PASS_Callbacks(VoucherGifts):
    VOUCHER_KEY = "VCH_ALL_PASS"

class GFT_NO_PASS_Callbacks(BaseCallbacks):
    @classmethod
    def gift_name(cls, gift):
        return "Early Access"

    @classmethod
    def gift_description(cls, gift):
        return "An invitation to participate in the closed beta."
