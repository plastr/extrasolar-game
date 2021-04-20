# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import math

from front import subspecies_types
from front.backend import deferred
from front.lib import db, geometry, utils
from front.data import scene
from front.models import species, message, region, progress, RegionPack
from front.models import mission as mission_module
from front.models import rover as rover_module
from front.models import target as target_module

import logging
logger = logging.getLogger(__name__)

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass
    NO_OVERRIDE = ['region_list']

    @classmethod
    def create_specifics(cls, ctx, user, **kwargs):
        """
        A callback which is called when a mission instance is created to do any init time setup in the
        mission code. Returns a dict which will be persisted into the database as the mission "specifics".
        :param ctx: The database context.
        :param user: The User who will own this mission.
        :param kwargs: dict All other keyword arguments will be passed through to the create_specifics
            for this mission. These might be useful when creating the mission specifics. It is intended
            that on specific BaseCallbacks subclasses the required arguments will be listed by name
            and **kwargs will not be defined as a catch-all. This provides a runtime check that all
            required arguments were passed through when creating the mission.
        """
        return {}

    @classmethod
    def create_parts(cls, mission):
        """
        A callback which is called when a mission instance is created to provide a list of any child
        missions, or 'parts', that are part of this parent mission and should be created at the same time
        that it is created.
        Returns a list of mission definition strings, or an empty list.
        """
        return []

    @classmethod
    def region_list_not_done(cls, mission):
        """
        A callback which returns any Regions that should be available in this User's current gamestate,
        after this Mission has been added to the gamestate but not marked done.
        See mission_callbacks.region_list for a full description of the return value.
        """
        return []

    @classmethod
    def region_list_done(cls, mission):
        """
        A callback which returns any Regions that should be available in this User's current gamestate,
        after this Mission has been marked done.
        See mission_callbacks.region_list for a full description of the return value.
        """
        return []

    @classmethod
    def was_created(cls, ctx, user, mission):
        """
        A callback which is called just after a mission is created and added to the user's mission list.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param mission: The Mission which has triggered this callback.
        """
        return

    @classmethod
    def marked_done(cls, ctx, user, mission):
        """
        A callback which is called just after a mission is marked done.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param mission: The Mission which has triggered this callback.
        """
        return

    @classmethod
    def validate_new_target_params(cls, user, mission, rover, arrival_delta, params):
        """
        A callback which is called when a target is being created giving any not done mission a chance to
        validate the new targets parameters. This callback can return True indicating the target creation
        can proceed, or False, meaning the target parameters are invalid. Optionally, this callback
        could also return True and change the values in the params dictionary to make the target
        be valid, if such change is possible given the gamestate and target data.
        NOTE: Values in params might already have been manipulated by early steps in the validation process.
        :param user: The User who owns this mission.
        :param mission: The Mission which was not done and triggered for this callback.
        :param rover: The Rover creating the target.
        :param arrival_delta, params: These are the target parameters sent by the client.
            See target.create_new_target for a full description of all of the values.
        """
        return True

    @classmethod
    def target_created(cls, ctx, user, mission, target):
        """
        A callback which is called on each mission which is not done whenever a target is created.
        If True is returned, the mission is marked done.
        If None is returned, the callback is responsible for managing mark_done itself.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param mission: The Mission which has triggered this callback.
        :param target: The target that was created.
        """
        return False

    @classmethod
    def target_en_route(cls, ctx, user, mission, target):
        """
        A callback which is called when a rover has begun to move towards the given target.
        If True is returned, the mission is marked done.
        If None is returned, the callback is responsible for managing mark_done itself.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param mission: The Mission which has triggered this callback.
        :param target: The Target which the user's rover has begun to move towards.
        """
        return False

    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        """
        A callback which is called when a rover has arrived at the given target.
        If True is returned, the mission is marked done.
        If None is returned, the callback is responsible for managing mark_done itself.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param mission: The Mission which has triggered this callback.
        :param target: The Target which the user's rover has arrived at.
        """
        return False

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        """
        A callback which is called on each mission which is not done whenever a species identification
        occurs. If True is returned, the mission is marked done.
        If None is returned, the callback is responsible for managing mark_done itself.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param mission: The Mission which has triggered this callback.
        :param target: The target where the identification happened.
        :param identified: The Species which was detected/identified.
        :param subspecies: The set of subspecies_ids that were detected/identified (at most 1 currently).
        """
        return False

    ## Do not override these methods, only meant to be called externally.
    @classmethod
    def region_list(cls, mission):
        """
        A callback which returns any Regions this mission would want to made available to the gamestate as
        long as this mission is not done.
        See progress_callbacks.region_list for providing progress key specific regions.
        The return value is a list object, which contains either a tuple mapping between the region_id to add
        to the gamestate and optionally any data to set in that Region when it is constructed, e.g.
        setting the center value of a waypoint based on gamestate data or just the region_id if
        there is no construction data.
        This method is NOT meant to be overriden, use region_list_not_done or region_list_done.
        e.g. [region_id1, (region_id2, {construction_args})]
        NOTE: Currently this code does not allow a region_id returned by this method (provided by this mission)
        to be provided by some other data in the gamestate. In other words, regions returned by a missions
        region_list are assumed to be unique to that mission and can be safely removed from the gamestate
        when the mission is marked done.
        Returns an empty list meaning no regions to add as a default.
        :param mission: The Mission which has triggered this callback.
        """
        if mission.is_done():
            return cls.region_list_done(mission)
        else:
            return cls.region_list_not_done(mission)

## Mission callbacks base classes.
class MissionParent(BaseCallbacks):
    NO_OVERRIDE = ['create_parts', 'marked_done']

    # The mission definitions of the child missions, in the order they will be
    # completed by the user.
    CHILDREN = []

    @classmethod
    def parent_marked_done(cls, ctx, user, mission):
        """
        A callback which is called just after this parent mission is marked done and all children have been
        marked done. If there is custom behavior to perform in this parent during that event, override this method,
        NOT marked_done which has special functionality in MissionParent subclasses.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param mission: The Mission which has triggered this callback.
        """
        return

    ## BaseCallbacks overrides.
    @classmethod
    def create_parts(cls, mission):
        # As a shortcut, allow subclasses to define their children by overriding the CHILDREN list.
        # NOTE: If a subclass overrides this method without calling super, the CHILDREN list is ignored.
        return cls.CHILDREN

    @classmethod
    def marked_done(cls, ctx, user, mission):
        # NOTE: Subclasses should override parent_marked_done instead of overriding this method.
        cls.parent_marked_done(ctx, user, mission)

        # Verify that all of the children have also been marked done.
        for child in mission.parts:
            assert child.is_done()

class MissionChild(BaseCallbacks):
    # Protect create_parts as no good reason for a child to create more children.
    NO_OVERRIDE = ['create_parts']

    @classmethod
    def child_marked_done(cls, ctx, user, mission):
        """
        A callback which is called just after this child mission is marked done. If there is custom behavior
        to perform in this child during that event, override this method, NOT marked_done which has special
        functionality in MissionChild subclasses.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param mission: The Mission which has triggered this callback.
        """
        return

    ## BaseCallbacks overrides.
    @classmethod
    def marked_done(cls, ctx, user, mission):
        # NOTE: Subclasses should override child_marked_done instead of overriding this method.
        cls.child_marked_done(ctx, user, mission)

        # If all siblings are also done, mark the parent as done.
        for sibling in mission.siblings():
            if not sibling.is_done():
                return  # We still have incomplete siblings.  Do nothing.

        # All sibling missions are done.  Mark the parent as done.
        mission.mark_parent_done()

## Serial mission callbacks base classes.  The children of serial missions must be completed in order.
class SerialMissionParent(MissionParent):
    @classmethod
    def active_child(cls, mission):
        """ Returns the child mission which is active, meaning the first not done child in the order defined
            by the parent mission. """
        not_done = [m for m in mission.parts if not m.is_done()]
        if len(not_done) == 0:
            return None
        else:
            return not_done[0]

class SerialMissionChild(MissionChild):
    NO_OVERRIDE = ['region_list_not_done', 'marked_done']

    @classmethod
    def region_list_pre_active(cls, mission):
        """
        A callback which returns any Regions this child mission would want to made available to the gamestate as
        long as this mission is not done AND is not the active mission, meaning the first not done child in the order
        defined by the parent mission. In other words, these are the regions to supploy before this child becomes active.
        See region_list_when_active and region_list_done to provide regions during other mission state.
        See BaseCallbacks.region_list for a complete description of the return value.
        Returns an empty list meaning no regions to add as a default.
        :param mission: The Mission which has triggered this callback.
        """
        return []

    @classmethod
    def region_list_when_active(cls, mission):
        """
        A callback which returns any Regions this child mission would want to made available to the gamestate as
        long as this mission is not done AND is the active mission, meaning the first not done child in the order
        defined by the parent mission.
        NOTE: If SerialMissionChild.region_list is overriden and does not call super, this method has no effect.
        See region_list_pre_active and region_list_done to provide regions during other mission state.
        See BaseCallbacks.region_list for a complete description of the return value.
        Returns an empty list meaning no regions to add as a default.
        :param mission: The Mission which has triggered this callback.
        """
        return []

    @classmethod
    def is_active(cls, mission):
        """ Returns True if this child mission is the 'active' mission for this serial mission set, meaning
            the first not done child in the order defined by the parent mission. """
        # If this is the first child, then it is active if it is not done.
        if mission.previous_step() is None:
            return not mission.is_done()
        # Else this is the active child if the previous child (implying all previous) are done.
        else:
            return mission.previous_step().is_done()

    ## BaseCallbacks overrides.
    @classmethod
    def region_list_not_done(cls, mission):
        # NOTE: Subclasses should override region_list_when_active or region_list_pre_active instead
        # of overriding this method.
        if cls.is_active(mission):
            return cls.region_list_when_active(mission)
        else:
            return cls.region_list_pre_active(mission)

    @classmethod
    def marked_done(cls, ctx, user, mission):
        # NOTE: Subclasses should override child_marked_done instead of overriding this method.
        cls.child_marked_done(ctx, user, mission)

        # Verify that all previous siblings have also been marked done.
        previous_step = mission.previous_step()
        while previous_step is not None:
            if not previous_step.is_done():
                previous_step.mark_done()
            previous_step = previous_step.previous_step()

        # If we are the last child, mark our parent done.
        if mission.next_step() is None:
            mission.mark_parent_done()
            return

        # Issue ADD chips for any regions defined/made available by the next child mission. Some child
        # missions might only want their regions to be available once they are the 'active' step in the
        # serial mission.
        for region_id, constructor_args in mission.next_step().region_list_callback():
            # Only add the region (and issue the ADD chip) if it is not already in the regions collection.
            if region_id not in user.regions:
                region.add_region_to_user(ctx, user, region_id, **constructor_args)

#======== AUDIO MISSIONS ========
# Audio missions tend to have similar structures, so we've created a set of parent classes
# with overridable callback functions to tune behavior.

class AudioMissionParent(SerialMissionParent):
    """ Parent mission callback for finding an audio source. """
    NO_OVERRIDE = ['region_list_done']
    REQUIRED_NOT_NONE = ['REGION_AUDIO_ICON']

    REGION_AUDIO_ICON = None  # The region to show when the mission is complete.

    @classmethod
    def region_list_done(cls, mission):
        # Once the source has been tagged, pinpoint its origin.
        return [cls.REGION_AUDIO_ICON]

class AudioMissionChildEnterZone(SerialMissionChild):
    """ Child mission callback for entering an audio zone to pinpoint an audio source. """
    NO_OVERRIDE = ['region_list_when_active', 'was_created', 'arrived_at_target']
    REQUIRED_NOT_NONE = ['REGION_AUDIO_ZONE', 'MESSAGE_ROVERAUDIO', 'SOUND_DETECTED']

    REGION_AUDIO_ZONE  = None # The zone region to show when the mission is started.
    MESSAGE_ROVERAUDIO = None # The message to send when the mission is triggered.
    SOUND_DETECTED     = None # The sound to append to the target when the zone is entered.

    @classmethod
    def region_list_when_active(cls, mission):
        return [cls.REGION_AUDIO_ZONE]

    @classmethod
    def was_created(cls, ctx, user, mission):
        # Message from rover: Sound detected.
        message.send_now(ctx, user, cls.MESSAGE_ROVERAUDIO)
        # Perform any additional acctions that should be run when the mission is started.
        cls.audio_mission_started(ctx, user, mission)

    @classmethod
    def target_en_route(cls, ctx, user, mission, target):
        zone = user.regions[cls.REGION_AUDIO_ZONE]
        if target.traverses_region(zone) and not target.has_detected_sound(cls.SOUND_DETECTED):
            # Attach the detected sound data to this target.
            target.detected_sound(cls.SOUND_DETECTED)
        return False

    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        zone = user.regions[cls.REGION_AUDIO_ZONE]
        done = target.traverses_region(zone)
        if done:
            # Perform any additional actions that should be run when the rover enters the zone.
            cls.audio_detected(ctx, user, mission, target)
            # Double-check that the sound has been attached to this target. It's improbable but
            # possible that this mission was not active when we started en route to this target.
            if not target.has_detected_sound(cls.SOUND_DETECTED):
                # Attach the detected sound data to this target.
                target.detected_sound(cls.SOUND_DETECTED)
        return done

    @classmethod
    def audio_mission_started(cls, ctx, user, mission):
        """
        If other messages should be sent or queued when this mission is created,
        override this callback.
        """
        return

    @classmethod
    def audio_detected(cls, ctx, user, mission, target):
        """
        If other messages should be sent or queued when this mission is done,
        override this callback.
        """
        return

class AudioMissionChildTagSource(SerialMissionChild):
    """ Child mission callback for tagging an audio source. """
    NO_OVERRIDE = ['region_list_when_active', 'species_identified']
    REQUIRED_NOT_NONE = ['REGION_AUDIO_PINPOINT', 'SOUND_DETECTED', 'MISSION_SIBLING', 'SPECIES_AUDIO_SOURCE']

    REGION_AUDIO_PINPOINT   = None # The region that should be shown when the sound has been pinpointed but not tagged.
    SOUND_DETECTED          = None # The sound to append to the target when the zone is entered.
    MISSION_SIBLING         = None # The corresponding sibiling mission of type AudioMissionChildEnterZone.
    SPECIES_AUDIO_SOURCE    = None # The species that must be tagged to complete this mission.
    SUBSPECIES_AUDIO_SOURCE = None # Optional: If not None, a subspecies set that must match exactly to complete this mission.
    
    @classmethod
    def region_list_when_active(cls, mission):
        # Only show the pinpoint if the previous step (part a) is done.
        return [cls.REGION_AUDIO_PINPOINT]

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        done = (identified.key == cls.SPECIES_AUDIO_SOURCE and (cls.SUBSPECIES_AUDIO_SOURCE == None or cls.SUBSPECIES_AUDIO_SOURCE == subspecies))
        if done:
            # Triple-check that the sound associated with this audio mission gets attached to at
            # least one target. If we never entered the zone, attach the sound to this target.
            if not user.missions.get_only_by_definition(cls.MISSION_SIBLING).is_done() and not target.has_detected_sound(cls.SOUND_DETECTED):
                # Attach the detected sound data to this target.
                target.detected_sound(cls.SOUND_DETECTED)
            # Note: Some of the audio_identified callbacks rely on an accurate count of completed
            # missions. Mark this mission done before the callback to support this behavior.
            mission.mark_done()
            # Perform any additional acctions that should be run when the species has been tagged.
            cls.audio_identified(ctx, user, mission, target, identified, subspecies)
        return None

    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        """
        If other messages should be sent or queued when this mission is done,
        override this callback.
        """
        return

#========

## Simulator mission callback definitions.
class MIS_SIMULATOR_Callbacks(SerialMissionParent):
    CHILDREN = ['MIS_SIMULATORa', 'MIS_SIMULATORb']

## Mission tutorial callback definitions.
class MIS_TUT01_Callbacks(SerialMissionParent):
    CHILDREN = ['MIS_TUT01a', 'MIS_TUT01b']

    @classmethod
    def region_list_not_done(cls, mission):
        # Don't let the player stray too far from the lander until they've tagged it.
        return ['RGN_TAG_LANDER01_CONSTRAINT']

class MIS_TUT01a_Callbacks(SerialMissionChild):
    """ A target mission which is done when the lander has been targeted. """
    @classmethod
    def create_specifics(cls, ctx, user, rover):
        """ rover is a required parameter when creating this mission type with add_mission. """
        # RCJ: I added a hidden marker to the mission specifics.  This prevents the
        # user from dragging their rover directly on top of the lander.
        return {'rover_id':rover.rover_id,
                'distance':15}

    @classmethod
    def region_list_when_active(cls, mission):
        lander = mission.user.rovers[mission.specifics['rover_id']].lander
        lander_region = RegionPack('RGN_LANDER01_WAYPOINT', center=[lander['lat'], lander['lng']])
        return [lander_region]

    @classmethod
    def validate_new_target_params(cls, user, mission, rover, arrival_delta, params):
        # While the TUT01a mission is not done, the only valid target a user can create is one near
        # and pointed at the lander. The client should be enforcing this, so this is just a failsafe.
        assert str(rover.rover_id) == mission.specifics['rover_id']
        return cls._is_target_close_enough_to_lander(mission, rover, params['lat'], params['lng'], params['yaw'])

    @classmethod
    def target_created(cls, ctx, user, mission, target):
        # If the target was pointed at close enough to the lander, then this mission is done.
        rover = user.rovers[mission.specifics['rover_id']]
        return cls._is_target_close_enough_to_lander(mission, rover, target.lat, target.lng, target.yaw)

    @classmethod
    def _is_target_close_enough_to_lander(cls, mission, rover, target_lat, target_lng, target_yaw):
        lander = rover.lander
        lander_lat = lander['lat']
        lander_lng = lander['lng']
        dist = geometry.dist_between_lat_lng(lander_lat, lander_lng, target_lat, target_lng)
        if(dist < mission.specifics['distance']):
            # Within distance
            tangle = math.atan2(lander_lng - target_lng, lander_lat - target_lat);
            if geometry.angle_closeness(tangle, target_yaw, 0.70):
                # Within angle
                return True
        # Neither within distance nor angle
        return False

class MIS_TUT01b_Callbacks(SerialMissionChild):
    """ An identification mission which is done whenever the lander is identified. """
    @classmethod
    def create_specifics(cls, ctx, user, rover):
        """ rover is a required parameter when creating this mission type with add_mission. """
        return {'rover_id':rover.rover_id}

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        # If the species was the lander, then this mission is done.
        done = (identified.key == "SPC_LANDER01")
        if done:
            with db.conn(ctx) as ctx:
                # Send a message describing the artifact finding mission and add the mission for this user.
                message.send_later(ctx, user, 'MSG_ARTIFACT01a', utils.in_seconds(minutes=1))
        return done

## Mission event callback definitions.
class MIS_ARTIFACT01_Callbacks(BaseCallbacks):
    """ An identification mission which is done whenever the first artifact is identified. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_ARTIFACT01_WAYPOINT']

    @classmethod
    def region_list_done(cls, mission):
        return ['RGN_ARTIFACT01_ICON']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        # If the species was the artifact, then this mission is done.
        done = (identified.key == "SPC_ARTIFACT01")
        if done:
            # Message from Kryptex: Take another photo.
            message.send_later(ctx, user, 'MSG_ARTIFACT01d', utils.in_seconds(minutes=1))
            # Message from XRI encouraging you to ignore the artifact.
            message.send_later(ctx, user, 'MSG_ARTIFACT01b', utils.in_seconds(hours=1))
            # Message from Kryptex claiming the artifact is not manmade.
            message.send_later(ctx, user, 'MSG_ARTIFACT01c', utils.in_seconds(hours=1.5))
        return done

class MIS_ARTIFACT01_CLOSEUP_Callbacks(BaseCallbacks):
    """ Kryptex asks the player to take another photo of the ARTIFACT01 """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        # To prevent the player from cheating by tagging the artifact twice in the same photo,
        # we require that the artifact be tagged in at least 2 separate images.
        if user.species.target_count_for_key('SPC_ARTIFACT01') < 2:
            return False
        # If the species was the artifact, then this mission is done.
        done = (identified.key == "SPC_ARTIFACT01")
        if done:
            # Message from Kryptex: That writing is familiar.
            message.send_later(ctx, user, 'MSG_ARTIFACT01e', utils.in_seconds(minutes=1))
            # Message from Turing: Move along now.
            message.send_later(ctx, user, 'MSG_ARTIFACT01f', utils.in_seconds(minutes=3))
            # Message from Kryptex: Leave the sandbox.
            message.send_later(ctx, user, 'MSG_ARTIFACT01g', utils.in_seconds(minutes=5))
        return done

class MIS_EXPLORE_ISLAND_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_SANDBOX_SAFE01', 'RGN_SANDBOX_SAFE02']

    @classmethod
    def target_created(cls, ctx, user, mission, target):
        # If the user has already created the target where it will get stuck, then mark targets
        # that will be neutered. These targets will remain as markers on the map until the rover
        # arrives at the threshold target, at which time we delete all future targets past this point.
        # Note: Neutering a target marks it as processed to make sure that it's never passed to
        # the renderer.
        if (user.has_target_with_metadata_key('TGT_S1_STUCK_IN_DUNES')):
            target.mark_as_neutered()

        # If this target is the first outside of the sandbox, add target metadata to indicate
        # that the rover will be stuck so any additional targets created before the rover arrives
        # at the stuck target will be neutered and not rendered.
        sandbox = region.from_id('RGN_SANDBOX')
        if not target.is_inside_region(sandbox):
            target.add_metadata_unique('TGT_S1_STUCK_IN_DUNES')

        # Will be marked done by the arrived_at_target callback when the rover has become stuck.
        return False

    @classmethod
    def target_en_route(cls, ctx, user, mission, target):
        # If this target is the first outside of the sandbox, send a message from Turing.
        sandbox = region.from_id('RGN_SANDBOX')
        if not target.is_inside_region(sandbox) and not user.messages.has_been_queued_or_delivered('MSG_ROVER_WILL_BE_STUCK'):
            # We duplicate some of the code from target_created to account for the unlikely scenario
            # when this mission was not active when this target was created.
            if target.add_metadata_unique('TGT_S1_STUCK_IN_DUNES') == True:
                logger.warning("Metadata key TGT_S1_STUCK_IN_DUNES was expected but not found [%s, %s]", user.user_id, target.target_id)

            # T: This is bad news.
            message_delay = (target.arrival_time - target.start_time) - utils.in_seconds(minutes=20)
            message.send_later(ctx, user, 'MSG_ROVER_WILL_BE_STUCK', message_delay)

            # Neuter any future targets that have already been scheduled.
            neutered_targets = target.rover.targets.split_on_target(target)[1]
            for neutered in neutered_targets:
                neutered.mark_as_neutered()

        # Will be marked done by the arrived_at_target callback when the rover has become stuck.
        return False

    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        sandbox = region.from_id('RGN_SANDBOX')
        if not target.is_inside_region(sandbox) and not user.messages.has_been_queued_or_delivered('MSG_ROVER_STUCKa'):
            stuck_rover = target.rover

            # Delete any future targets (and target_images) beyond where the rover is stuck.
            neutered_targets = stuck_rover.targets.split_on_target(target)[1]
            for neutered in neutered_targets:
                stuck_rover.delete_target(neutered)
     
            # Assert that the last rover target (its location) is the same as the target associated
            # with this callback after the neutering.
            assert stuck_rover.targets.last().target_id == target.target_id

            # Add a progress key indicating the rover has become stuck.
            progress.create_new_progress(ctx, user, progress.names.PRO_ROVER_STUCK)

            # Add a new mission to find the stuck rover.
            mission_module.add_mission(ctx, user, "MIS_FIND_STUCK_ROVER", target=target)
            
            # Mark the stuck_rover as inactive.
            stuck_rover.mark_inactive()
            # Add the new rover with the same lander as the old rover.
            lander = stuck_rover.lander
            epoch_now = user.epoch_now
            activated_at = epoch_now - utils.in_seconds(hours=3)
            r = rover_module.create_new_rover(ctx, user, lander=lander, rover_key='RVR_S1_UPGRADE', activated_at=activated_at, active=1)
            # The rover starts at the lander location.
            epoch_now = user.epoch_now
            target_module.create_new_target(ctx, r,
                start_time=activated_at,
                arrival_time=epoch_now - utils.in_seconds(hours=2),
                lat=lander['lat'], lng=lander['lng'], yaw=0.0, picture=0, processed=1)

            # Send messages to the user informing them their rover is stuck and introducing them to
            # their new rover's audio capabilities.
            message.send_all_now(ctx, user, ['MSG_ROVER_STUCKa', 'MSG_AUDIO_TUTORIAL01a'])
            # Intro to your second rover's features.
            message.send_later(ctx, user, 'MSG_ROVER_INTRO02', utils.in_seconds(minutes=1))
            # A message from Kryptex, apologizing for bad advice.
            message.send_later(ctx, user, 'MSG_ROVER_STUCKb', utils.in_seconds(minutes=10))
            # Short-circuit trigger for the photosynthesis science missions.
            send_sci_photosynthesis_messages(ctx, user)
            # Mark done.
            return True
        
        return False

class MIS_FIND_STUCK_ROVER_Callbacks(BaseCallbacks):
    """ An identification mission which is done whenever the first artifact is identified. """
    @classmethod
    def create_specifics(cls, ctx, user, target):
        # Record the stuck rover's location.
        return {'stuck_lat':target.lat,
                'stuck_lng':target.lng}

    @classmethod
    def region_list_not_done(cls, mission):
        stuck = RegionPack('RGN_FIND_STUCK_ROVER_WAYPOINT',
                           center=[mission.specifics['stuck_lat'], mission.specifics['stuck_lng']])
        return ['RGN_FIND_STUCK_ROVER_CONSTRAINT', stuck]

    @classmethod
    def region_list_done(cls, mission):
        stuck = RegionPack('RGN_FIND_STUCK_ROVER_WAYPOINT',
                           center=[mission.specifics['stuck_lat'], mission.specifics['stuck_lng']])
        return [stuck]

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        # If the species was the original rover, then this mission is done.
        done = (identified.key == "SPC_ROVER_DISASSEMBLED")
        if done:
            # Message from XRI remarking on the found rover.  Message callback has other events.
            message.send_later(ctx, user, 'MSG_FOUND_ROVER01a', utils.in_seconds(minutes=1))
            # Message from Kryptex remarking on found rover delivered in the future
            # after she has had time to analyze the imagery.
            message.send_later(ctx, user, 'MSG_FOUND_ROVER01b', utils.in_seconds(hours=1))
            # Turing: Invite your colleagues.
            message.send_later(ctx, user, 'MSG_INVITATIONSa', utils.in_seconds(hours=2))
        return done

class MIS_VISIT_CENTRAL_PLATEAU_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_AUDIO_TUTORIAL01_CARROT']

#======== AUDIO TUTORIAL 1 ========
""" Mission callback for the audio tutorial mission. """

class MIS_AUDIO_TUTORIAL01_Callbacks(AudioMissionParent):
    CHILDREN = ['MIS_AUDIO_TUTORIAL01a', 'MIS_AUDIO_TUTORIAL01b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_TUTORIAL01_ICON'

class MIS_AUDIO_TUTORIAL01a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_TUTORIAL01_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_ORGANIC01'
    SOUND_DETECTED = 'SND_ANIMAL001_ZONE'

    @classmethod
    def audio_mission_started(cls, ctx, user, mission):
        # Jane: Look for these 3 species.
        message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISc', utils.in_seconds(minutes=3))

    @classmethod
    def audio_detected(cls, ctx, user, mission, target):
        # Message from Turing: Listen to that!
        message.send_later(ctx, user, 'MSG_AUDIO_TUTORIAL01b', utils.in_seconds(minutes=10))

class MIS_AUDIO_TUTORIAL01b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_TUTORIAL01_PINPOINT'
    SOUND_DETECTED = 'SND_ANIMAL001_ZONE'
    MISSION_SIBLING = 'MIS_AUDIO_TUTORIAL01a'
    SPECIES_AUDIO_SOURCE = 'SPC_ANIMAL001'
    
    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        # Message from Turing: An animal!
        message.send_later(ctx, user, 'MSG_AUDIO_TUTORIAL01c', utils.in_seconds(minutes=10))
        # Jane: We've seen variations
        message.send_later(ctx, user, 'MSG_SCI_VARIATIONa', utils.in_seconds(hours=24))

#======== OBELISK 1 ========
class MIS_AUDIO_MYSTERY01_Callbacks(AudioMissionParent):
    """ Search for Obelisk 1 """
    CHILDREN = ['MIS_AUDIO_MYSTERY01a', 'MIS_AUDIO_MYSTERY01b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_MYSTERY01_ICON'

class MIS_AUDIO_MYSTERY01a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_MYSTERY01_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_MYSTERY01'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY01'

    @classmethod
    def audio_mission_started(cls, ctx, user, mission):
        # Mark the carrot mission done when triggering MIS_AUDIO_MYSTERY01 or MIS_AUDIO_MYSTERY06.
        carrot = user.missions.get_only_by_definition('MIS_VISIT_CENTRAL_PLATEAU')
        assert carrot != None
        if not carrot.is_done():
            carrot.mark_done()

class MIS_AUDIO_MYSTERY01b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_MYSTERY01_PINPOINT'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY01'
    MISSION_SIBLING = 'MIS_AUDIO_MYSTERY01a'
    SPECIES_AUDIO_SOURCE = 'SPC_UNKNOWN_ORIGIN02'
    SUBSPECIES_AUDIO_SOURCE = set([])
    
    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        send_obelisk_messages(ctx, user, get_done_obelisk_mission_count(user))

#======== OBELISK 2 ========
class MIS_AUDIO_MYSTERY02_Callbacks(AudioMissionParent):
    """ Search for Obelisk 2 """
    CHILDREN = ['MIS_AUDIO_MYSTERY02a', 'MIS_AUDIO_MYSTERY02b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_MYSTERY02_ICON'

class MIS_AUDIO_MYSTERY02a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_MYSTERY02_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_MYSTERY02'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY02'

class MIS_AUDIO_MYSTERY02b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_MYSTERY02_PINPOINT'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY02'
    MISSION_SIBLING = 'MIS_AUDIO_MYSTERY02a'
    SPECIES_AUDIO_SOURCE = 'SPC_UNKNOWN_ORIGIN02'
    SUBSPECIES_AUDIO_SOURCE = set([subspecies_types.artifact.LOCATION_B])

    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        send_obelisk_messages(ctx, user, get_done_obelisk_mission_count(user))

#======== OBELISK 3 ========
class MIS_AUDIO_MYSTERY03_Callbacks(AudioMissionParent):
    """ Search for Obelisk 3 """
    CHILDREN = ['MIS_AUDIO_MYSTERY03a', 'MIS_AUDIO_MYSTERY03b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_MYSTERY03_ICON'

class MIS_AUDIO_MYSTERY03a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_MYSTERY03_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_MYSTERY03'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY03'

class MIS_AUDIO_MYSTERY03b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_MYSTERY03_PINPOINT'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY03'
    MISSION_SIBLING = 'MIS_AUDIO_MYSTERY03a'
    SPECIES_AUDIO_SOURCE = 'SPC_UNKNOWN_ORIGIN02'
    SUBSPECIES_AUDIO_SOURCE = set([subspecies_types.artifact.LOCATION_C])

    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        send_obelisk_messages(ctx, user, get_done_obelisk_mission_count(user))

#======== OBELISK 4 ========
class MIS_AUDIO_MYSTERY04_Callbacks(AudioMissionParent):
    """ Search for Obelisk 4 """
    CHILDREN = ['MIS_AUDIO_MYSTERY04a', 'MIS_AUDIO_MYSTERY04b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_MYSTERY04_ICON'

class MIS_AUDIO_MYSTERY04a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_MYSTERY04_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_MYSTERY04'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY04'

class MIS_AUDIO_MYSTERY04b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_MYSTERY04_PINPOINT'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY04'
    MISSION_SIBLING = 'MIS_AUDIO_MYSTERY04a'
    SPECIES_AUDIO_SOURCE = 'SPC_UNKNOWN_ORIGIN02'
    SUBSPECIES_AUDIO_SOURCE = set([subspecies_types.artifact.LOCATION_D])

    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        send_obelisk_messages(ctx, user, get_done_obelisk_mission_count(user))

#======== OBELISK 5 ========
class MIS_AUDIO_MYSTERY05_Callbacks(AudioMissionParent):
    """ Search for Obelisk 5 """
    CHILDREN = ['MIS_AUDIO_MYSTERY05a', 'MIS_AUDIO_MYSTERY05b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_MYSTERY05_ICON'

class MIS_AUDIO_MYSTERY05a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_MYSTERY05_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_MYSTERY05'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY05'

class MIS_AUDIO_MYSTERY05b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_MYSTERY05_PINPOINT'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY05'
    MISSION_SIBLING = 'MIS_AUDIO_MYSTERY05a'
    SPECIES_AUDIO_SOURCE = 'SPC_UNKNOWN_ORIGIN02'
    SUBSPECIES_AUDIO_SOURCE = set([subspecies_types.artifact.LOCATION_E])

    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        send_obelisk_messages(ctx, user, get_done_obelisk_mission_count(user))

#======== OBELISK 6 ========
class MIS_AUDIO_MYSTERY06_Callbacks(AudioMissionParent):
    """ Search for Obelisk 6 """
    CHILDREN = ['MIS_AUDIO_MYSTERY06a', 'MIS_AUDIO_MYSTERY06b']
    REGION_AUDIO_ICON = 'RGN_AUDIO_MYSTERY06_ICON'

class MIS_AUDIO_MYSTERY06a_Callbacks(AudioMissionChildEnterZone):
    REGION_AUDIO_ZONE = 'RGN_AUDIO_MYSTERY06_ZONE'
    MESSAGE_ROVERAUDIO = 'MSG_ROVERAUDIO_MYSTERY06'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY06'

    @classmethod
    def audio_mission_started(cls, ctx, user, mission):
        # Mark the carrot mission done when triggering MIS_AUDIO_MYSTERY01 or MIS_AUDIO_MYSTERY06.
        carrot = user.missions.get_only_by_definition('MIS_VISIT_CENTRAL_PLATEAU')
        assert carrot != None
        if not carrot.is_done():
            carrot.mark_done()

class MIS_AUDIO_MYSTERY06b_Callbacks(AudioMissionChildTagSource):
    REGION_AUDIO_PINPOINT = 'RGN_AUDIO_MYSTERY06_PINPOINT'
    SOUND_DETECTED = 'SND_AUDIO_MYSTERY06'
    MISSION_SIBLING = 'MIS_AUDIO_MYSTERY06a'
    SPECIES_AUDIO_SOURCE = 'SPC_UNKNOWN_ORIGIN02'
    SUBSPECIES_AUDIO_SOURCE = set([subspecies_types.artifact.LOCATION_F])

    @classmethod
    def audio_identified(cls, ctx, user, mission, target, identified, subspecies):
        send_obelisk_messages(ctx, user, get_done_obelisk_mission_count(user))

#================
class MIS_FIND_EM_SOURCE_Callbacks(BaseCallbacks):
    """ Mission callback for the central monument. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_EM_SOURCE_PINPOINT']

    @classmethod
    def region_list_done(cls, mission):
        return ['RGN_EM_SOURCE_ICON']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        done = (identified.key == "SPC_UNKNOWN_ORIGIN08")
        if done:
            # If the player tagged the central monument before the GPS unit, send a disappointed message from K.
            if user.species.target_count_for_key('SPC_MANMADE005') == 0:
                message.send_later(ctx, user, 'MSG_GPSx', utils.in_seconds(minutes=1))
            # Message from Turing: Coming clean.
            message.send_later(ctx, user, 'MSG_MISSION02c', utils.in_seconds(minutes=15))
            # Message from Kryptex: Keep looking
            message.send_later(ctx, user, 'MSG_MISSION02d', utils.in_seconds(minutes=25))
            # Mark done now. Following code relies on the done status of this mission.
            mission.mark_done()
            # If all conditions are met, unlock access to the ruins.
            enable_access_to_ruins(ctx, user)
            # If MSG_ENCRYPTION01 has also been unlocked, kick off the next message/mission from Turing.
            second_trigger = user.messages.by_type('MSG_ENCRYPTION01')
            if second_trigger is not None and not second_trigger.is_locked():
                # Message from Turing: Head toward ruins.
                message.send_later(ctx, user, 'MSG_GO_TO_RUINS', utils.in_seconds(minutes=45))
        # Signal event system this callback is handling mark_done itself.
        return None

## Kryptex: Get the name of the GPS unit and use it as a password.
class MIS_FIND_GPS_UNIT_Callbacks(SerialMissionParent):
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_GPS_MISSION_ICON']

    CHILDREN = ['MIS_FIND_GPS_UNITa', 'MIS_FIND_GPS_UNITb']

class MIS_FIND_GPS_UNITa_Callbacks(SerialMissionChild):
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        # Mark the first half of the mission done if the player tagged the GPS unit.
        done = (identified.key == "SPC_MANMADE005")
        return done

class MIS_FIND_GPS_UNITb_Callbacks(SerialMissionChild):
    # Mark the second half of the mission done if the player uses the password.
    # This is handled in the was_unlocked callback for message MSG_ENCRYPTION01.
    pass

class MIS_VISIT_RUINS_Callbacks(BaseCallbacks):
    """ Mission callback for the first photo of the ruins. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_RUINS_PINPOINT']

    @classmethod
    def region_list_done(cls, mission):
        return ['RGN_RUINS_ICON']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        done = (identified.key == "SPC_UNKNOWN_ORIGIN09")
        if done:
            # T: Amazing! More photos, please. (Message has callbacks to change missions.)
            message.send_later(ctx, user, 'MSG_RUINSa', utils.in_seconds(minutes=1))
            # K: Contacting Enki.
            message.send_later(ctx, user, 'MSG_ENKI01a', utils.in_seconds(minutes=25))
        return done

class MIS_PHOTOGRAPH_RUINS_Callbacks(BaseCallbacks):
    """ Mission callback for 2 additional photos of the ruins. """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        ruins_tagged = (identified.key == "SPC_UNKNOWN_ORIGIN09")
        # TODO: Make sure the player isn't just tagging the same image repeatedly.
        if ruins_tagged:
            # Take one more photo.
            mission_module.add_mission(ctx, user, 'MIS_PHOTOGRAPH_RUINS02')
            # T: Take more photos.
            message.send_later(ctx, user, 'MSG_RUINSb', utils.in_seconds(minutes=1))
            # T: Where did the aliens go?
            message.send_later(ctx, user, 'MSG_RUINSd', utils.in_seconds(minutes=30))
            return True
        return False # This mission stays active until a few photos have been taken and tagged.

class MIS_PHOTOGRAPH_RUINS02_Callbacks(BaseCallbacks):
    """ Mission callback for 1 additional photo of the ruins. """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        ruins_tagged = (identified.key == "SPC_UNKNOWN_ORIGIN09")
        # TODO: Make sure the player isn't just tagging the same image repeatedly.
        if ruins_tagged:
            # T: Photograph the signal source.
            message.send_later(ctx, user, 'MSG_RUINSc', utils.in_seconds(minutes=1))
            # Add a progress key that will enable access to the signal source and obelisk 3.
            progress.create_new_progress(ctx, user, progress.names.PRO_ENABLE_NORTH_REGION)
            return True
        return False # This mission stays active until a few photos have been taken and tagged.

class MIS_RUINS_SIGNAL_SOURCE_Callbacks(BaseCallbacks):
    """ Mission callback for photographing complete message. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_RUINS_SIGNAL_PINPOINT']

    @classmethod
    def region_list_done(cls, mission):
        return ['RGN_RUINS_SIGNAL_ICON']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        done = (identified.key == "SPC_UNKNOWN_ORIGIN10")
        if done:
            # T: The full signal source!
            message.send_later(ctx, user, 'MSG_RUINSe', utils.in_seconds(minutes=1))
            # K: The full signal source!
            message.send_later(ctx, user, 'MSG_RUINSf', utils.in_seconds(minutes=30))
            # Set a progress key that will open access to all obelisks.
            progress.create_new_progress(ctx, user, progress.names.PRO_ENABLE_ALL_OBELISKS)
            # T: Adding landmarks to map.
            message.send_later(ctx, user, 'MSG_LANDMARKS01', utils.in_seconds(hours=2))
        return done

class MIS_2_MORE_OBELISKS_Callbacks(BaseCallbacks):
    """ Mission callback for photographing 2 more obelisks. """
    @classmethod
    def region_list_not_done(cls, mission):
        obelisk_regions = get_untagged_obelisk_regions_at_mission_start(mission)
        assert len(obelisk_regions) == 2, 'obelisk_regions='+str(obelisk_regions)
        return obelisk_regions

class MIS_1_MORE_OBELISK_Callbacks(BaseCallbacks):
    """ Mission callback for photographing 1 more obelisk. """
    @classmethod
    def region_list_not_done(cls, mission):
        obelisk_regions = get_untagged_obelisk_regions_at_mission_start(mission)
        assert len(obelisk_regions) == 1, 'obelisk_regions='+str(obelisk_regions)
        return obelisk_regions

class MIS_CODED_LOC_Callbacks(BaseCallbacks):
    """ Mission callback for photographing the item at the coded location discovered by Kryptex. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_CODED_LOC_PINPOINT']

    @classmethod
    def region_list_done(cls, mission):
        return ['RGN_CODED_LOC_ICON']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        done = (identified.key == "SPC_MANMADE006")
        if done:
            # K: what's so special about that?
            message.send_later(ctx, user, 'MSG_CODED_LOCa', utils.in_seconds(minutes=1))

            # TODO: DELETE THIS. I moved this message to be sent earlier in the timeline, but we need to keep this
            # second trigger in place for a while for players who have already passed the first trigger.
            if not user.messages.has_been_queued_or_delivered('MSG_LANDMARKS01'):
                # T: Adding landmarks to map.
                message.send_later(ctx, user, 'MSG_LANDMARKS01', utils.in_seconds(minutes=45))

        return done

class MIS_MONUMENT_PLAYBACK_Callbacks(SerialMissionParent):
    """ Mission callback collecting all 6 audio clips and playing back at central monument. """
    CHILDREN = ['MIS_MONUMENT_PLAYBACKa', 'MIS_MONUMENT_PLAYBACKb']

    @classmethod
    def was_created(cls, ctx, user, mission):
        # If the player already found all 6 obelisks, then mark the first part done.
        if user.messages.has_been_queued_or_delivered('MSG_OBELISK06a'):
            mission.mark_done()

class MIS_MONUMENT_PLAYBACKa_Callbacks(SerialMissionChild):
    # This will be marked complete when the 6th obelisk is tagged.
    pass

class MIS_MONUMENT_PLAYBACKb_Callbacks(SerialMissionChild):
    @classmethod
    def region_list_when_active(cls, mission):
        return ['RGN_EM_SOURCE_PLAYBACK_ZONE']

    # TODO: If we later allow the player to select an audio clip for playback, then for both
    # target_en_route and arrived_at_target, also check to make sure the audio clip is has been
    # selected before activating any triggers.
    # Note that both target_en_route and arrived_at_target must have exactly the same trigger conditions.
    @classmethod
    def target_en_route(cls, ctx, user, mission, target):
        if not user.missions.get_only_by_definition('MIS_MONUMENT_PLAYBACKa').is_done():
            return False;  # We need all 6 audio clips first.

        assert get_done_obelisk_mission_count(user) == 6
        zone = region.from_id('RGN_EM_SOURCE_PLAYBACK_ZONE')
        will_be_done = target.is_inside_region(zone)
        if will_be_done and not user.messages.has_been_queued_or_delivered('MSG_LASTTHINGa'):
            # Send a message from Kryptex just before the mission gets completed.
            time_until_send = target.arrival_time - target.start_time - utils.in_seconds(minutes=15)
            assert time_until_send > 0
            # K: I need you to photograph a rover.
            message.send_later(ctx, user, 'MSG_LASTTHINGa', time_until_send)

        # This callback should never cause completion of the mission.
        return False

    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        if not user.missions.get_only_by_definition('MIS_MONUMENT_PLAYBACKa').is_done():
            return False;  # We need all 6 audio clips first.

        assert get_done_obelisk_mission_count(user) == 6
        zone = region.from_id('RGN_EM_SOURCE_PLAYBACK_ZONE')
        done = target.is_inside_region(zone)
        if done: 
            # Attach the sound of the tone playback and the resulting foghorn and earthquake.
            target.detected_sound("SND_MONUMENT_PLAYBACK")

            # RCJ: It's theoretically possible (though unlikely) that the player tagged the
            # 6th obelisk _while_ the rover was en route to this target.  Just in case,
            # double-check that this message gets sent.
            if not user.messages.has_been_queued_or_delivered('MSG_LASTTHINGa'):
                logger.warning("MSG_LASTTHINGa sent later than expected [%s]", user.user_id)
                # K: I need you to photograph a rover.
                message.send_now(ctx, user, 'MSG_LASTTHINGa')

            # T: We've lost connectivity.
            message.send_later(ctx, user, 'MSG_MISSION04b', utils.in_seconds(minutes=1))
            # T: Something happened to one of our rovers.
            message.send_later(ctx, user, 'MSG_MISSION04c', utils.in_seconds(minutes=10))
            # K: i need that rover!
            message.send_later(ctx, user, 'MSG_LASTTHINGb', utils.in_seconds(minutes=15))
        return done

class MIS_FIND_LOST_ROVER_Callbacks(BaseCallbacks):
    """ Mission callbacks for finding the rover that's gone missing on the north coast. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_MISSING_ROVER_ICON']

    @classmethod
    def target_created(cls, ctx, user, mission, target):
        # If this is the lost-at-sea target that is programatically created by the arrived_at_target
        # function, don't do anything here.
        if 'TGT_S1_LOST_AT_SEA' in target.metadata:
            return False

        # If the user has already created the target where it will fall off the cliffs, then mark
        # targets that will be neutered. These targets will remain as markers on the map until the rover
        # arrives at the threshold target, at which time we delete all future targets past this point.
        # Note: Neutering a target marks it as processed to make sure that it's never passed to
        # the renderer.
        if (user.has_target_with_metadata_key('TGT_S1_FALL_OFF_CLIFFS')):
            target.mark_as_neutered()

        # If this target is inside the trigger zone, add target metadata to indicate that the rover
        # will fall off the cliffs so any additional targets created before the rover arrives
        # at the target will be neutered and not rendered.
        trigger_zone = region.from_id('RGN_MISSING_ROVER_TRIGGER')
        if target.is_inside_region(trigger_zone):
            target.add_metadata_unique('TGT_S1_FALL_OFF_CLIFFS')

        # Will be marked done by the arrived_at_target callback when the rover has become stuck.
        return False

    @classmethod
    def target_en_route(cls, ctx, user, mission, target):
        # If this is the lost-at-sea target that is programatically created by the arrived_at_target
        # function, don't do anything here.
        if 'TGT_S1_LOST_AT_SEA' in target.metadata:
            return False

        # If this target is inside the trigger zone, add target metadata to indicate that the rover
        # will fall off the cliffs.
        trigger_zone = region.from_id('RGN_MISSING_ROVER_TRIGGER')
        if target.is_inside_region(trigger_zone) and not user.messages.has_been_queued_or_delivered('MSG_LASTTHINGd'):
            # We duplicate some of the code from target_created to account for the unlikely scenario
            # when this mission was not active when this target was created.
            if target.add_metadata_unique('TGT_S1_FALL_OFF_CLIFFS') == True:
                logger.warning("Metadata key TGT_S1_FALL_OFF_CLIFFS was expected but not found [%s, %s]", user.user_id, target.target_id)

            # Neuter any future targets that have already been scheduled.
            neutered_targets = target.rover.targets.split_on_target(target)[1]
            for neutered in neutered_targets:
                neutered.mark_as_neutered()
        
        # Will be marked done by the arrived_at_target callback.
        return False

    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        trigger_zone = region.from_id('RGN_MISSING_ROVER_TRIGGER')
        if target.is_inside_region(trigger_zone) and not user.messages.has_been_queued_or_delivered('MSG_LASTTHINGd'):
            # K: password on rover unlocks the doc.
            mission_module.add_mission(ctx, user, 'MIS_UNLOCK_LAST_DOC')
            # T: Lost contact with your rover too.
            message.send_now(ctx, user, 'MSG_LASTTHINGd')
            # K: no! what happened!
            message.send_later(ctx, user, 'MSG_LASTTHINGe', utils.in_seconds(minutes=5))

            # Delete any future targets (and target_images) beyond where the rover is stuck.
            tragic_rover = target.rover
            neutered_targets = tragic_rover.targets.split_on_target(target)[1]
            for neutered in neutered_targets:
                tragic_rover.delete_target(neutered)
     
            # Assert that the last rover target (its location) is the same as the target associated
            # with this callback after the neutering.
            assert tragic_rover.targets.last().target_id == target.target_id
            
            # Create a new target in the ocean pre-rendered with a special image taken from the
            # water and looking back at the island.
            region_swim = region.from_id('RGN_S1_LOST_AT_SEA');
            epoch_now = user.epoch_now
            target_distress = target_module.create_new_target(ctx, tragic_rover, scene=scene.DISTRESS01,
                start_time=epoch_now, arrival_time=epoch_now + utils.in_seconds(hours=1), classified=1,
                lat=region_swim.center[0], lng=region_swim.center[1], yaw=3.3, picture=1, processed=1,
                metadata={'TGT_S1_LOST_AT_SEA': ''})
            # Attach the voice of the aquatics.
            target_distress.detected_sound("SND_DISTRESS01")

            # Mark the rover as inactive.  We won't issue a new rover until MSG_END is sent.
            tragic_rover.mark_inactive()
            # Mark done.
            return True

        return False

class MIS_UNLOCK_LAST_DOC_Callbacks(BaseCallbacks):
    """ Find the rover that's gone missing so that you can get the final S1 password. """
    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        # Is this the target where we hear the voice of the aquatics?
        if 'SND_DISTRESS01' in target.sounds and not user.messages.has_been_queued_or_delivered('MSG_LASTTHINGf'):
            # T: Whalesong?! We have 24h.
            message.send_later(ctx, user, 'MSG_LASTTHINGf', utils.in_seconds(minutes=5))

            # To create a target that's hidden from the player, we'll create a new rover
            # that's outside of the viewable map bounds and then create a target for that rover.
            hidden_region = region.from_id('RGN_S1_OFF_MAP');

            # Create a lander to be associated with the rover.
            hidden_lander = rover_module.create_new_lander(ctx, lat=hidden_region.center[0], lng=hidden_region.center[1])

            # Create the rover, but immediately mark it inactive.
            epoch_now = user.epoch_now
            activated_at = epoch_now
            hidden_rover = rover_module.create_new_rover(ctx, user, hidden_lander, rover_key='RVR_S1_NEW_ISLAND', activated_at=activated_at, active=0)

            # Create a new target off the map with a special metadata key to indicate the keycode
            # that should be painted on the side of a rover that is visible in the scene.
            target_module.create_new_target(ctx, hidden_rover,
                start_time=activated_at, arrival_time=epoch_now + utils.in_seconds(hours=23), classified=1,
                lat=hidden_region.center[0], lng=hidden_region.center[1], yaw=0.0, picture=1, processed=0,
                metadata={'TGT_S1_STRANDED_ROVER': message.keycode_for_msg_type('MSG_LASTTHINGa', user)})

        # Is this the target that shows the image of a new island and the missing rover?
        elif 'TGT_S1_STRANDED_ROVER' in target.metadata and not user.messages.has_been_queued_or_delivered('MSG_LASTTHINGg'):
            # T: We got an image.
            message.send_later(ctx, user, 'MSG_LASTTHINGg', utils.in_seconds(minutes=3))
            # K: that's it!
            message.send_later(ctx, user, 'MSG_LASTTHINGh', utils.in_seconds(minutes=5))
        return False


# ======== SCIENCE MISSIONS ========

class FindSpeciesMission(BaseCallbacks):
    NO_OVERRIDE = ['species_identified']

    # Set this to the number of organic species that must be fully detected by the
    # user to mark this mission done.
    SPECIES_COUNT = None

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        organics = species.are_organic(user.species.values())
        if len(organics) >= cls.SPECIES_COUNT:
            delayed = species.are_currently_delayed(organics)
            if len(delayed) == 0:
                return True
            else:
                # Find the species with the most amount of time left until fully available.
                longest_delay = max(delayed, key=lambda s: s.delayed_seconds_remaining)
                # Mark the mission done when that species with the longest delay is fully available.
                mission.mark_done_after(utils.in_seconds(seconds=longest_delay.delayed_seconds_remaining))
                return False
        return False

class MIS_SPECIES_FIND_5_Callbacks(FindSpeciesMission):
    """ An identification mission which is done whenever 5 organic species are identified. """
    SPECIES_COUNT = 5

    @classmethod
    def marked_done(cls, ctx, user, mission):
        send_sci_photosynthesis_messages(ctx, user)

class MIS_SPECIES_FIND_10_Callbacks(FindSpeciesMission):
    """ An identification mission which is done whenever 10 unique species are identified. """
    SPECIES_COUNT = 10

    @classmethod
    def marked_done(cls, ctx, user, mission):
        # Jane: Congrats!
        message.send_later(ctx, user, 'MSG_FIND_10', utils.in_seconds(minutes=11))

class MIS_SPECIES_FIND_15_Callbacks(FindSpeciesMission):
    """ An identification mission which is done whenever 15 unique species are identified. """
    SPECIES_COUNT = 15

    @classmethod
    def marked_done(cls, ctx, user, mission):
        # Jane: Congrats!
        message.send_later(ctx, user, 'MSG_FIND_15', utils.in_seconds(minutes=5))

class MIS_SCI_FIND_COMMON_Callbacks(MissionParent):
    """ Find these 2 presumed-common species outside of the sandbox. """
    CHILDREN = ['MIS_SCI_FIND_COMMONa', 'MIS_SCI_FIND_COMMONb', 'MIS_SCI_FIND_COMMONc']

class MIS_SCI_FIND_COMMONa_Callbacks(MissionChild):
    """ Find the serpentgrass """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_PLANT021'):
            # Outside of sandbox.
            species_counts = user.species_count(only_subspecies_id=subspecies_types.plant.LOCATION_B)
            if species_counts[identified.species_id] >= 2:
                # Jane: experimenting on serpentgrass.
                message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISd', utils.in_seconds(minutes=3))
                # Jane: experiment a success.
                message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISe', utils.in_seconds(days=2.9))

                # If child missions a and b are both done, then cancel child mission c.
                if len(mission.done_siblings()) == 1 and not user.messages.has_been_queued_or_delivered('MSG_SCI_PHOTOSYNTHESISh'):
                    # Jane: We will not experiment on the aircomber.
                    message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISh', utils.in_seconds(minutes=15))
                return True
        return False

class MIS_SCI_FIND_COMMONb_Callbacks(MissionChild):
    """ Find the spindlepod """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_PLANT024'):
            # Outside of sandbox.
            species_counts = user.species_count(only_subspecies_id=subspecies_types.plant.LOCATION_B)
            if species_counts[identified.species_id] >= 2:
                # Jane: experimenting on spindlepod.
                message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISf', utils.in_seconds(minutes=7))
                # Jane: experiment a success.
                message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISg', utils.in_seconds(days=6.9))

                # If child missions a and b are both done, then cancel child mission c.
                if len(mission.done_siblings()) == 1 and not user.messages.has_been_queued_or_delivered('MSG_SCI_PHOTOSYNTHESISh'):
                    # Jane: We will not experiment on the aircomber.
                    message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISh', utils.in_seconds(minutes=15))
                return True
        return False

class MIS_SCI_FIND_COMMONc_Callbacks(MissionChild):
    """ Find the aircomber. This child mission should be impossible to accomplish.
        It will get marked done when the other 2 submissions are complete. """
    @classmethod
    def child_marked_done(cls, ctx, user, mission):
        send_sci_cellular_end_messages(ctx, user)

class MIS_SCI_CELLULARa_Callbacks(BaseCallbacks):
    """ Find 3 gordy trees. """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_PLANT032'):
            species_counts = user.species_count()
            if species_counts[identified.species_id] >= 3:
                # Jane: Results from celluar analysis
                message.send_later(ctx, user, 'MSG_SCI_CELLULARb', utils.in_seconds(hours=24))
                send_sci_cellular_start_messages(ctx, user, identified.species_id)
                return True
        return False

class MIS_SCI_LIFECYCLE_Callbacks(BaseCallbacks):
    """ Find all 3 life stages of the gordy tree. """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_PLANT032'):
            # Have we seen all 3 life stages of the gordy tree?
            subspecies_count = user.subspecies_count_for_species(identified.species_id)
            observed_life_stages = 0
            for i in [subspecies_types.plant.DEFAULT, subspecies_types.plant.YOUNG, subspecies_types.plant.DEAD]:
                if subspecies_count[i] != 0:
                    observed_life_stages += 1
            if observed_life_stages >= 3:
                # Mark done now. Following code relies on the done flag being set.
                mission.mark_done()
                send_sci_cellular_end_messages(ctx, user)
                return None
        return False

class MIS_SCI_VARIATION_Callbacks(BaseCallbacks):
    """ Find bristletongue variant """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_SCI_VARIATION_PINPOINT']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_ANIMAL006'):
            # Jane: About variations
            message.send_later(ctx, user, 'MSG_SCI_VARIATIONb', utils.in_seconds(minutes=15))
            return True
        return False

class MIS_SCI_FLOWERS_Callbacks(BaseCallbacks):
    """ Tag open and closed starspore flowers """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_PLANT028'):
            # Have we seen 2 instances of both the open and closed variations?
            subspecies_count = user.subspecies_count_for_species(identified.species_id)
            if subspecies_count[subspecies_types.plant.DEFAULT] >= 2 and subspecies_count[subspecies_types.plant.VARIATION_B] >= 2:
                # Jane: Speculation on "flowers"
                message.send_later(ctx, user, 'MSG_SCI_FLOWERSb', utils.in_seconds(minutes=20))
                return True
        return False

class MIS_SCI_BIOLUMINESCENCE_Callbacks(BaseCallbacks):
    """ Tag all 3 bioluminescent colors, 2x each. """
    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        BIOLUMINESCENT_SPECIES = [0x1000f0, 0x100160, 0x1001F0]
        if identified.species_id in BIOLUMINESCENT_SPECIES:
            # Count only species exhibiting bioluminescence.
            species_counts =  user.species_count(only_subspecies_id=subspecies_types.plant.BIOLUMINESCENT)
            observed_species = 0
            for species_id in BIOLUMINESCENT_SPECIES:
                if species_counts[species_id] >= 2:
                    observed_species += 1
            if observed_species >= 3:
                # Jane: Analysis of bioluminescent species.
                message.send_later(ctx, user, 'MSG_SCI_BIOLUMINESCENCEb', utils.in_seconds(minutes=10))
                return True
        return False

class MIS_SCI_FLIGHT_Callbacks(BaseCallbacks):
    """ Photograph flying creatures. """
    @classmethod
    def region_list_not_done(cls, mission):
        return ['RGN_SCI_FLIGHT01', 'RGN_SCI_FLIGHT02', 'RGN_SCI_FLIGHT03']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        if (identified.key == 'SPC_ANIMAL004'):
            species_counts = user.species_count()
            if species_counts[identified.species_id] >= 3:
                # Jane: Flying species analysis
                message.send_later(ctx, user, 'MSG_SCI_FLIGHTb', utils.in_seconds(minutes=5))
                return True
        return False

#======== BREATHING PLANT ========
class MIS_AUDIO_MYSTERY07_Callbacks(SerialMissionParent):
    """ Search for audio source """
    CHILDREN = ['MIS_AUDIO_MYSTERY07a', 'MIS_AUDIO_MYSTERY07b']

    @classmethod
    def was_created(cls, ctx, user, mission):
        # Message from rover: Sound detected.
        message.send_now(ctx, user, 'MSG_ROVERAUDIO_MYSTERY07')

class MIS_AUDIO_MYSTERY07a_Callbacks(SerialMissionChild):
    """ Mission callback for arriving in the audio zone. """
    @classmethod
    def region_list_when_active(cls, mission):
        return ['RGN_AUDIO_MYSTERY07_ZONE']

    @classmethod
    def arrived_at_target(cls, ctx, user, mission, target):
        zone = user.regions['RGN_AUDIO_MYSTERY07_ZONE']
        done = target.traverses_region(zone)
        if done: 
            # Attach the detected sound data to this target.
            target.detected_sound("SND_AUDIO_MYSTERY07")
            # Jane: So many pinpoints!
            message.send_later(ctx, user, 'MSG_SCI_AUDIO_MYSTERY07b', utils.in_seconds(minutes=5))
        return done

class MIS_AUDIO_MYSTERY07b_Callbacks(SerialMissionChild):
    """ Mission callback for tagging a breathing photobiont. """
    @classmethod
    def region_list_when_active(cls, mission):
        # After we've entered the zone, show a bunch of scattered pinpoints.
        return ['RGN_AUDIO_MYSTERY07_PINPOINT01', 'RGN_AUDIO_MYSTERY07_PINPOINT02', 'RGN_AUDIO_MYSTERY07_PINPOINT03',
                'RGN_AUDIO_MYSTERY07_PINPOINT04', 'RGN_AUDIO_MYSTERY07_PINPOINT05', 'RGN_AUDIO_MYSTERY07_PINPOINT06']

    @classmethod
    def species_identified(cls, ctx, user, mission, target, identified, subspecies):
        # Usually, players can short-circuite an audio mission's sequence by tagging the origin of
        # the sound before entering the zone.  In this case, we want to force MIS_AUDIO_MYSTERY07a
        # to get completed first to make sure messages are sent in the right order.
        if user.missions.get_only_by_definition('MIS_AUDIO_MYSTERY07a').is_done():
            if identified.key == 'SPC_PLANT014' and subspecies_types.plant.LOCATION_B in subspecies:
                # Jane: A breathing plant?
                message.send_later(ctx, user, 'MSG_SCI_AUDIO_MYSTERY07c', utils.in_seconds(minutes=35))
                return True
        return False

# ======== SHARED CALLBACK FUNCTIONS ========

def enable_access_to_ruins(ctx, user):
    # Both of these triggers must be met to grant access to the ruins.
    # This is partly to ensure that MSG_ENCRYPTION02 is sent before Kryptex finds the coordinates of the
    # coded location that will unlock it.
    mis_trigger = user.missions.get_only_by_definition('MIS_FIND_EM_SOURCE')
    msg_trigger = user.messages.by_type('MSG_ENCRYPTION01')
    if mis_trigger is not None and mis_trigger.is_done() and msg_trigger is not None and not msg_trigger.is_locked():
        # Add a progress key that will unlock access to the ruins.
        progress.create_new_progress(ctx, user, progress.names.PRO_ENABLE_NE_REGION)

def before_kryptex_lockout(user):
    return not user.messages.has_been_queued_or_delivered('MSG_ENKI02a')

def after_kryptex_lockout(user):
    # Check if the video where Kryptex contacts Turing has been viewed (has been unlocked).
    msg_contact = user.messages.by_type('MSG_BACKb')
    return msg_contact is not None and not msg_contact.is_locked()

def during_kryptex_lockout(user):
    return not before_kryptex_lockout(user) and not after_kryptex_lockout(user)

def send_obelisk_messages(ctx, user, tagged_obelisk_count):
    # Perform the appropriate events based on the number of obelisks that have been
    # tagged so far, regardless of the order in which they are visited.
    # Behavior for obelisks 5 and 6 differs depending on whether Kryptex has established
    # communication with Turing (MSG_BACKb unlocked).
    assert tagged_obelisk_count >= 1 and tagged_obelisk_count <= 6

    if tagged_obelisk_count == 1 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK01a'):
        assert before_kryptex_lockout(user)
        # Set a progress key to enable access to the central monument and first GPS unit.
        progress.create_new_progress(ctx, user, progress.names.PRO_TAGGED_ONE_OBELISK)
        # Message from Kryptex: Need more writing!
        message.send_later(ctx, user, 'MSG_OBELISK01a', utils.in_seconds(minutes=1))
        # Message from Turing: Go to GPS Unit. (Message has callbacks.)
        message.send_later(ctx, user, 'MSG_MISSION02a', utils.in_seconds(minutes=2))
        # Message from Kryptex: They're lying.
        message.send_later(ctx, user, 'MSG_PHONE01a', utils.in_seconds(minutes=20))
        # Message from Kryptex: Who's Arling?
        message.send_later(ctx, user, 'MSG_PHONE01b', utils.in_seconds(hours=1))
        # Message from Kryptex: More on Arling.
        message.send_later(ctx, user, 'MSG_ENCRYPTION01', utils.in_seconds(hours=1.5))
        # Message from Kryptex: Get the password from the GPS unit. (Message has callbacks.)
        message.send_later(ctx, user, 'MSG_GPSa', utils.in_seconds(hours=2))

    elif tagged_obelisk_count == 2 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK02a'):
        assert before_kryptex_lockout(user)
        # Message from Turing: Hmmm... another obelisk.
        message.send_later(ctx, user, 'MSG_OBELISK02a', utils.in_seconds(minutes=15))
        # Message from Kryptex: Good, more writing.
        message.send_later(ctx, user, 'MSG_OBELISK02b', utils.in_seconds(minutes=25))

    elif tagged_obelisk_count == 3 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK03a'):
        assert before_kryptex_lockout(user)
        # K: First half of encrypted msg.
        message.send_later(ctx, user, 'MSG_OBELISK03a', utils.in_seconds(minutes=15))
        # K: More about my father.
        message.send_later(ctx, user, 'MSG_OBELISK03b', utils.in_seconds(hours=2))
        # Set a progress key that will open access to the second GPS unit.
        progress.create_new_progress(ctx, user, progress.names.PRO_ENABLE_NW_REGION)

    elif tagged_obelisk_count == 4 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK04a'):
        # Could be before, during or after kryptex gets locked out.
        # T: Obelisks form a circle.
        message.send_later(ctx, user, 'MSG_OBELISK04a', utils.in_seconds(minutes=5))
        if not during_kryptex_lockout(user):
            # K: another coded message.
            message.send_later(ctx, user, 'MSG_OBELISK04b', utils.in_seconds(minutes=10))
            # Rather than using message.send_later, we use a timer event to send the appropriate
            # message version when the callback is run.
            deferred.run_on_timer(ctx, 'TMR_MSG_OBELISK04c', user, utils.in_seconds(hours=1.5))

    elif tagged_obelisk_count == 5 and not after_kryptex_lockout(user) and not user.messages.has_been_queued_or_delivered('MSG_OBELISK05z'):
        # T: I was right about obelisk positions.
        message.send_later(ctx, user, 'MSG_OBELISK05z', utils.in_seconds(minutes=5))

    elif tagged_obelisk_count == 6 and not after_kryptex_lockout(user) and not user.messages.has_been_queued_or_delivered('MSG_OBELISK06z'):
        # T: What's the significance of the obelisks?
        message.send_later(ctx, user, 'MSG_OBELISK06z', utils.in_seconds(minutes=5))
    

    if after_kryptex_lockout(user):
        # Kryptex has contacted Turing.  Note that if this function is called right after the Kryptex
        # Lockout (Unlock MSG_BACKb), the Obelisk04/05/06 messages may need to be sent.
        send_delay = 0
        if not user.messages.has_been_queued_or_delivered('MSG_BACKc'):
            # T: I need to know what's going on.
            message.send_later(ctx, user, 'MSG_BACKc', utils.in_seconds(minutes=20))
            send_delay += utils.in_seconds(minutes=20)

        if tagged_obelisk_count >= 4 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK04b'):
            # K: another coded message.
            message.send_later(ctx, user, 'MSG_OBELISK04b', utils.in_seconds(minutes=10))
            # Rather than using message.send_later, we use a timer event to send the appropriate
            # message version when the callback is run.
            deferred.run_on_timer(ctx, 'TMR_MSG_OBELISK04c', user, utils.in_seconds(hours=1))
            send_delay += utils.in_seconds(hours=1)

        if tagged_obelisk_count >= 5 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK05a'):
            # K: enough data to translate.
            message.send_later(ctx, user, 'MSG_OBELISK05a', send_delay + utils.in_seconds(minutes=5))
            # K: the full message. no warnings.
            message.send_later(ctx, user, 'MSG_OBELISK05b', send_delay + utils.in_seconds(hours=3))
            # T: Why is Arling involved?
            message.send_later(ctx, user, 'MSG_OBELISK05c', send_delay + utils.in_seconds(hours=3.2))
            # K: this means fraud, treason.
            message.send_later(ctx, user, 'MSG_OBELISK05d', send_delay + utils.in_seconds(hours=3.4))
            # T: Revealing the truth could shut us down.
            message.send_later(ctx, user, 'MSG_OBELISK05e', send_delay + utils.in_seconds(hours=3.6))
            # K: arling must pay.
            message.send_later(ctx, user, 'MSG_OBELISK05f', send_delay + utils.in_seconds(hours=3.8))
            send_delay += utils.in_seconds(hours=3.8)

        if tagged_obelisk_count == 6 and not user.messages.has_been_queued_or_delivered('MSG_OBELISK06a'):
            # If the player has the sub-mission to find all 6 obelisks, mark it done now.
            msn_find_all = user.missions.get_only_by_definition('MIS_MONUMENT_PLAYBACKa')
            if msn_find_all:
                msn_find_all.mark_done()
            # T: We'll blackmail Arling.
            message.send_later(ctx, user, 'MSG_OBELISK06a', send_delay + utils.in_seconds(minutes=5))
            # K: ok. listen in on the call.
            message.send_later(ctx, user, 'MSG_OBELISK06b', send_delay + utils.in_seconds(minutes=30))

    # If we're just tagged the 5th or 6th obelisk, mark the appropriate mission as done.
    if tagged_obelisk_count == 5:
        mis_2_more = user.missions.get_only_by_definition('MIS_2_MORE_OBELISKS')
        mis_1_more = user.missions.get_only_by_definition('MIS_1_MORE_OBELISK')
        # Guard against taking any action when the end of the Kryptex lockout triggered this routine.
        # Note that if obelisks 4 and 5 were tagged in rapid succession, MIS_2_MORE_OBELISKS may not exist.
        if mis_2_more and not mis_2_more.is_done():
            mis_2_more.mark_done()
        if not mis_1_more:
            mission_module.add_mission(ctx, user, 'MIS_1_MORE_OBELISK')

    elif tagged_obelisk_count == 6:
        mis_obelisks = user.missions.get_only_by_definition('MIS_1_MORE_OBELISK')
        # Guard against taking any action when the end of the Kryptex lockout triggered this routine.
        if not mis_obelisks.is_done():
            mis_obelisks.mark_done()

def send_sci_photosynthesis_messages(ctx, user):
    if not user.messages.has_been_queued_or_delivered('MSG_SCI_PHOTOSYNTHESISa'):
        # Jane: Congrats
        message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISa', utils.in_seconds(minutes=11))
        # Jane: An explosion!
        message.send_later(ctx, user, 'MSG_SCI_PHOTOSYNTHESISb', utils.in_seconds(hours=22))
        # Jane: Speculation about photobionts.
        message.send_later(ctx, user, 'MSG_SCI_GASSES', utils.in_seconds(hours=36))

def send_sci_cellular_start_messages(ctx, user, species_id):
    if not user.messages.has_been_queued_or_delivered('MSG_SCI_CELLULARa'):
        # Jane: Find more gordy trees.
        message.send_later(ctx, user, 'MSG_SCI_CELLULARa', utils.in_seconds(minutes=15))
    if not user.messages.has_been_queued_or_delivered('MSG_SCI_CELLULARc'):
        # Have we already seen at least 2 life stages of the gordy tree OR completed MIS_SCI_CELLULARa?
        subspecies_count = user.subspecies_count_for_species(species_id)
        observed_life_stages = 0
        for i in [subspecies_types.plant.DEFAULT, subspecies_types.plant.YOUNG, subspecies_types.plant.DEAD]:
            if subspecies_count[i] != 0:
                observed_life_stages += 1
        mis_cellular = user.missions.get_only_by_definition('MIS_SCI_CELLULARa')
        if observed_life_stages >= 2 or (mis_cellular is not None and mis_cellular.is_done()):
            # Jane: Observe the life stages.
            message.send_later(ctx, user, 'MSG_SCI_CELLULARc', utils.in_seconds(minutes=20))

def send_sci_cellular_end_messages(ctx, user):
    mis_common    = user.missions.get_only_by_definition('MIS_SCI_FIND_COMMONc')
    mis_lifecycle = user.missions.get_only_by_definition('MIS_SCI_LIFECYCLE')
    if not user.messages.has_been_queued_or_delivered('MSG_SCI_CELLULARd') \
        and mis_common    is not None and mis_common.is_done() \
        and mis_lifecycle is not None and mis_lifecycle.is_done():
            # Jane: Next steps.
            message.send_later(ctx, user, 'MSG_SCI_CELLULARd', utils.in_seconds(minutes=10))

def send_sci_variation_message(ctx, user):
    ''' If the user has observed all 3 of the species with cnideria, send a message. '''
    SPECIES_WITH_CNIDERIA = [0x1000c0, 0x100210, 0x100220]
    if not user.messages.has_been_queued_or_delivered('MSG_SCI_VARIATIONc'):
        species_counts = user.species_count()
        observed_species = 0
        for species_id in SPECIES_WITH_CNIDERIA:
            if species_counts[species_id] > 0:
                observed_species += 1
        if observed_species >= 3:
            # Jane: Speculation about cnideria
            message.send_later(ctx, user, 'MSG_SCI_VARIATIONc', utils.in_seconds(minutes=30))

def trigger_sci_bioluminescence(ctx, user, species_id):
    ''' If the message that kicks off the bioluminescence missions has not yet been sent
        and the given species was seen at night without flash (i.e., visibly glowing),
        then kick off the bioluminescence mission. '''
    if not user.messages.has_been_queued_or_delivered('MSG_SCI_BIOLUMINESCENCEa'):
        # Count only species exhibiting bioluminescence.
        species_counts =  user.species_count(only_subspecies_id=subspecies_types.plant.BIOLUMINESCENT)
        if species_counts[species_id] >= 1:
            message.send_later(ctx, user, 'MSG_SCI_BIOLUMINESCENCEa', utils.in_seconds(minutes=33))

# ======== OBELISK MISSION HELPERS ========

OBELISK_MISSIONS = ['MIS_AUDIO_MYSTERY01', 'MIS_AUDIO_MYSTERY02', 'MIS_AUDIO_MYSTERY03',
                    'MIS_AUDIO_MYSTERY04', 'MIS_AUDIO_MYSTERY05', 'MIS_AUDIO_MYSTERY06']
OBELISK_REGIONS  = ['RGN_AUDIO_MYSTERY01_ESTIMATE', 'RGN_AUDIO_MYSTERY02_ESTIMATE', 'RGN_AUDIO_MYSTERY03_ESTIMATE',
                    'RGN_AUDIO_MYSTERY04_ESTIMATE', 'RGN_AUDIO_MYSTERY05_ESTIMATE', 'RGN_AUDIO_MYSTERY06_ESTIMATE']

def get_done_obelisk_mission_count(user):
    # Count the number of completed obelisks missions.
    done_missions = user.missions.done(root_only=True)
    tagged_obelisks = 0
    for m in done_missions:
        if m.mission_definition in OBELISK_MISSIONS:
            tagged_obelisks += 1
    return tagged_obelisks

def get_untagged_obelisk_regions_at_mission_start(mission):
    """
    To allow our missions to return a consistent region_list over time, we search for
    obelisks that had not yet been detected when the given mission was started.
    """
    # Step 1: Assemble a list of mission_definitions for the obelisks tagged prior to the start of the given mission.
    done_missions_at_time = []
    done_missions = mission.user.missions.done(root_only=True)
    for m in done_missions:
        if m.mission_definition in OBELISK_MISSIONS and m.done_at <= mission.started_at:
            done_missions_at_time.append(m.mission_definition)

    # Step 2: Add a corresponding region for each mission NOT represented in the above list.
    untagged_obelisk_regions = []
    for i in range(len(OBELISK_MISSIONS)):
        if OBELISK_MISSIONS[i] not in done_missions_at_time:
            untagged_obelisk_regions.append(OBELISK_REGIONS[i])
    return untagged_obelisk_regions
