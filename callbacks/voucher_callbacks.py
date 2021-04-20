# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import utils
from front.models import message as message_module

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def voucher_was_delivered(cls, ctx, user, voucher):
        """
        A callback which is called after a voucher is delivered to a user.
        Returns nothing.
        :param ctx: The database context.
        :param user: The User who purchased the voucher.
        :param voucher: The Voucher which was just delivered.
        """
        return

class VoucherMessage(BaseCallbacks):
    NO_OVERRIDE = ['voucher_was_delivered']
    REQUIRED_NOT_NONE = ['MSG_TYPE']

    # Set this to the MSG_ key string that this specific subclass should send to the user on delivery.
    MSG_TYPE = None

    @classmethod
    def voucher_was_delivered(cls, ctx, user, voucher):
        # Send a message with info about newly acquired capabilities.
        message_module.send_now(ctx, user, cls.MSG_TYPE)

class VCH_S1_PASS_Callbacks(VoucherMessage):
    MSG_TYPE = 'MSG_DELIVER_VCH_S1_PASS'

class VCH_ALL_PASS_Callbacks(VoucherMessage):
    MSG_TYPE = 'MSG_DELIVER_VCH_ALL_PASS'
