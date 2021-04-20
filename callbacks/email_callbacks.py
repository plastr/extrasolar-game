# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

import time
from front.lib import utils

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def should_send(cls, ctx, user):
        """
        A callback which is called just before an email will be sent to a user.
        If True and a context dictionary are returned, the email will be sent with the provided context merged
        into the email template rendering.
        If False is returned, then the message will not be delivered to this user. Any context is ignored.
        :param ctx: The database context.
        :param user: The User to whom this message might be delivered.
        """
        return True, {}

    @classmethod
    def was_sent_or_queued(cls, ctx, user, email_message):
        """
        A callback which is called when aan email has been sent or queued, if the email_queue is enabled.
        :param ctx: The database context.
        :param user: The User to whom this email was sent.
        :param email_message: The EmailMessage instance which was sent.
        """
        return

# This helper function chooses a random excerpt from Jane to include in the lure email.
# TODO: Can we move these strings into email_types.yaml?
def random_lure_body():
    message_bodies = [
    utils.tr("<p>I just wanted to send you a quick message to make sure you haven't forgotten about us here\
        at XRI.  We rely on citizen scientists like you to assist us in the amazing scientific discoveries\
        we're making on Epsilon Prime.  I hope you understand what a privilege it is to be part of our team.</p>"),
    utils.tr("<p>I haven't seen you login to Extrasolar in a while, so I assume you must be quite busy.\
        As I'm sure you understand, groundbreaking scientific discoveries aren't going to happen on their own!</p>"),
    utils.tr("<p>I noticed that you haven't logged in for a few days, so I wanted to send a friendly reminder\
        that you have a few tasks that may need some attention. Thanks for everything you've done for our team!</p>")
    ]
    random_index = int(time.time()) % 3
    return message_bodies[random_index]

# Verification emails should only be sent if the player hasn't already validated their account.
class EMAIL_VERIFY_Callbacks(BaseCallbacks):
    @classmethod
    def should_send(cls, ctx, user):
        return (not user.valid), {}

class EMAIL_VERIFY02_Callbacks(BaseCallbacks):
    @classmethod
    def should_send(cls, ctx, user):
        return (not user.valid), {}

class EMAIL_LURE_ALERT_Callbacks(BaseCallbacks):
    @classmethod
    def should_send(cls, ctx, user):
        # Randomly select a message for the body and return it to the template.
        return True, {'custom_body':random_lure_body()}
