# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import Constants
from front.lib import db, get_uuid, utils
from front.models.mission import make_mission_id

# TODO: Consider additional optimizations for these queries that would not require large
# portions of the gamestate to be built. If any query returns an element then we know
# we have some activity so we could then load all the collections we are interested in and
# so the activity detection on the Model objects and save subsequent queries.
def recent_activity_for_user(ctx, user, since, until):
    return RecentUserActivity(ctx, user, since, until)

def lure_activity_for_user(ctx, user):
    return LureUserActivity(user)

# When selecting species for activity, filter out species which are not yet fully available.
def _select_species(r, u):
    species = u.species[r['species_id']]
    if species.is_currently_delayed():
        return None
    else:
        return species

# Describes the activity data.
# Elements are:
#  activity_attr: UserActivity attribute name for these data.
#  query_name: database query name to load activity data.
#  time_attr: time attribute to sort data on.
#  selector: selector function to load data from database row and user object.
#  query_params: optional query parameters to pass to query_name.
ALERT_ACTIVITY_DATA = (
    ('unread_messages', 'select_unread_messages_for_user_since', 'sent_at',
        lambda r, u: u.messages[get_uuid(r['message_id'])], {}),
    ('unviewed_targets', 'select_unviewed_targets_for_user_since', 'arrival_time',
        lambda r, u: u.rovers[get_uuid(r['rover_id'])].targets[get_uuid(r['target_id'])], {}),
    ('unviewed_missions', 'select_unviewed_missions_for_user_since', 'started_at',
        lambda r, u: u.missions[make_mission_id(r['mission_definition'], r['specifics_hash'])], {}),
    # When looking for unviewed species, factor in the maximum amount of time that species data could be delayed
    # to the client (MAX_SPECIES_DELAY_MINUTES). Species that are not yet fully available are filtered/delayed for
    # notifying by the selector function but the 'detected_at' is still recorded as the earliest alert time for a
    # species so that in the situation where the species is the only activity to alert and the alert window is greater
    # than MAX_SPECIES_DELAY_MINUTES, the species will be alerted on as soon as possible.
    ('unviewed_species', 'select_unviewed_species_for_user_since', 'detected_at',
        _select_species, {'max_species_delay_seconds': utils.in_seconds(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)}),
    ('unviewed_achievements', 'select_unviewed_achievements_for_user_since', 'achieved_at',
        lambda r, u: u.achievements[r['achievement_key']], {})
)

class RecentUserActivity(object):
    """
    Holds the user activity data for the activity alert notifications.
    Will have every attribute listed as the first arguments in ACTIVITY and an 'earliest' field
    after constructed.
    NOTE: earliest can be None or a datetime object.
    :field unread_messages: All unread messages for this user within the activity alert window (between since and until)
    :field unviewed_targets: All unviewed targets for this user within the activity alert window (between since and until)
    :field unviewed_missions: All unviewed missions for this user within the activity alert window (between since and until)
    :field unviewed_species: All unviewed species for this user within the activity alert window (between since and until)
        NOTE: Any new species data delay time is factored into which species are considered unviewed. See ALERT_ACTIVITY_DATA.
    :field unviewed_achievements: All unviewed achievments for this user within the activity alert window (between since and until)
    :field earliest: datetime, earliest time for whichever activity alert data is the oldest. See ALERT_ACTIVITY_DATA.
        NOTE: Can be None if there is no activity data.
    """
    def __init__(self, ctx, user, since, until):
        # Convert the datetimes to seconds since user epoch.
        since_epoch = utils.seconds_between_datetimes(user.epoch, since)
        until_epoch = utils.seconds_between_datetimes(user.epoch, until)

        earliest = None
        # Gather all the unviewed data for this user between since and until
        # sorted by appropriate keys, newest first.
        for activity_attr, query_name, time_attr, selector, query_params in ALERT_ACTIVITY_DATA:
            unviewed = self._load_activity(ctx, user, since_epoch, until_epoch, query_name, selector, query_params)
            setattr(self, activity_attr, unviewed)

            # Determine which bit of activity is the oldest/earliest.
            if (len(unviewed) > 0):
                last = getattr(unviewed[-1], time_attr)
                if earliest is None:
                    earliest = last
                elif last < earliest:
                    earliest = last

        # Convert earliest from seconds since user.epoch back to a datetime.
        if earliest is not None:
            earliest = user.after_epoch_as_datetime(earliest)
        self.earliest = earliest

    def _load_activity(self, ctx, user, since, until, query_name, selector, query_params):
        unviewed = []
        with db.conn(ctx) as ctx:
            for row in db.rows(ctx, 'activity/' + query_name, user_id=user.user_id, since=since, until=until, **query_params):
                selected = selector(row, user)
                # The selector funcs can return None to indicate the given data is not yet ready.
                if selected is not None:
                    unviewed.append(selected)
        return unviewed

# The number of recent arrived at picture targets to load for the lure user activity.
RECENT_TARGETS_COUNT = 3
class LureUserActivity(object):
    """
    Holds the user activity data for the lure alert notifications.
    :field not_done_missions: All not done root missions for this user. Used in has_lure_activity.
    :field unread_messages: All unread messages for this user. Used in has_lure_activity.
    :field unviewed_species: All unviewed species for this user. NOT used in has_lure_activity.
    :field unviewed_achievements: All unviewed achievements for this user. NOT used in has_lure_activity.
    :field recent_targets: RECENT_TARGETS_COUNT number of recent targets for this user. NOT used in has_lure_activity.
    :field unviewed_targets_count: int, Number of unviewed targets in the recent_targets list. Used in has_lure_activity.
    """
    def __init__(self, user):
        self.not_done_missions = user.missions.not_done(root_only=True)        
        self.unread_messages = user.messages.unread()
        self.unviewed_species = user.species.unviewed()
        self.unviewed_achievements = user.achievements.unviewed_and_achieved()
        # Find at most RECENT_TARGETS_COUNT most recent targets for the user, whether viewed or not. Also count how 
        # many of those targets are unviewed.
        self.recent_targets = []
        self.unviewed_targets_count = 0
        for index, t in enumerate(user.rovers.iter_processed_pictures(newest_first=True)):
            self.recent_targets.append(t)
            if not t.was_viewed():
                self.unviewed_targets_count += 1
            if index + 1 == RECENT_TARGETS_COUNT:
                break

    def has_lure_activity(self):
        """ If returns True, then the lure email will be sent for this user. """
        # Currently only interested in any unviewed recent targets, not completed missions, and unread messages.
        return self.unviewed_targets_count + len(self.not_done_missions) + len(self.unread_messages) > 0
