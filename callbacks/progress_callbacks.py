# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.

import math
from front import Constants, InitialMessages
from front.lib import utils
from front.lib import planet as planet_module
from front.data import scene
from front.models import region, convert_to_region_descriptions
from front.models import progress as progress_module
from front.models import message as message_module
from front.models import mission as mission_module
from front.models import target as target_module
from front.callbacks import callback_key_from_class, run_all_callbacks_flatten_results, PROGRESS_CB

# Locations for the first rover and lander for a new user.
ROVER01_NORTH  = {'lat':6.24058154685141, 'lng':-109.4141514504012, 'yaw':0.0}
ROVER01_EAST   = {'lat':6.24055455369857, 'lng':-109.4140929227886, 'yaw':1.5708}
ROVER01_SOUTH  = {'lat':6.24049972923687, 'lng':-109.4140877988633, 'yaw':3.1416}
ROVER01_WEST   = {'lat':6.24046490213549, 'lng':-109.4141470479545, 'yaw':4.7124}

SECONDS_BETWEEN_STARTING_TARGETS = utils.in_seconds(minutes=30) # Minutes between each of the 4 initial targets.

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass
    NO_OVERRIDE = ['progress_achieved', 'progress_will_be_achieved', 'region_list']

    @classmethod
    def region_list_achieved(cls, ctx, user):
        """
        A callback which returns any Regions that should be available in this User's current gamestate,
        after this specific progress key is achieved.
        See mission_callbacks.region_list for providing mission specific regions.
        See region_list for a full description of the return value.
        """
        return []

    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        """
        A callback which returns any Regions that should be available in this User's current gamestate,
        before this specific progress key is achieved.
        See mission_callbacks.region_list for providing mission specific regions.
        See region_list for a full description of the return value.
        """
        return []

    @classmethod
    def will_be_achieved(cls, ctx, user):
        """
        A callback which is called when a given progress key is about to be first achieved by the user.
        In progress specific subclasses, this is the method to override to perform actions in
        response to this event.
        """
        return

    @classmethod
    def was_achieved(cls, ctx, user, progress):
        """
        A callback which is called when a given progress key is about to be first achieved by the user.
        In progress specific subclasses, this is the method to override to perform actions in
        response to this event.
        :param progress: The Progress object just achieved.
        """
        return

    ## Do not override these methods, only meant to be called externally.
    @classmethod
    def progress_will_be_achieved(cls, ctx, user):
        """
        A callback which is called when a given progress key is about to be first achieved by the user.
        This method is NOT meant to be overriden, use will_be_achieved.
        """
        # The ADD chips for region_list_achieved regions need to be issued before the progress key
        # is available as that key is used by the region's lazy loader to add that region to the
        # regions collection so it would already have been added if this was called after
        # the progress had been achieved.
        for region_id, constructor_args in convert_to_region_descriptions(cls.region_list_achieved(ctx, user)):
            region.add_region_to_user(ctx, user, region_id, **constructor_args)
        # The DEL chips for region_list_not_achieved regions need to be issued before the progress key
        # is available as that key is used by the region's lazy loader to not provide that region to the
        # regions collection so it would already have been deleted if this was called after
        # the progress had been achieved.
        for region_id, constructor_args in convert_to_region_descriptions(cls.region_list_not_achieved(ctx, user)):
            user.regions.delete_by_id(region_id)

        cls.will_be_achieved(ctx, user)

    @classmethod
    def progress_achieved(cls, ctx, user, progress):
        """
        A callback which is called when a given progress key is first achieved by the user.
        This method is NOT meant to be overriden, use was_achieved.
        :param progress: The Progress object just achieved.
        """
        cls.was_achieved(ctx, user, progress)

    @classmethod
    def region_list(cls, ctx, user):
        """
        A callback which returns any Regions that should be available in this User's current gamestate.
        See mission_callbacks.region_list for providing mission specific regions.
        The return value is a list object, which contains either a tuple mapping between the region_id to add
        to the gamestate and optionally any data to set in that Region when it is constructed, e.g.
        setting the center value of a waypoint based on gamestate data or just the region_id if
        there is no construction data.
        e.g. [region_id1, (region_id2, {construction_args})]
        This method is NOT meant to be overriden, use region_list_achieved or region_list_not_achieved.
        """
        if user.progress.has_achieved(cls.progress_key()):
            return cls.region_list_achieved(ctx, user)
        # PRO_USER_CREATED acts as a guard for the initial state of the user. If the user is currently
        # being created, do not provide the region_list_not_achieved regions yet, so that they can be
        # ADD'd propery by PRO_USER_CREATED_Callbacks.will_be_achieved
        elif user.progress.has_achieved(progress_module.names.PRO_USER_CREATED):
            return cls.region_list_not_achieved(ctx, user)
        return []

    @classmethod
    def progress_key(cls):
        """ Return the progress key e.g. PRO_KEY_NAME, for this specific callback.
            This is derived from the classname when not supplied to the callback method directly. """
        # Derive the progress key from the class name.
        return callback_key_from_class(cls)

## Progress specific event callback definitions.
class PRO_USER_CREATED_Callbacks(BaseCallbacks):
    @classmethod
    def will_be_achieved(cls, ctx, user):
        # Just before the user is fully created, issue proper ADD chips for all of the known
        # region_list_not_achieved regions. This code only runs once, right before the user
        # is created the first time, to emulate the correct behavior when any model is
        # first 'created' (e.g. issuing the ADD chip.)
        # See BaseCallbacks.region_list for the other part that makes this posssible.
        results = run_all_callbacks_flatten_results(PROGRESS_CB, 'region_list_not_achieved', ctx, user)
        region_descriptions = convert_to_region_descriptions(results)
        for region_id, constructor_args in region_descriptions:
            region.add_region_to_user(ctx, user, region_id, **constructor_args)

    @classmethod
    def region_list_achieved(cls, ctx, user):
        # For episode 1, always return the ISLAND region.
        # NOTE: Eventually this will require a more sophisticated filter based on whatever
        # progress key is used to indicate the user is onto episode 2.
        return ['RGN_ISLAND01']

class PRO_TUT_01_STEP_09_Callbacks(BaseCallbacks):
    @classmethod
    def was_achieved(cls, ctx, user, progress):
        if user.messages.by_type('MSG_SIMULATOR_DONE') is None:
            user.missions.get_only_by_definition("MIS_SIMULATORa").mark_done()

class PRO_TUT_04_Callbacks(BaseCallbacks):
    @classmethod
    def was_achieved(cls, ctx, user, progress):
        # When debugging, it's possible to set this progress key more than once.  Prevent
        # duplicate message sending.
        if user.messages.by_type('MSG_SIMULATOR_DONE') is None:
            user.missions.get_only_by_definition("MIS_SIMULATORb").mark_done()
            user.missions.get_only_by_definition("MIS_SIMULATOR").mark_done()
            # When the last part of the simulator is complete, send a message to acknowledge it.
            message_module.send_now(ctx, user, 'MSG_SIMULATOR_DONE')
            # Intro to your first rover's features.
            message_module.send_later(ctx, user, 'MSG_ROVER_INTRO01', utils.in_seconds(minutes=1))
            # Send introduction from our exobiologist Jane.
            message_module.send_later(ctx, user, 'MSG_JANE_INTRO', utils.in_seconds(minutes=InitialMessages.MSG_JANE_INTRO_DELAY_MINUES))
            # Kryptex: Thanks for your help.
            message_module.send_later(ctx, user, 'MSG_KTHANKS', utils.in_seconds(minutes=InitialMessages.MSG_KTHANKS_DELAY_MINUES))
            # Mission: Calibrate the lander.
            rovers = user.rovers.active()
            assert(len(rovers) == 1)
            mission_module.add_mission(ctx, user, "MIS_TUT01", rover=rovers[0])

            # Calculate a recent time at which mid-day occurred.
            hours_since_midday = planet_module.hours_since_solar_event(0.5)
            # Create targets close to this time, but within the window of EPOCH_START_HOURS.
            photo_target_time = math.floor((Constants.EPOCH_START_HOURS - hours_since_midday)*60*60 - SECONDS_BETWEEN_STARTING_TARGETS*5)

            active_rovers = user.rovers.active()
            assert len(active_rovers) is 1
            r = user.rovers.active()[0]

            # At a slight distance from the lander, add 4 photos, one in each compass direction.
            target_module.create_new_target(ctx, r, scene=scene.INITIAL_NORTH,
                start_time=photo_target_time, arrival_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS,
                lat=ROVER01_NORTH['lat'], lng=ROVER01_NORTH['lng'], yaw=ROVER01_NORTH['yaw'],
                picture=1, processed=1)

            target_module.create_new_target(ctx, r, scene=scene.INITIAL_EAST,
                start_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS, arrival_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS*2,
                lat=ROVER01_EAST['lat'], lng=ROVER01_EAST['lng'], yaw=ROVER01_EAST['yaw'],
                picture=1, processed=1)

            target_module.create_new_target(ctx, r, scene=scene.INITIAL_SOUTH,
                start_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS*2, arrival_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS*3,
                lat=ROVER01_SOUTH['lat'], lng=ROVER01_SOUTH['lng'], yaw=ROVER01_SOUTH['yaw'],
                picture=1, processed=1)

            target_module.create_new_target(ctx, r, scene=scene.INITIAL_WEST,
                start_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS*3, arrival_time=photo_target_time+SECONDS_BETWEEN_STARTING_TARGETS*4,
                lat=ROVER01_WEST['lat'], lng=ROVER01_WEST['lng'], yaw=ROVER01_WEST['yaw'],
                picture=1, processed=1)

class PRO_SANDBOX_SAFETY_DISABLED_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_SANDBOX']

class PRO_ROVER_STUCK_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_SANDBAR']

class PRO_TAGGED_ONE_OBELISK_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_AUDIO_MYSTERY01_CONSTRAINT']

class PRO_SHOW_GPS_REGION_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_achieved(cls, ctx, user):
        return ['RGN_GPS_ICON']

class PRO_ENABLE_NE_REGION_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_NE_CONSTRAINT']

class PRO_ENABLE_NORTH_REGION_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_NORTH_CONSTRAINT']

class PRO_ENABLE_ALL_OBELISKS_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_OBELISK_CONSTRAINT']

class PRO_ENABLE_NW_REGION_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_not_achieved(cls, ctx, user):
        return ['RGN_NW_CONSTRAINT']

class PRO_SHOW_LANDMARKS01_Callbacks(BaseCallbacks):
    @classmethod
    def region_list_achieved(cls, ctx, user):
        return ['RGN_LANDMARK_N_SUMMIT', 'RGN_LANDMARK_S_SUMMIT', 'RGN_LANDMARK_SW_PENINSULA', 'RGN_LANDMARK01', 'RGN_LANDMARK02']
