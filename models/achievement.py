# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import pkg_resources

from front import models
from front.lib import db, urls
from front.data import load_json, schemas, assets
from front.models import chips
from front.callbacks import run_callback, get_all_callback_classes, callback_key_from_class, ACHIEVEMENT_CB

# The path relative to this package where the mission data is stored.
ACHIEVEMENT_DEFINITIONS = pkg_resources.resource_filename('front', 'data/achievement_definitions.json')

def award_new_achievement(ctx, user, achievement_key):
    """
    This marks a given achievement_key as achieved for this user.
    NOTE: This method currently just loads the achievement from the user's achievements collection
    and marks it achieved, which adds a record to the database. This pattern could be performed directly
    but this API exists to mirror the way other model objects are 'created'.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param achievement_key: str The achievement_key to award for this user. e.g. ACH_GAME_CREATE_USER.
    """
    achievement = user.achievements.get(achievement_key, None)
    if achievement is None:
        raise Exception("Unknown achievement_key %s" % achievement_key)
    # If this achievement has already been achieved, do nothing. This makes it safe to call
    # award_new_achievement more than once from different callback code locations if required.
    if achievement.was_achieved():
        return
    achievement.mark_achieved()

class Achievement(chips.Model, models.UserChild):
    """
    Holds the parameters for a single user achievement.
    """
    # These fields come from the achievement definitions JSON file.
    DEFINITION_FIELDS = frozenset(['title', 'description', 'type', 'secret', 'classified', 'icon'])

    id_field = 'achievement_key'
    fields = frozenset(['achieved_at', 'viewed_at']).union(DEFINITION_FIELDS)
    computed_fields = {
        'achieved_at_date'  : models.EpochDatetimeField('achieved_at'),
        'viewed_at_date'  : models.EpochDatetimeField('viewed_at')
    }

    def __init__(self, achievement_key, achieved_at, viewed_at):
        definition = get_achievement_definition(achievement_key)
        super(Achievement, self).__init__(achievement_key=achievement_key, achieved_at=achieved_at,
                                          viewed_at=viewed_at, **definition)

    @property
    def user(self):
        # self.parent is user.achievements, the parent of that is the User itself
        return self.parent.parent

    def is_secret(self):
        return self.secret == 1

    def is_classified(self):
        return self.classified == 1

    def was_achieved(self):
        return self.achieved_at != None

    def was_viewed(self):
        return self.viewed_at != None

    @property
    def url_icon(self):
        return assets.achievement_icon_url(self.icon)

    def mark_achieved(self):
        assert not self.was_achieved()
        run_callback(ACHIEVEMENT_CB, "will_be_achieved", self.achievement_key, ctx=self.ctx, user=self.user, achievement=self)

        # Mark the instance as achievd.
        self.achieved_at = self.user.epoch_now
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'insert_achievement', achievement_key=self.achievement_key, achieved_at=self.achieved_at,
                   user_id=self.user.user_id)

            # For any field which was hidden before being achieved, trigger the setter so that
            # the field is included in the MOD chip.
            info = run_callback(ACHIEVEMENT_CB, "unachieved_info", self.achievement_key, achievement=self)
            for field in info:
                setattr(self, field, getattr(self, field))

            # Issues a MOD for the achieved_at change.
            self.send_chips(ctx, self.user)

        run_callback(ACHIEVEMENT_CB, "was_achieved", self.achievement_key, ctx=self.ctx, user=self.user, achievement=self)

    def mark_viewed(self):
        assert self.was_achieved(), "Only achieved achievements can be marked viewed."
        with db.conn(self.ctx) as ctx:
            epoch_now = self.user.epoch_now
            db.run(ctx, "update_achievement_viewed_at", user_id=self.user.user_id,
                achievement_key=self.achievement_key, viewed_at=epoch_now)
            self.viewed_at = epoch_now # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'mark_viewed':urls.achievement_mark_viewed(self.achievement_key)
            }

        # If the achievement has not yet been achieved, ask the callback if any information should be hidden
        # or changed in the client data.
        if not self.was_achieved():
            info = run_callback(ACHIEVEMENT_CB, "unachieved_info", self.achievement_key, achievement=self)
            for key in info:
                if key in struct:
                    struct[key] = info[key]

        return struct

def get_special_date_achievement_keys():
    """ Return a list of acheivement_key strings for all of the 'special date' achievement types, sorted
        by the month and then day of the month of the special date. """
    # Avoid potential circular dependency
    from front.callbacks import achievement_callbacks
    classes = [c for c in get_all_callback_classes(ACHIEVEMENT_CB)
                       if issubclass(c, achievement_callbacks.SpecialDateAchievement)]
    # Sort the callbacks by special date month and day.
    classes = sorted(classes, key=lambda c: (c.MONTH, c.DAY_OF_MONTH))
    return [callback_key_from_class(c) for c in classes]

def get_achievement_definition(achievement_key):
    """
    Return the achievement definition as a dictionary for the given achievement id.

    :param achievement_key: str key for this achievment definition e.g ACH_TRAVEL_500M. Defined in
    achievement_definitions.json
    """
    return all_achievement_definitions()[achievement_key]

def all_achievement_definitions():
    """ Load the JSON file that contains the achievement definitions """
    return _g_achievement_definitions

_g_achievement_definitions = None
def init_module():
    global _g_achievement_definitions
    if _g_achievement_definitions is not None: return
    _g_achievement_definitions = load_json(ACHIEVEMENT_DEFINITIONS, schema=schemas.ACHIEVEMENT_DEFINITIONS)
