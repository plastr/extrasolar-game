# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import pkg_resources
from datetime import timedelta

from front import models, Constants
from front.lib import db, gametime
from front.models import chips
# from front.models import target as target_module
from front.data import load_json, schemas

import logging
logger = logging.getLogger(__name__)

# The path relative to this package where the sound data is stored.
TARGET_SOUNDS_DEFINITIONS = pkg_resources.resource_filename('front', 'data/target_sounds.json')

def create_new_target_sound(ctx, target, sound_key):
    """
    This creates a new TargetSound object for the given Target based on the sound key value provided.
    These keys are enumerated in the target_sounds.json file.
    If the target has not been arrived at, the ADD chip will be delivered at target.arrival_time
    otherwise the chip is sent immediately.
    Returns the newly created TargetSound object.

    :param sound_key: str, The unique key for the sound file data.
    """
    params = {}
    params['sound_key'] = sound_key

    # If the target has been arrived at send the ADD chip immediatly, otherwise send it in the future
    # to be delivered when the target is arrived at.
    with db.conn(ctx) as ctx:
        target_sound = target.sounds.create_child(**params)
        if target.has_been_arrived_at():
            target_sound.send_chips(ctx, target.user)
        else:
            deliver_at = target.arrival_time_date - timedelta(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)
            target_sound = chips.add_in_future(ctx, target.user, target.sounds, deliver_at=deliver_at, **params)

        # target_id is only used when creating the TargetSound in the database, it is not loaded
        # by chips as the target.sounds collection takes care of assigning a TargetSound to a Target.
        db.run(ctx, "insert_target_sound", user_id=target.user.user_id, target_id=target.target_id,
               sound_key=sound_key, created=gametime.now())
        return target_sound

class TargetSound(chips.Model, models.UserChild):
    id_field = 'sound_key'
    fields = frozenset(['title', 'video_id'])

    # user_id, target_id and created are database only fields.
    def __init__(self, sound_key, user_id=None, target_id=None, created=None):
        definition = get_target_sound_definition(sound_key)
        description = {}
        for field in self.fields:
            # Ignore comment fields.
            if field == 'comment':
                continue
            else:
                value = definition.get(field, None)
            description[field] = value
        super(TargetSound, self).__init__(sound_key=sound_key, **description)

    @property
    def target(self):
        # self.parent is target.sounds, the parent of that is the target itself
        return self.parent.parent

    @property
    def user(self):
        return self.target.user

def get_target_sound_definition(sound_key):
    """
    Return the target sound definition as a dictionary for the given sound key.

    :param sound_key: str key for this target sound definition e.g SND_ANIMAL001_ZONE. Defined in
    target_sounds.json
    """
    return all_target_sound_definitions()[sound_key]

def all_target_sound_definitions():
    """ Load the JSON file that contains the target sound definitions """
    return _g_sound_definitions

_g_sound_definitions = None
def init_module():
    global _g_sound_definitions
    if _g_sound_definitions is not None: return
    _g_sound_definitions = load_json(TARGET_SOUNDS_DEFINITIONS, schema=schemas.TARGET_SOUNDS_DEFINITIONS)
