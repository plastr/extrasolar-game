# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

from front.lib import utils
from front.models import progress, mission
from front.models import message as message_module
from front.models import rover as rover_module
from front.models import target as target_module
from front.models import achievement as achievement_module
from front.callbacks import mission_callbacks

import logging
logger = logging.getLogger(__name__)

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def should_deliver(cls, ctx, user):
        """
        A callback which is called just before a message has been delivered to a user.
        If False is returned, then the message will not be delivered to this user. The primary
        purpose of this callback is to allow a delayed message to check the gamestate one last time
        before deciding if its time to delivery a message or for delivering a message to all users in
        a migration.
        :param ctx: The database context.
        :param user: The User to whom this message might be delivered.
        """
        return True

    @classmethod
    def was_delivered(cls, ctx, user, message):
        """
        A callback which is called when a message has been delivered to a user.
        :param ctx: The database context.
        :param user: The User to whom this message was delivered.
        :param message: The Message which was delivered.
        """
        return

    @classmethod
    def was_read(cls, ctx, user, message):
        """
        A callback which is called when a message has been marked read.
        :param ctx: The database context.
        :param user: The User to whom this message was sent.
        :param message: The Message which was read.
        """
        return

    @classmethod
    def was_unlocked(cls, ctx, user, message):
        """
        A callback which is called when a message has been successfully unlocked.
        :param ctx: The database context.
        :param user: The User to whom this message was unlocked.
        :param message: The Message which was unlocked.
        """
        return

    @classmethod
    def forwarded_to(cls, ctx, user, message, recipient):
        """
        A callback which is called when a user attempts to forward a message.
        :param ctx: The database context.
        :param user: The User to whom this message was sent.
        :param message: The Message being forwarded.
        :param recipient: str The recipient name the user is attempting to forward to.
        Override this method if a certain message type is expected to be forwarded.
        """
        # The default behavior of this system is to send a few messages to the user
        # the first time they try and forward letting them know now is not the right time.
        # Override this method if a certain message type is expected to be forwarded.
        if recipient == 'KRYPTEX':
            # The first time you forward something to Kryptex, send a "no need for that" message.
            if not user.messages.has_been_queued_or_delivered('MSG_NO_FORWARD_TO_KRYPTEX'):
                message_module.send_later(ctx, user, 'MSG_NO_FORWARD_TO_KRYPTEX', utils.in_seconds(minutes=5))
        else:
            if not user.messages.has_been_queued_or_delivered('MSG_NO_FORWARDa'):
                message_module.send_later(ctx, user, 'MSG_NO_FORWARDa', utils.in_seconds(minutes=5))
            elif not user.messages.has_been_queued_or_delivered('MSG_NO_FORWARDb'):
                message_module.send_later(ctx, user, 'MSG_NO_FORWARDb', utils.in_seconds(minutes=5))
            # If both message forwarding hints have been sent, do nothing.
        return

## Message event callback definitions.
class MSG_JANE_INTRO_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Add a mission to tag 5 species.
        mission.add_mission(ctx, user, "MIS_SPECIES_FIND_5")
        return

class MSG_ARTIFACT01a_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Turing: Tag the artifact.
        mission.add_mission(ctx, user, 'MIS_ARTIFACT01')

class MSG_ARTIFACT01d_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Kryptex: Get another photo.
        mission.add_mission(ctx, user, 'MIS_ARTIFACT01_CLOSEUP')

class MSG_ARTIFACT01g_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Add a progress key to unlock the sandbox
        progress.create_new_progress(ctx, user, progress.names.PRO_SANDBOX_SAFETY_DISABLED)
        # Add a mission to leave the sandbox and issue the RGN_SANDBOX_SAFE region chips.
        mission.add_mission(ctx, user, "MIS_EXPLORE_ISLAND")
        return

class MSG_FOUND_ROVER01a_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Mission from XRI to send the player further inland.
        # Movement in that direction should kick off AUDIO_TUTORIAL01 and AUDIO_MYSTERY01.
        mission.add_mission(ctx, user, 'MIS_VISIT_CENTRAL_PLATEAU')
        return

class MSG_INVITATIONSa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Add invitations
        user.increment_invites_left(5)

class MSG_MISSION02a_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # T: Go photograph the EM source near the AGPS unit.
        mission.add_mission(ctx, user, 'MIS_FIND_EM_SOURCE')
        # Add a progress key to show the GPS unit.  This region is not mission-critical, so we
        # add it with a progress key rather than listing it in the mission's region_list_not_done.
        progress.create_new_progress(ctx, user, progress.names.PRO_SHOW_GPS_REGION)

class MSG_GPSa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # It's super unlikely that this could happen, but it may be possible for the player
        # to unlock MSG_ENCRYPTION01 in the brief time window before this message is sent.
        # If that happens, log a warning, but don't create the mission.
        if user.messages.by_type('MSG_ENCRYPTION01').is_locked():
            # K: Get the password from the AGPS unit.
            mission.add_mission(ctx, user, 'MIS_FIND_GPS_UNIT')
        else:
            # If this happens, we expect that the warning in MSG_ENCRYPTION01.was_unlocked has already been triggered.
            logger.warning("MSG_ENCRYPTION01 was already unlocked when MSG_GPSa was delivered. [%s]", user.user_id)

class MSG_ENCRYPTION01_Callbacks(BaseCallbacks):
    @classmethod
    def was_unlocked(cls, ctx, user, message):
        # Using the password completes the second half of mission MIS_FIND_GPS_UNITb.
        # It's super unlikely but theoretically possible that the player could find the GPS unit
        # and unlock the message before receiving the hint mission from Kryptex.
        mis = user.missions.get_only_by_definition("MIS_FIND_GPS_UNITb")
        if mis is not None:
            mis.mark_done()
        else:
            # If this happens, we expect that the warning from MSG_GPSa.was_delivered will be triggered next.
            logger.warning("MSG_ENCRYPTION01 was unlocked before MIS_FIND_GPS_UNITb was assigned. [%s]", user.user_id)
        # If all conditions are met, unlock access to the ruins.
        mission_callbacks.enable_access_to_ruins(ctx, user)
        # Message from Kryptex: About my father.
        message_module.send_later(ctx, user, 'MSG_GPSc', utils.in_seconds(minutes=30))
        # Message from Kryptex: More encrypted docs.
        message_module.send_later(ctx, user, 'MSG_ENCRYPTION02', utils.in_seconds(hours=6))
        # If MIS_FIND_EM_SOURCE is also done, kick off the next message/mission from Turing.
        if user.missions.get_only_by_definition('MIS_FIND_EM_SOURCE').is_done():
            # Message from Turing: Head toward ruins.
            message_module.send_later(ctx, user, 'MSG_GO_TO_RUINS', utils.in_seconds(minutes=45))

class MSG_GO_TO_RUINS_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # T: Visit ruins.
        mission.add_mission(ctx, user, 'MIS_VISIT_RUINS')

class MSG_RUINSa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # T: More photos please.
        mission.add_mission(ctx, user, 'MIS_PHOTOGRAPH_RUINS')

class MSG_RUINSc_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Replace prior mission (Photogaph ruins) with another (Photograph at signal source).
        mission.add_mission(ctx, user, 'MIS_RUINS_SIGNAL_SOURCE')

class MSG_RUINSe_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Unless the player already where the 2 remaining obelisks are,
        # Add a mission to explore other parts of the island.
        if user.missions.get_only_by_definition('MIS_EXPLORE_ISLAND02') is None:
            # T: Explore other parts of the island.
            mission.add_mission(ctx, user, 'MIS_EXPLORE_ISLAND02')

class MSG_OBELISK04a_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Mark the generic "go explore" mission as done and replace it with a more explicit mission
        # with all expected obelisk locations.
        explore_mission = user.missions.get_only_by_definition('MIS_EXPLORE_ISLAND02')
        if explore_mission is not None:
            explore_mission.mark_done()
        # If obelisks 4 and 5 were tagged in rapid succession, then we never need to add MIS_2_MORE_OBELISKS.
        if mission_callbacks.get_done_obelisk_mission_count(user) == 4:
            # T: Photograph all obelisks
            mission.add_mission(ctx, user, 'MIS_2_MORE_OBELISKS')

class MSG_OBELISK04c_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # K: go to coded location
        mission.add_mission(ctx, user, 'MIS_CODED_LOC')

# Note that this message is never sent if the player figures it out on their own.
class MSG_LANDMARKS01_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Add a progress key to display landmarks that will later be used to locate Turing's rover.
        progress.create_new_progress(ctx, user, progress.names.PRO_SHOW_LANDMARKS01)

# Note that this message is never sent if the player figures it out on their own.
class MSG_CODED_LOCb_Callbacks(BaseCallbacks):
    @classmethod
    def should_deliver(self, ctx, user):
        # If the player figured out how to unlock the encrypted message on their own, the hint isn't needed.
        return user.messages.by_type('MSG_ENCRYPTION02').is_locked()

    @classmethod
    def was_delivered(self, ctx, user, message):
        # K: use the unit name as the password
        mission.add_mission(ctx, user, 'MIS_CODED_LOC_PASSWORD')

class MSG_ENCRYPTION02_Callbacks(BaseCallbacks):
    @classmethod
    def was_unlocked(cls, ctx, user, message):
        # Mark the optional hint mission as done.
        search_mission = user.missions.get_only_by_definition('MIS_CODED_LOC')
        hint_mission   = user.missions.get_only_by_definition('MIS_CODED_LOC_PASSWORD')
        if search_mission == None and hint_mission == None:
            # Amazingly, the player found the GPS unit and used it to unlock the doc with no assistance.
            # We need to short-circuit everything that would be triggered by MIS_CODED_LOC.
            # K: edna is a middleman! (unbelievable!)
            message_module.send_later(ctx, user, 'MSG_CODED_LOCc_v3', utils.in_seconds(minutes=5))
        elif hint_mission != None:
            hint_mission.mark_done()
            # K: edna is a middleman! (hint was given)
            message_module.send_later(ctx, user, 'MSG_CODED_LOCc_v2', utils.in_seconds(minutes=5))
        else:
            # K: edna is a middleman! (no hint was required)
            message_module.send_later(ctx, user, 'MSG_CODED_LOCc_v1', utils.in_seconds(minutes=5))
        # K: video from dad.
        message_module.send_later(ctx, user, 'MSG_RICHARD01a', utils.in_seconds(minutes=30))
        # K: they killed dad.
        message_module.send_later(ctx, user, 'MSG_RICHARD01c', utils.in_seconds(hours=2))

    @classmethod
    def forwarded_to(cls, ctx, user, message, recipient):
        # Check status of the MIS_SEND_TO_ENKI mission to ensure this doesn't happen more than once.
        if recipient == 'ENKI':
            if not user.missions.get_only_by_definition("MIS_SEND_TO_ENKI").is_done():
                user.missions.get_only_by_definition("MIS_SEND_TO_ENKI").mark_done()
                # Enki: Calling Arling now.
                message_module.send_later(ctx, user, 'MSG_ENKI02b', utils.in_seconds(minutes=30))
        # If the recipient is not ENKI, perform the default behavior which is Kryptex telling
        # the player not to forward things willy-nilly.
        else:
            BaseCallbacks.forwarded_to(ctx, user, message, recipient)

class MSG_ENKI02a_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(cls, ctx, user, message):
        # Add a progress key to enabled forwarding messages to enki.
        progress.create_new_progress(ctx, user, progress.names.PRO_ENABLE_FWD_TO_EXOLEAKS)
        # K: fwd docs to enki
        mission.add_mission(ctx, user, 'MIS_SEND_TO_ENKI')

class MSG_ENKI02d_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(cls, ctx, user, message):
        # K: find turing's rover. it's the password i need.
        mission.add_mission(ctx, user, 'MIS_FIND_TURING_ROVER')

    @classmethod
    def was_unlocked(cls, ctx, user, message):
        # Mark the "find turing's rover" mission as done.
        msn = user.missions.get_only_by_definition('MIS_FIND_TURING_ROVER')
        if msn is not None:
            msn.mark_done()
        # K: i'm back!  Slightly different message version if all obelisks have been tagged.
        if mission_callbacks.get_done_obelisk_mission_count(user) < 6:
            message_module.send_later(ctx, user, 'MSG_BACKa_v1', utils.in_seconds(minutes=1))
        else:
            message_module.send_later(ctx, user, 'MSG_BACKa_v2', utils.in_seconds(minutes=1))

class MSG_BACKb_Callbacks(BaseCallbacks):
    @classmethod
    def was_unlocked(cls, ctx, user, message):
        # Add a mission to find all 6 obelisks and playback the tone sequence.
        mission.add_mission(ctx, user, 'MIS_MONUMENT_PLAYBACK')
        # If the player has tagged obelisks 5 and/or 6, send messages that have been blocked until now.
        mission_callbacks.send_obelisk_messages(ctx, user, mission_callbacks.get_done_obelisk_mission_count(user))

class MSG_OBELISK06b_Callbacks(BaseCallbacks):
    @classmethod
    def was_unlocked(cls, ctx, user, message):
        # K: it's over.
        message_module.send_later(ctx, user, 'MSG_OBELISK06d', utils.in_seconds(minutes=1))
        # T: Not much time. Play this at central monument.
        message_module.send_later(ctx, user, 'MSG_MISSION04a', utils.in_seconds(minutes=2))

class MSG_MISSION04c_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # T: Find a rover with lost connectivity.
        mission.add_mission(ctx, user, 'MIS_FIND_LOST_ROVER')

class MSG_LASTTHINGa_Callbacks(BaseCallbacks):
    @classmethod
    def was_unlocked(cls, ctx, user, message):
        # Mark the related mission as done.
        user.missions.get_only_by_definition('MIS_UNLOCK_LAST_DOC').mark_done()
        # K: going to find my father.
        message_module.send_later(ctx, user, 'MSG_RICHARD02b', utils.in_seconds(minutes=5))
        # T: Thank you.
        message_module.send_later(ctx, user, 'MSG_END', utils.in_seconds(minutes=10))
        # T: Patience. Link to credits.
        message_module.send_later(ctx, user, 'MSG_S1_CREDITS', utils.in_seconds(minutes=20))
        # Anonymous: Call between Arling and Cavendish.
        message_module.send_later(ctx, user, 'MSG_AUDIO_TEASE', utils.in_seconds(days=6.9))

class MSG_S1_CREDITS_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Add invitations
        user.increment_invites_left(5)

class MSG_END_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Make sure this user has at least 1 inactive rover.
        inactive_rovers = user.rovers.inactive()
        assert len(inactive_rovers) > 0

        # Issue a new rover with the same lander as the first rover.
        lander = inactive_rovers[0].lander
        epoch_now = user.epoch_now
        activated_at = epoch_now - utils.in_seconds(hours=3)
        r = rover_module.create_new_rover(ctx, user, lander=lander, rover_key='RVR_S1_FINAL', activated_at=activated_at, active=1)
        # The rover starts at the lander location and then moves a small distance so create targets
        # for these locations.
        target_module.create_new_target(ctx, r,
            start_time=activated_at,
            arrival_time=epoch_now - utils.in_seconds(hours=2),
            lat=lander['lat'], lng=lander['lng'], yaw=0.0, picture=0, processed=1)

# ======== SCIENCE MISSIONS ========

class MSG_SCI_PHOTOSYNTHESISa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Find 10 species.
        mission.add_mission(ctx, user, 'MIS_SPECIES_FIND_10')

class MSG_SCI_PHOTOSYNTHESISc_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Find these 3 presumed-common species
        mission.add_mission(ctx, user, 'MIS_SCI_FIND_COMMON')

class MSG_SCI_PHOTOSYNTHESISh_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: We will not experiment on the aircomber.
        user.missions.get_only_by_definition("MIS_SCI_FIND_COMMONc").mark_done()

class MSG_FIND_10_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Find 15 unique species.
        mission.add_mission(ctx, user, 'MIS_SPECIES_FIND_15')

class MSG_SCI_CELLULARa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Find 3 gordy trees.
        mission.add_mission(ctx, user, 'MIS_SCI_CELLULARa')

class MSG_SCI_CELLULARc_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Find all 3 life stages of the gordy tree
        mission.add_mission(ctx, user, 'MIS_SCI_LIFECYCLE')

class MSG_SCI_VARIATIONa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Track down the bristletongue variant
        mission.add_mission(ctx, user, 'MIS_SCI_VARIATION')

class MSG_SCI_FLOWERSa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Tag open and closed starspore "flowers"
        mission.add_mission(ctx, user, 'MIS_SCI_FLOWERS')

class MSG_SCI_BIOLUMINESCENCEa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Tag all 3 bioluminescent colors.
        mission.add_mission(ctx, user, 'MIS_SCI_BIOLUMINESCENCE')

class MSG_SCI_FLIGHTa_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Jane: Tag 3 sail flyers.
        mission.add_mission(ctx, user, 'MIS_SCI_FLIGHT')

# ======== ACHIEVEMENT MESSAGES ========

class MSG_ACH_SPECIES_TAG_3_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Mark the achievement as achieved.
        achievement_module.award_new_achievement(ctx, user, 'ACH_SPECIES_TAG_3')

class MSG_ACH_SPECIES_ANIMAL_5_Callbacks(BaseCallbacks):
    @classmethod
    def was_delivered(self, ctx, user, message):
        # Mark the achievement as achieved.
        achievement_module.award_new_achievement(ctx, user, 'ACH_SPECIES_ANIMAL_5')

class MSG_ACH_PHOTO_HIGHLIGHT_Callbacks(BaseCallbacks):
    @classmethod
    def should_deliver(cls, ctx, user):
        # Only deliver this message if the player has at least 1 highlighted arrived at photo.
        # We do this check here in case the player's photo has been un-highlighted.
        for target in user.rovers.iter_processed_pictures(newest_first=True):
            if target.is_highlighted():
                return True
        return False

    @classmethod
    def was_delivered(self, ctx, user, message):
        # User's target was highlighted: badge achieved. Will only award this for first highlight.
        achievement_module.award_new_achievement(ctx, user, 'ACH_PHOTO_HIGHLIGHT')
