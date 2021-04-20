# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import utils, email_module

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def invoice_was_paid(cls, ctx, user, invoice):
        """
        A callback which is called after an invoice has been paid.
        Returns nothing.
        :param ctx: The database context.
        :param user: The User who paid the invoice.
        :param invoice: The Invoice which was just paid.
        """
        template_data = {
            'invoice': invoice
        }
        email_module.send_now(ctx, user, "EMAIL_PURCHASE_RECEIPT", template_data=template_data)
