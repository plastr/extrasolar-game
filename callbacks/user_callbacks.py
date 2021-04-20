# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.

from front import InitialMessages
from front.lib import utils, email_module
from front.backend import deferred
from front.models import rover, target, mission, message, progress, achievement

# Locations for the first rover and lander for a new user.
LANDER01_START = {'lat':6.24062620105185, 'lng':-109.4144723535118}

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def user_created(cls, ctx, user, send_validation_email):
        """
        A callback which is called when the user just after the user is first created.
        Additional, game specific setup is expected to occur in this callback.
        :param ctx: The database context.
        :param user: The User who was just created.
        :param send_validation_email: Whether a validation email is expected to be sent for this user.
            Only set to False in debugging/test situations.
        """
        # Create a lander to be associated with the rover.
        lander = rover.create_new_lander(ctx, **LANDER01_START)

        # Create the first lander and rover for this user.
        activated_at = utils.in_seconds(hours=0)
        r = rover.create_new_rover(ctx, user, lander, rover_key='RVR_S1_INITIAL', activated_at=activated_at, active=1)

        # The rover starts at the lander location and then moves a small distance so create targets
        # for these locations.
        target.create_new_target(ctx, r,
            start_time=activated_at, arrival_time=utils.in_seconds(hours=0),
            lat=lander['lat'], lng=lander['lng'],
            yaw=0.0, picture=0, processed=1)

        # Add the initial simulator mission and submissions.
        mission.add_mission(ctx, user, 'MIS_SIMULATOR')

        # Deliver the welcome message.
        message.send_now(ctx, user, 'MSG_WELCOME')

        # Add a progress key that the user was created.
        progress.create_new_progress(ctx, user, progress.names.PRO_USER_CREATED)

        # Start with 5 free invitations.
        user.increment_invites_left(5)

        # User created achieved.
        achievement.award_new_achievement(ctx, user, 'ACH_GAME_CREATE_USER')

        # If requested, create the email validation code entry and send the validation email.
        if send_validation_email:
            # XRI: We're over capacity.
            email_module.send_now(ctx, user, "EMAIL_CAPACITY")
            # Kryptex: Back door.
            email_module.send_later(ctx, user, 'EMAIL_VERIFY', utils.in_seconds(minutes=InitialMessages.EMAIL_VERIFY_DELAY_MINUTES))
            # 22 hours later, send another email if the user still isn't verified.
            deferred.run_on_timer(ctx, 'TMR_EMAIL_VERIFY02', user, utils.in_seconds(hours=InitialMessages.EMAIL_VERIFY02_DELAY_HOURS))

    @classmethod
    def user_validated(cls, ctx, user):
        """
        A callback which is called when the user is validated.
        :param ctx: The database context.
        :param user: The User who was just validated.
        """
        # Send an email: Welcome. Credentials verified.
        email_module.send_later(user.ctx, user, 'EMAIL_WELCOME', 
            utils.in_seconds(minutes=InitialMessages.EMAIL_WELCOME_DELAY_MINUTES))

    @classmethod
    def user_accepted_invite(cls, ctx, recipient, invite):
        """
        A callback which is called when a user was created in response to an invitation.
        :param ctx: The database context.
        :param recipient: The User who accepted the invite.
        :param invite: The Invite which was accepted.
        """
        pass

    @classmethod
    def user_created_invite(cls, ctx, sender, invite, recipient_message):
        """
        A callback which is called when the user creates an invitation.
        :param ctx: The database context.
        :param sender: The User who created the invite.
        :param invite: The Invite which was created. Note that the Invite might have an optional Gift
            object attached available in an invite.gift field which can be None.
        :param recipient_message: The string message meant to be seen be the invited person.
        """
        template_data = {
            'sender': sender,
            'invite': invite,
            'recipient_message': recipient_message
        }

        # Send an email: You have been invited.
        email_module.send_now_to_address(ctx, invite.recipient_email, 'EMAIL_INVITE', template_data=template_data)

        # User sent invitation achieved. Will only award this for first invitation.
        achievement.award_new_achievement(ctx, sender, 'ACH_SOCIAL_INVITE')

    @classmethod
    def user_current_voucher_level(cls, ctx, user):
        """
        A callback which is called when determining the user's lazy current_voucher_level field.
        Returns the voucher_key for the current voucher level (the voucher that grants the most).
        """
        # If there are no vouchers there is no voucher current level.
        if len(user.vouchers) == 0:
            return None

        # If there is one voucher, then that must be the current level.
        if len(user.vouchers) == 1:
            return user.vouchers.keys()[0]

        # Determine if a voucher is a candidate for the current level. If any voucher in its list of
        # not_available_after keys is present in the user's vouchers collection then it is rejected,
        # otherwise it is a candidate.
        def is_candidate(v):
            for v_key in v.not_available_after:
                if v_key in user.vouchers:
                    return False
            return True
        candidates = [v for v in user.vouchers.itervalues() if is_candidate(v)]
        assert len(candidates) == 1, "Cannot select a current voucher level if > 1 candidate based on not_available_after."
        return candidates[0].voucher_key
