# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import Constants
from front.lib import utils

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def max_unarrived_targets(cls, user, rover):
        """
        A callback which returns the maximum number of unarrived at targets allowed to exist
        at a given time for this rover.
        :param user: The User who owns this rover.
        :param rover: The Rover instance.
        """
        if rover.can_use_feature('TGT_FEATURE_4_MOVES'):
            return 4
        elif rover.can_use_feature('TGT_FEATURE_3_MOVES'):
            return 3
        return 2

    @classmethod
    def min_target_seconds(cls, user, rover):
        """
        A callback which returns the minimum number of seconds of travel time between the last
        previously arrived at target and the next target being created.
        :param user: The User who owns this rover.
        :param rover: The Rover instance.
        """
        if rover.can_use_feature('TGT_FEATURE_FAST_MOVE'):
            return Constants.MIN_FAST_TARGET_SECONDS
        return Constants.MIN_TARGET_SECONDS

    @classmethod
    def max_target_seconds(cls, user, rover):
        """
        A callback which returns the maximum number of seconds of travel time between the last
        previously arrived at target and the next target being created.
        :param user: The User who owns this rover.
        :param rover: The Rover instance.
        """
        return Constants.MAX_TARGET_SECONDS

    @classmethod
    def max_travel_distance(cls, user, rover):
        """
        A callback which returns the maximum number of meters that this rover can travel
        between targets.
        :param user: The User who owns this rover.
        :param rover: The Rover instance.
        """
        return Constants.MAX_TRAVEL_DISTANCE
