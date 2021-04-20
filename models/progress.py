# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import models
from front.lib import db, urls
from front.models import chips, convert_to_region_descriptions
from front.callbacks import run_callback, run_all_callbacks_flatten_results, PROGRESS_CB

import logging
logger = logging.getLogger(__name__)

# Progress key constants.
class names(object):
    # This progress happens after all of the initial rover moves have happened.
    # e.g. the achieved_at time is the first moment the user could make a first move.
    PRO_USER_CREATED            = "PRO_USER_CREATED"
    PRO_SANDBOX_SAFETY_DISABLED = "PRO_SANDBOX_SAFETY_DISABLED"
    PRO_ROVER_WILL_BE_STUCK     = "PRO_ROVER_WILL_BE_STUCK"
    PRO_ROVER_STUCK             = "PRO_ROVER_STUCK"
    PRO_TAGGED_ONE_OBELISK      = "PRO_TAGGED_ONE_OBELISK"
    PRO_SHOW_GPS_REGION         = "PRO_SHOW_GPS_REGION"
    PRO_ENABLE_NE_REGION        = "PRO_ENABLE_NE_REGION"
    PRO_ENABLE_NORTH_REGION     = "PRO_ENABLE_NORTH_REGION"
    PRO_ENABLE_ALL_OBELISKS     = "PRO_ENABLE_ALL_OBELISKS"
    PRO_ENABLE_NW_REGION        = "PRO_ENABLE_NW_REGION"
    PRO_SHOW_LANDMARKS01        = "PRO_SHOW_LANDMARKS01"
    PRO_ENABLE_FWD_TO_EXOLEAKS  = "PRO_ENABLE_FWD_TO_EXOLEAKS"
    PRO_ROVER_WILL_GO_MISSING   = "PRO_ROVER_WILL_GO_MISSING"

# The list of progress key prefixes which are valid and allowed 'namespaces' for the client
# to create and reset progress keys in.
CLIENT_NAMESPACES = [
    "PRO_TUT"
]

def create_new_client_progress(ctx, user, key, value=""):
    """
    This creates a new Progress object and persists it. These are used to mark game progress
    for a particular user.
    This version of create_new_progress is expected to be used when creating progress keys
    from a client request. Only keys in valid namespaces will be allowed, otherwise an Exception
    will be raised.
    See CLIENT_NAMESPACES and create_new_progress for more documentation.
    """
    if not is_valid_client_key(key):
        raise Exception("Invalid client side progress key [%s]" % key)
    return create_new_progress(ctx, user, key, value=value)

def reset_client_progress(ctx, user, key):
    """
    Reset a progress key from the client. If the key is not in an allowed client 'namespace'
    or is not present in the progress collection, an Exception will be raised.
    If this function succeeds, the key will be deleted form the progress collection and
    a DELETE chip issued.
    """
    if not is_valid_client_key(key):
        raise Exception("Invalid client side progress key [%s]" % key)

    assert key in user.progress
    # Delete the key from the database.
    with db.conn(ctx) as ctx:
        db.run(ctx, "delete_progress", user_id=user.user_id, key=key)
    # And remove it from the progress collection and issue the DELETE chip.
    progress = user.progress[key]
    user.progress.delete_child(progress)
    progress.send_chips(ctx, user)

def is_valid_client_key(key):
    """ Returns True if the given key is allowed to be created or reset by the client. """
    return len([k for k in CLIENT_NAMESPACES if key.startswith(k)]) > 0

def create_new_progress(ctx, user, key, value="", achieved_at=None):
    """
    This creates a new Progress object and persists it. These are used to mark game progress
    for a particular user.
    NOTE: If the given key has already been added to this user, then this function will log
    a warning and return None indicating the progress was already achieved. This behavior exists so that if the ordering
    of when progress keys are added is changed on the live system to reflect for instance a change in the story, then
    if a user had already received a progress key in the previous version of the story it will not raise an exception here,
    hopefully allowing a smoother migration experience for existing users to the new story version.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param key: str The key for this progress. e.g. PRO_USER_CREATED.
    :param value: str Any additional payload associated with this progress key.
    Defaults to an empty string.
    :param achieved_at: int Number of seconds since user.epoch_now this progress was achieved.
    Defaults to 'now'.
    """
    # As we change the story script, sometimes we change the order when a progress key is being added
    # to the game. This guard is intended to make that migration more smooth. NOTE: It is critical
    # that a given PRO_ key always refers to the same 'progress concept'.
    if key in user.progress:
        logger.warning("Refusing to add exising progress key to user. [%s][%s]", key, user.user_id)
        return None

    if achieved_at is None:
        achieved_at = user.epoch_now
    params = {}
    params['key'] = key
    params['value'] = value
    params['achieved_at'] = achieved_at

    # Trigger the progress_will_be_achieved callback.
    run_callback(PROGRESS_CB, "progress_will_be_achieved", key, ctx=ctx, user=user)

    with db.conn(ctx) as ctx:
        # user_id is only used when creating the Progress in the database, it is not loaded
        # by chips as the user.progress collection takes care of assigning Progress to a User.
        db.run(ctx, "insert_progress", user_id=user.user_id, **params)
        p = user.progress.create_child(**params)
        p.send_chips(ctx, user)

    # Trigger the progress_achieved callback.
    run_callback(PROGRESS_CB, "progress_achieved", key, ctx=ctx, user=user, progress=p)

    return p

def run_region_list_callbacks(ctx, user):
    """ Run the progress_callbacks.region_list callback for every defined progress key in the
        progress_callbacks module and return the list of region descriptions that should be made
        available for the given users game state. """
    results = run_all_callbacks_flatten_results(PROGRESS_CB, 'region_list', ctx, user)
    return convert_to_region_descriptions(results)

class Progress(chips.Model, models.UserChild):
    """
    Holds the parameters for a single user progress key and value.
    """
    id_field = 'key'
    fields = frozenset(['value', 'achieved_at'])
    computed_fields = {
        'achieved_at_date'  : models.EpochDatetimeField('achieved_at')
    }

    # user_id is a database only field.
    def __init__(self, key, value, achieved_at, user_id=None):
        super(Progress, self).__init__(key=key, value=value, achieved_at=achieved_at)

    @property
    def user(self):
        # self.parent is user.progress, the parent of that is the User itself
        return self.parent.parent

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'reset':urls.client_progress_reset(self.key)
            }
        return struct
