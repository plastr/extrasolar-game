# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.

from front.lib import utils, email_module
from front.models import message as message_module

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def timer_arrived_at(cls, ctx, user):
        """
        A callback which is called when a given timer has expired and been arrived at.
        """
        return

class TMR_EMAIL_VERIFY02_Callbacks(BaseCallbacks):
    @classmethod
    def timer_arrived_at(cls, ctx, user):
        # If the player hasn't clicked the backdoor link, send a second email.
        if not user.valid:
            # Kryptex: Here's the backdoor link... again.
            email_module.send_now(ctx, user, "EMAIL_VERIFY02")

class TMR_MSG_OBELISK04c_Callbacks(BaseCallbacks):
    @classmethod
    def timer_arrived_at(cls, ctx, user):
        # Send the appropriate version of the MSG_OBELISK04c message depending on whether the
        # player has (a) found the GPS unit at the coded location, and (b) already used
        # it to unlock MSG_ENCRYPTION02
        # Check if the player managed to unlock the video from Noam with no assistance.
        msg_encrypted = user.messages.by_type('MSG_ENCRYPTION02')
        msg_is_locked = (msg_encrypted is None or msg_encrypted.is_locked())
        gps_was_tagged = user.species.target_count_for_key('SPC_MANMADE006') > 0

        if msg_is_locked and not gps_was_tagged:
            # K: code signifies a location
            message_module.send_now(ctx, user, 'MSG_OBELISK04c')
        elif msg_is_locked:
            # Bypass creation of MIS_CODED_LOC, but short-circuit the stuff that would
            # normally be triggered by its completion.
            # K: code signifies where you found that gps unit.  But why is that important?
            message_module.send_now(ctx, user, 'MSG_OBELISK04c_v3')
        else:
            # Bypass creation of MIS_CODED_LOC, but short-circuit the stuff that would
            # normally be triggered by its completion.
            # K: code signifies where you found that gps unit.
            message_module.send_now(ctx, user, 'MSG_OBELISK04c_v2')
