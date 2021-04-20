# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import datetime

from front.lib import utils, gametime
from front.models import message as message_module

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def will_be_achieved(cls, ctx, user, achievement):
        """
        A callback which is called when a given achievement is about to be first achieved by the user.
        """
        return

    @classmethod
    def was_achieved(cls, ctx, user, achievement):
        """
        A callback which is called when a given achievement is about to be first achieved by the user.
        """
        return

    @classmethod
    def unachieved_info(cls, achievement):
        """
        If this achievement is secret, certain information will not be shown to the client until the
        achievement is achieved. Returns the placeholder overrides in a dict.
        """
        if achievement.is_secret():
            return {
               'description': utils.tr("No description available."),
               'icon': "ACH_ICON_NOT_ACHIEVED_SECRET"
            }
        else:
            return {
               'icon': "ACH_ICON_NOT_ACHIEVED"
            }

    @classmethod
    def target_created(cls, ctx, user, achievement, target):
        """
        A callback which is called on each achievement which has not been achieved whenever a target is created.
        If True is returned, the achivement is marked achieved.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param achievement: The Achivement object.
        :param target: The target that was created.
        """
        return False

    @classmethod
    def target_en_route(cls, ctx, user, achievement, target):
        """
        A callback which is called when a rover has begun to move towards the given target.
        If True is returned, the achivement is marked achieved.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param achievement: The Achivement object.
        :param target: The Target which the user's rover has begun to move towards.
        """
        return False

    @classmethod
    def arrived_at_target(cls, ctx, user, achievement, target):
        """
        A callback which is called when a rover has arrived at the given target.
        If True is returned, the achivement is marked achieved.
        :param ctx: The database context.
        :param user: The User to whom this target belongs.
        :param achievement: The Achivement object.
        :param target: The Target which the user's rover has arrived at.
        """
        return False

    @classmethod
    def species_identified(cls, ctx, user, achievement, target, identified, subspecies):
        """
        A callback which is called on each achievement which has not been achieved whenever a species identification
        occurs. If True is returned, the achivement is marked achieved.
        :param ctx: The database context.
        :param user: The User who owns this mission.
        :param achievement: The Achivement object.
        :param target: The target where the identification happened.
        :param identified: The Species which was detected/identified.
        :param subspecies: The set of subspecies_ids that were detected/identified (at most 1 currently).
        """
        return False

## TravelAchievements. When certain distance thresholds are reached with the rover, award
# a badge and send a message.
class TravelAchievement(BaseCallbacks):
    # Set this to the distance at which the badge should be awarded.
    DISTANCE_THRESHOLD = None
    # Set this to the MSG_ type string if a message should be sent when the achievement is awarded.
    ACHIEVEMENT_MESSAGE = None

    @classmethod
    def arrived_at_target(cls, ctx, user, achievement, target):
        # Double-check distance to make sure the target wasn't neutered.
        return user.total_distance_traveled() >= cls.DISTANCE_THRESHOLD

    @classmethod
    def was_achieved(cls, ctx, user, achievement):
        if cls.ACHIEVEMENT_MESSAGE is not None:
            # Send a corresponding message from the science team.
            message_module.send_now(ctx, user, cls.ACHIEVEMENT_MESSAGE)

class ACH_TRAVEL_300M_Callbacks(TravelAchievement):
    DISTANCE_THRESHOLD = 300.0
    ACHIEVEMENT_MESSAGE = 'MSG_ACH_TRAVEL_300M'

class ACH_TRAVEL_SPIRIT_Callbacks(TravelAchievement):
    DISTANCE_THRESHOLD = 7730.0
    ACHIEVEMENT_MESSAGE = 'MSG_ACH_TRAVEL_SPIRIT'

class ACH_TRAVEL_VOYAGER1_Callbacks(TravelAchievement):
    DISTANCE_THRESHOLD = 17043.0
    ACHIEVEMENT_MESSAGE = 'MSG_ACH_TRAVEL_VOYAGER1'

## SpecialDateAchievement. Award badges when photos are taken on special dates.
# Note that we use a time window larger than 24 hours to accommodate multiple time zones.
class SpecialDateAchievement(BaseCallbacks):
    # Set these values for the date of interest.
    MONTH = None
    DAY_OF_MONTH = None
    # Set this to the MSG_ type string if a message should be sent when the achievement is awarded.
    ACHIEVEMENT_MESSAGE = None

    @classmethod
    def arrived_at_target(cls, ctx, user, achievement, target):
        # We consider the date a match between 4:00am UTC and midnight PST (8:00am UTC the following day).
        now = gametime.now()
        window_start = datetime.datetime(now.year, cls.MONTH, cls.DAY_OF_MONTH, 4, 0, 0, 0)
        # Account for time windows that span a change of year.
        if now < window_start:
            window_start = datetime.datetime(now.year-1, cls.MONTH, cls.DAY_OF_MONTH, 4, 0, 0, 0)
        window_end   = window_start + datetime.timedelta(hours=28)
        return now >= window_start and now <= window_end

    @classmethod
    def was_achieved(cls, ctx, user, achievement):
        if cls.ACHIEVEMENT_MESSAGE is not None:
            # Send a corresponding message from the science team.
            message_module.send_now(ctx, user, cls.ACHIEVEMENT_MESSAGE)

class ACH_DATE_0215_Callbacks(SpecialDateAchievement):
    MONTH = 2
    DAY_OF_MONTH = 15

class ACH_DATE_0623_Callbacks(SpecialDateAchievement):
    MONTH = 6
    DAY_OF_MONTH = 23

class ACH_DATE_1017_Callbacks(SpecialDateAchievement):
    MONTH = 10
    DAY_OF_MONTH = 17

class ACH_DATE_1109_Callbacks(SpecialDateAchievement):
    MONTH = 11
    DAY_OF_MONTH = 9

class ACH_DATE_1225_Callbacks(SpecialDateAchievement):
    MONTH = 12
    DAY_OF_MONTH = 25

# Award a badge the first time a player takes a panorama photo.
class ACH_PHOTO_PANO_Callbacks(BaseCallbacks):
    @classmethod
    def arrived_at_target(cls, ctx, user, achievement, target):
        return target.is_panorama()
            
# Award a badge the first time a player takes an infrared photo.
class ACH_PHOTO_IR_Callbacks(BaseCallbacks):
    @classmethod
    def arrived_at_target(cls, ctx, user, achievement, target):
        return target.is_infrared()

# Award a badge the first time a player tags 3 unique species in the same photo.
class ACH_SPECIES_TAG_3_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, achievement, target, identified, subspecies):
        species_count = target.species_count()
        # If fewer than 3 unique species were identified, badge not achieved.
        if len(species_count) < 3:
            return False
        # Now count the number of unique organic species.
        organics = []
        for s_id in species_count.keys():
            species = user.species.get(s_id)
            if species is not None and species.is_organic():
                organics.append(species)
        if len(organics) >= 3 and not user.messages.has_been_queued_or_delivered('MSG_ACH_SPECIES_TAG_3'):
            # Find the species with the most amount of time left until fully available. This will be 0 if
            # all species are fully available.
            longest_delay = max(organics, key=lambda s: s.delayed_seconds_remaining)
            delayed_seconds_remaining = longest_delay.delayed_seconds_remaining
            # If some of the species identified are not yet fully available, delay the delivery of the corresponding
            # message. The achievement will be marked achieved by the was_delivered callback in message_callbacks.
            if delayed_seconds_remaining > 0:
                message_module.send_later(ctx, user, 'MSG_ACH_SPECIES_TAG_3', delayed_seconds_remaining)
            # Otherwise, deliver the message immediately as all species data is fully available.
            else:
                message_module.send_now(ctx, user, 'MSG_ACH_SPECIES_TAG_3')
            # Achievement is marked achieved inside of the was_delivered message_callback
            return False
        else:
            return False

# Award a badge when the player tags their 5th unique animal.
class ACH_SPECIES_ANIMAL_5_Callbacks(BaseCallbacks):
    @classmethod
    def species_identified(cls, ctx, user, achievement, target, identified, subspecies):
        animals = user.species.animals()
        # If fewer than 5 animal species have been identified, badge not achieved.
        if len(animals) < 5:
            return False
        if not user.messages.has_been_queued_or_delivered('MSG_ACH_SPECIES_ANIMAL_5'):
            # Find the species with the most amount of time left until fully available. This will be 0 if
            # all species are fully available.
            longest_delay = max(animals, key=lambda s: s.delayed_seconds_remaining)
            delayed_seconds_remaining = longest_delay.delayed_seconds_remaining
            # If some of the species identified are not yet fully available, delay the delivery of the corresponding
            # message. The achievement will be marked achieved by the was_delivered callback in message_callbacks.
            if delayed_seconds_remaining > 0:
                message_module.send_later(ctx, user, 'MSG_ACH_SPECIES_ANIMAL_5', delayed_seconds_remaining)
            # Otherwise, deliver the message immediately as all species data is fully available.
            else:
                message_module.send_now(ctx, user, 'MSG_ACH_SPECIES_ANIMAL_5')
        # Achievement is marked achieved inside of the was_delivered message_callback
        return False
