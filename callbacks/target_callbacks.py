# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

from front import Constants
from front.lib import utils, geometry
from front.data import audio_regions
from front.models import mission as mission_module
from front.models import message as message_module
from front.models import capability as capability_module

import logging
logger = logging.getLogger(__name__)

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass
    NO_OVERRIDE = ['validate_new_target_params', 'target_deleted']

    @classmethod
    def validate_new_target_params(cls, ctx, user, rover, arrival_delta, target_id, params):
        """
        A callback which is called while a target is being created to validate client provided
        data and constrain it as needed.
        If a constraint is violated where the data can be fudged to make it valid, a warning will be
        logged and the data will be fudged. If an unfudgeable constraint is violated, then an error
        will be logged, no target will be created, and None will be returned from this function.
        :param ctx: The database context.
        :param user: The User who is creating this target.
        :param rover: The Rover that will own this target.
        :param arrival_delta: int The number of seconds the client is requesting from 'now' that this
            target should be arrived at. This is just a request from the client, the server may constrain
            this value when computing the true arrival_time for various reasons.
        :param target_id: The UUID that will be used for this Target's target_id if it is allowed to be created.
        :param params: dict The remaining client Target parameters. See target.create_new_target for details.
        """
        # The rover creating this target must be active.
        if not rover.is_active():
            logger.error("Refusing to create target for inactive rover. [%s]", rover.rover_id)
            # Return None indicating an unrecoverable error.
            return None

        # Enforce the maximum number of unarrived at targets per user.
        # Include the target about to be created in the count of unarrived at targets.
        max_unarrived_targets = rover.max_unarrived_targets
        unarrived_at_count = len(rover.targets.unarrived_at()) + 1
        if unarrived_at_count > max_unarrived_targets:
            logger.error("Player exceeded max unarrived at targets %d > %d [%s]",
                unarrived_at_count, max_unarrived_targets, user.user_id)
            # Return None indicating an unrecoverable error.
            return None

        # Default start_time to now.
        params['start_time'] = user.epoch_now
        # arrival_delta is the number of seconds from "now" that the client is requesting that
        # this new target will arrive at. 6 hours = 21600, 12 hours = 43200 etc.
        params['arrival_time'] = user.epoch_now + arrival_delta

        # start_time is the later of now or the latest arrival_time which would happen if there
        # are targets which have not been arrived at yet.
        last_target = rover.targets.last()
        if last_target and last_target.arrival_time > params['start_time']:
            params['start_time'] = last_target.arrival_time

        # Enforce a minimum time between 'start_time' and 'arrival_time'.
        min_target_seconds = rover.min_target_seconds - Constants.TARGET_SECONDS_GRACE
        min_arrival_time = params['start_time'] + utils.in_seconds(seconds=min_target_seconds)
        if (params['arrival_time'] < min_arrival_time):
            logger.warn("Target arrival_time %s too early, modifying to %s [%s]",
                        params['arrival_time'], min_arrival_time, target_id)
            params['arrival_time'] = min_arrival_time

        # Enforce a maximum time between 'start_time' and 'arrival_time'.
        max_target_seconds = rover.max_target_seconds + Constants.TARGET_SECONDS_GRACE
        max_arrival_time = params['start_time'] + utils.in_seconds(seconds=max_target_seconds)
        if (params['arrival_time'] > max_arrival_time):
            logger.warn("Target arrival_time %s too late, modifying to %s [%s]",
                        params['arrival_time'], max_arrival_time, target_id)
            params['arrival_time'] = max_arrival_time

        # Make sure we haven't traveled too far.
        max_travel_distance = rover.max_travel_distance + Constants.TRAVEL_DISTANCE_GRACE
        dist = geometry.dist_between_lat_lng(params['lat'], params['lng'], last_target.lat, last_target.lng);
        if (dist > max_travel_distance):
            logger.warn("Player exceeded travel limit, %f > %f, last_target=%r, target_id=%s, lat/lng=%f/%f",
                        dist, max_travel_distance, last_target, target_id, params['lat'], params['lng'])
            # Clip the path from A to B at the distance limit.
            params['lat'], params['lng'] = geometry.clip_path([params['lat'], params['lng']],
                                                              [last_target.lat, last_target.lng],
                                                              max_travel_distance/dist)

        # Make sure the target position doesn't violate any of the region constraints.
        for region in user.regions.itervalues():
            if region.restrict == 'INSIDE' and not region.point_inside(params['lat'], params['lng']):
                logger.error("Target must be inside region %s [%s]", region, user.user_id)
                return None
            elif region.restrict == 'OUTSIDE' and region.point_inside(params['lat'], params['lng']):
                logger.error("Target must be outside region %s [%s]", region, user.user_id)
                return None

        # For every requested rover feature to enable for this target (as passed via
        # the target metadata) and that is listed in any rover_features field in the capability definitions,
        # verify any required capabilities are available and have uses left.
        # If they are not available or have uses, remove that feature request from the metadata and log an error.
        # NOTE: Need to copy the keys into a new list as the metadata dictionary might have keys removed during iteration.
        for rover_feature in (f for f in params['metadata'].keys() if f in capability_module.all_rover_features()):
            if rover.can_use_feature(rover_feature):
                rover.use_feature(rover_feature)
            else:
                logger.error("Rover feature %s requires capability which has no uses left or is not available, disabling." % rover_feature)
                del params['metadata'][rover_feature]

        # Panorama and infrared options are mutually-exclusive.
        if 'TGT_FEATURE_PANORAMA' in params['metadata'] and 'TGT_FEATURE_INFRARED' in params['metadata']:
            logger.warn("Panorama and infrared features set together on target [%s], disabling infrared.", target_id)
            del params['metadata']['TGT_FEATURE_INFRARED']

        # Finally, every not done mission gets a chance to validate the target parameters, either to
        # change them to be correct or to return False, indicating that the target cannot be created.
        for m in user.missions.not_done():
            valid = m.validate_new_target_params_callback(rover, arrival_delta, params)
            if not valid:
                logger.error("Mission reports target parameters invalid, cannot create target. [%s][%s][%s]" % (m, rover, params))
                # Return None indicating an unrecoverable error.
                return None

        return params

    @classmethod
    def target_can_abort_until(cls, target_id, params):
        """
        A callback which is called when a Target is constructed to set the 'can_abort_until' value for the target.
        Returns either an epoch delta time (an integer) which is the deadline past which a target cannot be aborted
        or None, indicating this target can never be aborted.
        :param target_id: The UUID that will be used for this Target's target_id if it is allowed to be created.
        :param params: dict The remaining client Target parameters. See target.create_new_target for details.
        """
        # If the target is not a picture or was not user created, then it is not abort-able, return None to indicate.
        if params['picture'] == 0 or params['user_created'] == 0:
            return None
        # Otherwise a target can be aborted up until its start time minus the target data leeway.
        return params['start_time'] - Constants.TARGET_DATA_LEEWAY_SECONDS

    @classmethod
    def target_created(cls, ctx, user, target):
        """
        A callback which is called whenever a target is created.
        :param ctx: The database context.
        :param user: The User who owns this target.
        :param target: The Target that was created.
        """
        return

    @classmethod
    def target_will_be_deleted(cls, ctx, user, target):
        """
        A callback which is called whenever a target is deleted.
        :param ctx: The database context.
        :param user: The User who owned this target.
        :param target: The Target that was deleted.
        """
        # For every rover feature that was enabled/used by this target being deleted (as passed via
        # the target metadata) and that is listed in any rover_features field in the capability definitions,
        # decrement its uses count to both free up any free uses and keep an accurate count of the number of uses.
        for rover_feature in (f for f in target.metadata.iterkeys() if f in capability_module.all_rover_features()):
            if target.rover.can_reuse_feature(rover_feature):
                target.rover.reuse_feature(rover_feature)
            else:
                logger.warn("No available capabilities when trying to reuse rover feature [%s][%s]",
                            rover_feature, target.user.capabilities)
    @classmethod
    def target_en_route(cls, ctx, user, target):
        """
        A callback which is called when a rover has begun to move towards the given target.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param target: The Target which the user's rover has begun to move towards.
        """
        return

    @classmethod
    def arrived_at_target(cls, ctx, user, target):
        """
        A callback which is called when a rover has arrived at the given target.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param target: The Target which the user's rover has arrived at.
        """
        return

    @classmethod
    def target_was_highlighted(cls, ctx, user, target):
        """
        A callback which is called when a target was highlighted by an admin.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param target: The Target which was highlighted.
        """
        # User's target was highlighted achieved. Will only award this for first highlight.
        if not user.messages.has_been_queued_or_delivered('MSG_ACH_PHOTO_HIGHLIGHT'):
            if target.has_been_arrived_at():
                message_module.send_now(ctx, user, 'MSG_ACH_PHOTO_HIGHLIGHT')
            else:
                # If the user hasn't arrived at the target yet, delay the message and badge
                # to coincide with the arrival time plus a little extra leeway.
                delay = target.arrival_time - user.epoch_now + utils.in_seconds(minutes=1)
                message_module.send_later(ctx, user, 'MSG_ACH_PHOTO_HIGHLIGHT', delay)

class TARGET_AUDIO_DETECT_MISSION_Callbacks(BaseCallbacks):
    @classmethod
    def arrived_at_target(cls, ctx, user, target):
        # Now that the rover has arrived at the target which appeared to traverse at least one
        # active audio region when it was created, enumerate all of the active audio regions it
        # did in fact pass through and create their initial missions.
        for audio_region in audio_regions.active_audio_regions_traversed_by_target(target):
            # If the mission for this audio region hasn't already been added for this user, add it now.
            if user.missions.get_only_by_definition(audio_region.mission_definition) is None:
                mission_module.add_mission(ctx, user, audio_region.mission_definition, target=target)
        return

## MessageSequence callbacks. Special target callbacks which are designed to send a sequence
# of messages using any target creation as the trigger to send the next messages.
# This class assumes all MSG_TYPES will be sent in a linear order. Multiple messages can be sent
# at the same time, but always in the expected sequence.
class MessageSequence(BaseCallbacks):
    REQUIRED_NOT_NONE = ['MSG_TYPES']

    # Should be a list of msg_type strings.
    MSG_TYPES = None

    class MessageHandler(object):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            """
            A callback which is called when the given msg_type that implements a subclass of this
            class is the NEXT unsent message. Will only be called once if this function sends
            a message for the given msg_type.
            This method is only called if the given msg_type is unsent.
            NOTE: More than one of the next msg_types in the sequence can be sent at the same time,
            so long as they are sent in the correct order.
            :param ctx: The database context.
            :param user: The User who owns this target.
            :param target: The Target that was created which triggered this event.
            :param msg_tye: str, The msg_type string for this unsent message.
            :param delivered_or_queued: list, The list of msg_type strings in MSG_TYPES that have already been
                delivered or queued for delivery.
            :param unsent: list, The list of msg_type strings in MSG_TYPES not yet sent, including this msg_type.
            """
            return

    @classmethod
    def arrived_at_target(cls, ctx, user, target):
        if len(cls.MSG_TYPES) == 0:
            raise Exception("Must define at least one msg_type in MSG_TYPES when using MessageSequence")
        # If the last msg_type in the sequence has been delivered then do nothing.
        # the sequence is complete.
        # NOTE This will lazy load the messages but does not yet touch the deferreds so it is a
        # small shortcircut to cut off running the rest of the code if the sequence is done.
        if user.messages.by_type(cls.MSG_TYPES[-1]) is not None:
            return

        # If the first msg_type in the sequence, which is acting as a sentinal to start the sequence,
        # is not in the gamestate or queued to be delivered, do nothing.
        if not user.messages.has_been_queued_or_delivered(cls.MSG_TYPES[0]):
            return

        # If the last msg_type in the sequence has been or is queued to be delivered then do nothing,
        # the sequence is complete.
        if user.messages.has_been_queued_or_delivered(cls.MSG_TYPES[-1]):
            return

        # Determine which msg_types have been queued or sent already and which ones
        # have not yet been sent.
        # We know the first MSG_TYPE has been sent or queued at this point.
        delivered_or_queued = [cls.MSG_TYPES[0]]
        unsent = []
        first_unsent = None
        # We can skip the first MSG_TYPE as we know it has been sent or queued at this point.
        for index, msg_type in enumerate(cls.MSG_TYPES[1:]):
            if user.messages.has_been_queued_or_delivered(msg_type):
                delivered_or_queued.append(msg_type)
            else:
                # Now that we have found the first unsent, store it and slice the MSG_TYPES
                # array for the remaining elements and assume they are also unsent.
                first_unsent = msg_type
                unsent = cls.MSG_TYPES[index + 1:]
                break

        # If there was a first unsent msg, dispatch the callback to the inner class handler if
        # implemented, otherwise do nothing.
        if first_unsent is not None:
            try:
                handler_class = getattr(cls, first_unsent)
            # If there is no handler, do nothing.
            except AttributeError:
                return

        # Don't handle the first_unsent message until all queued messages have been delivered.
        if user.messages.by_type(delivered_or_queued[-1]) is not None:
            # Perform the handler call down here so that the exception handler above doesn't hide
            # key/attribute errors in this code.
            handler_class.handle_unsent_message(ctx, user, target, first_unsent, delivered_or_queued, unsent)

# Message sequence for a number of docs sent by Kryptex about the origin of EDNA.
class EDNA01_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_ENCRYPTION02', 'MSG_PHONE03a', 'MSG_EDNA01', 'MSG_EDNA02', 'MSG_EDNA04']

    class MSG_PHONE03a(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: Leaked call, Arling, Turing, Cavendish
            message_module.send_later(ctx, user, 'MSG_PHONE03a', utils.in_seconds(minutes=2))
            # K: Doc about EDNA
            message_module.send_later(ctx, user, 'MSG_EDNA01', utils.in_seconds(minutes=15))
    
    class MSG_EDNA02(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: More docs
            message_module.send_later(ctx, user, 'MSG_EDNA02', utils.in_seconds(minutes=2))

    class MSG_EDNA04(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: More docs
            message_module.send_later(ctx, user, 'MSG_EDNA04', utils.in_seconds(minutes=2))

# Message sequence for a number of docs sent by Kryptex about the origin of EDNA.
class EDNA02_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_ENKI01a', 'MSG_EDNA05', 'MSG_EDNA08', 'MSG_ENKI01c']
    
    class MSG_EDNA05(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: more docs, who is edna?
            message_module.send_later(ctx, user, 'MSG_EDNA05', utils.in_seconds(minutes=2))

    class MSG_EDNA08(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: more docs, no response from enki
            message_module.send_later(ctx, user, 'MSG_EDNA08', utils.in_seconds(minutes=2))

    class MSG_ENKI01c(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: calling enki
            message_module.send_later(ctx, user, 'MSG_ENKI01c', utils.in_seconds(minutes=2))

# Message sequence for sending a hint if the player doesn't figure out to use the unit designation as a password.
# Note that MSG_RICHARD01a isn't actually sent by this handler, but once it's been sent,
# we know for certain this sequence can be ignored.
class CODED_LOC_HINT_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_CODED_LOCa', 'MSG_CODED_LOCb', 'MSG_RICHARD01a']
    
    class MSG_CODED_LOCb(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # Is the hint needed?
            if user.messages.by_type('MSG_ENCRYPTION02').is_locked():
                # K: maybe the item is the password.
                message_module.send_later(ctx, user, 'MSG_CODED_LOCb', utils.in_seconds(minutes=1))

# Same as above, but the hint is triggered by a different message.  This is the sequence that happens
# if the player tags the GPS unit before they get the coded location, but they don't figure out to
# use the GPS2 unit name as the password for MSG_ENCRYPTION02.
class CODED_LOC_HINT_v2_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_OBELISK04c_v3', 'MSG_CODED_LOCb', 'MSG_RICHARD01a']
    
    class MSG_CODED_LOCb(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # Is the hint needed?
            if user.messages.by_type('MSG_ENCRYPTION02').is_locked():
                # K: maybe the item is the password.
                message_module.send_later(ctx, user, 'MSG_CODED_LOCb', utils.in_seconds(minutes=1))

# Message sequence at the start of the Kryptex lockout.
class LOCKOUT01_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_RICHARD01c', 'MSG_SECURITY', 'MSG_ENKI02a']
    
    class MSG_SECURITY(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # T: plugging security holes.
            message_module.send_later(ctx, user, 'MSG_SECURITY', utils.in_seconds(minutes=2))
            # K: get docs to enki.
            message_module.send_later(ctx, user, 'MSG_ENKI02a', utils.in_seconds(minutes=15))

# Message sequence during Kryptex lockout.
class LOCKOUT02_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_ENKI02b', 'MSG_ENKI02d']
    
    class MSG_ENKI02d(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: turing's rover is the password i need.
            message_module.send_later(ctx, user, 'MSG_ENKI02d', utils.in_seconds(minutes=2))

# Message sequence when Kryptex gets back into the system.
# Note that there are 2 nearly identical versions of this class because there are 2 versions of MSG_BACKa
class KRYPTEX_BACKv1_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_BACKa_v1', 'MSG_BACKb']
    
    class MSG_BACKb(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # T: K intercepts call.
            message_module.send_later(ctx, user, 'MSG_BACKb', utils.in_seconds(minutes=2))

class KRYPTEX_BACKv2_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_BACKa_v2', 'MSG_BACKb']
    
    class MSG_BACKb(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # T: K intercepts call.
            message_module.send_later(ctx, user, 'MSG_BACKb', utils.in_seconds(minutes=2))

# Message sequence during Kryptex lockout.
class HURRY_Callbacks(MessageSequence):
    MSG_TYPES = ['MSG_LASTTHINGb', 'MSG_LASTTHINGc']
    
    class MSG_LASTTHINGc(MessageSequence.MessageHandler):
        @classmethod
        def handle_unsent_message(cls, ctx, user, target, msg_type, delivered_or_queued, unsent):
            # K: hurry!
            message_module.send_later(ctx, user, 'MSG_LASTTHINGc', utils.in_seconds(minutes=1))
