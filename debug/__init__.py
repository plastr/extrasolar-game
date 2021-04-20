# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, shutil, subprocess, pkg_resources, re
from datetime import timedelta

from front import read_config, Constants
from front.lib import db, get_uuid, gametime, xjson, utils
from front.backend import deferred
from front.data import scene
from front.models import user, chips

# We activate chips to this many seconds into the future in case the client's last_seen_chip_time
# and the server's gametime.now() are identical in which case the chips would not be seen
# if the fetch came in at the same time and also in case a fetch chips is happening during
# the activation process in which case the activated chips could get lost if other chips
# come back from the fetch and increment last_seen_chip_time
CHIP_ACTIVATION_DELTA = 1

# Relative to CHIP_ACTIVATION_DELTA we send user.epoch changes this number of microseconds
# before the chip activation time to be sure that user.epoch MODs are applied before any
# activated chips on the client.
EPOCH_ACTIVATION_DELTA = 100

DEVELOPMENT_DEPLOYMENT = "development"
RENDERER_PATH = pkg_resources.resource_filename('front', '../../renderer')
RENDERER_CMD = os.path.join(RENDERER_PATH, "renderer")
# Where the route json files are located.
ROUTES_DIR = os.path.join(os.path.dirname(__file__), 'routes')

# Test image species locations.
class rects(object):
    # MANMADE
    SPC_MANMADE_TOO_FAR    = {"xmin": 0.00, "ymin": 0.51, "xmax": 0.12, "ymax": 0.62}
    SPC_LANDER01           = {"xmin": 0.13, "ymin": 0.51, "xmax": 0.24, "ymax": 0.62}
    SPC_ROVER01            = {"xmin": 0.26, "ymin": 0.51, "xmax": 0.37, "ymax": 0.62}
    SPC_ROVER02            = {"xmin": 0.38, "ymin": 0.51, "xmax": 0.49, "ymax": 0.62}
    SPC_ROVER_DISASSEMBLED = {"xmin": 0.51, "ymin": 0.51, "xmax": 0.62, "ymax": 0.62}
    SPC_MANMADE005         = {"xmin": 0.63, "ymin": 0.51, "xmax": 0.74, "ymax": 0.62}
    SPC_MANMADE006         = {"xmin": 0.76, "ymin": 0.51, "xmax": 0.87, "ymax": 0.62}
    SPC_MANMADE007         = {"xmin": 0.88, "ymin": 0.51, "xmax": 0.99, "ymax": 0.62}

    # ALIEN ORIGIN
    SPC_UNKNOWN_ORIGIN_TOO_FAR = {"xmin": 0.00, "ymin": 0.76, "xmax": 0.12, "ymax": 0.87}
    SPC_ARTIFACT01             = {"xmin": 0.13, "ymin": 0.76, "xmax": 0.24, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN02       = {"xmin": 0.26, "ymin": 0.76, "xmax": 0.37, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN02_SUB01 = {"xmin": 0.38, "ymin": 0.76, "xmax": 0.49, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN02_SUB02 = {"xmin": 0.51, "ymin": 0.76, "xmax": 0.62, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN02_SUB03 = {"xmin": 0.63, "ymin": 0.76, "xmax": 0.74, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN02_SUB04 = {"xmin": 0.76, "ymin": 0.76, "xmax": 0.87, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN02_SUB05 = {"xmin": 0.88, "ymin": 0.76, "xmax": 0.99, "ymax": 0.87}
    SPC_UNKNOWN_ORIGIN08       = {"xmin": 0.01, "ymin": 0.88, "xmax": 0.12, "ymax": 0.99}
    SPC_UNKNOWN_ORIGIN09       = {"xmin": 0.13, "ymin": 0.88, "xmax": 0.24, "ymax": 0.99}
    SPC_UNKNOWN_ORIGIN10       = {"xmin": 0.26, "ymin": 0.88, "xmax": 0.37, "ymax": 0.99}

    # PLANT
    SPC_PLANT_TOO_FAR   = {"xmin": 0.00, "ymin": 0.01, "xmax": 0.12, "ymax": 0.12}
    SPC_PLANT001        = {"xmin": 0.13, "ymin": 0.01, "xmax": 0.24, "ymax": 0.12}
    SPC_PLANT002        = {"xmin": 0.26, "ymin": 0.01, "xmax": 0.37, "ymax": 0.12}
    SPC_PLANT003        = {"xmin": 0.38, "ymin": 0.01, "xmax": 0.49, "ymax": 0.12}
    SPC_PLANT004        = {"xmin": 0.51, "ymin": 0.01, "xmax": 0.62, "ymax": 0.12}
    SPC_PLANT005        = {"xmin": 0.63, "ymin": 0.01, "xmax": 0.74, "ymax": 0.12}
    SPC_PLANT006        = {"xmin": 0.76, "ymin": 0.01, "xmax": 0.87, "ymax": 0.12}
    SPC_PLANT007        = {"xmin": 0.88, "ymin": 0.01, "xmax": 0.99, "ymax": 0.12}
    SPC_PLANT008        = {"xmin": 0.01, "ymin": 0.13, "xmax": 0.12, "ymax": 0.24}
    SPC_PLANT009        = {"xmin": 0.13, "ymin": 0.13, "xmax": 0.24, "ymax": 0.24}
    SPC_PLANT010        = {"xmin": 0.26, "ymin": 0.13, "xmax": 0.37, "ymax": 0.24}
    SPC_PLANT011        = {"xmin": 0.38, "ymin": 0.13, "xmax": 0.49, "ymax": 0.24}
    SPC_PLANT012        = {"xmin": 0.51, "ymin": 0.13, "xmax": 0.62, "ymax": 0.24}
    SPC_PLANT013        = {"xmin": 0.63, "ymin": 0.13, "xmax": 0.74, "ymax": 0.24}
    SPC_PLANT014        = {"xmin": 0.76, "ymin": 0.13, "xmax": 0.87, "ymax": 0.24}
    SPC_PLANT015        = {"xmin": 0.88, "ymin": 0.13, "xmax": 0.99, "ymax": 0.24}
    SPC_PLANT016        = {"xmin": 0.01, "ymin": 0.26, "xmax": 0.12, "ymax": 0.37}
    SPC_PLANT65535      = {"xmin": 0.19, "ymin": 0.26, "xmax": 0.24, "ymax": 0.31}
    SPC_PLANT001_SUB01  = {"xmin": 0.88, "ymin": 0.26, "xmax": 0.93, "ymax": 0.31}
    SPC_PLANT001_SUB02  = {"xmin": 0.94, "ymin": 0.26, "xmax": 0.99, "ymax": 0.31}
    SPC_PLANT001_SUB03  = {"xmin": 0.88, "ymin": 0.32, "xmax": 0.93, "ymax": 0.37}
    SPC_PLANT001_SUB04  = {"xmin": 0.94, "ymin": 0.32, "xmax": 0.99, "ymax": 0.37}
    
    # SCIENCE MISSION TESTS
    SPC_PLANT021        = {"xmin": 0.76, "ymin": 0.26, "xmax": 0.81, "ymax": 0.31}
    SPC_PLANT024        = {"xmin": 0.82, "ymin": 0.26, "xmax": 0.87, "ymax": 0.31}
    SPC_PLANT021_SUB04  = {"xmin": 0.76, "ymin": 0.32, "xmax": 0.81, "ymax": 0.37}
    SPC_PLANT024_SUB04  = {"xmin": 0.82, "ymin": 0.32, "xmax": 0.87, "ymax": 0.37}
    SPC_PLANT032        = {"xmin": 0.63, "ymin": 0.26, "xmax": 0.68, "ymax": 0.31}
    SPC_PLANT032_SUB01  = {"xmin": 0.69, "ymin": 0.26, "xmax": 0.74, "ymax": 0.31}
    SPC_PLANT032_SUB02  = {"xmin": 0.63, "ymin": 0.32, "xmax": 0.68, "ymax": 0.37}
    SPC_PLANT032_SUB03  = {"xmin": 0.69, "ymin": 0.32, "xmax": 0.74, "ymax": 0.37}
    SPC_PLANT014        = {"xmin": 0.51, "ymin": 0.26, "xmax": 0.56, "ymax": 0.31}
    SPC_PLANT028        = {"xmin": 0.57, "ymin": 0.26, "xmax": 0.62, "ymax": 0.31}
    SPC_PLANT014_SUB04  = {"xmin": 0.51, "ymin": 0.32, "xmax": 0.56, "ymax": 0.37}
    SPC_PLANT028_SUB03  = {"xmin": 0.57, "ymin": 0.32, "xmax": 0.62, "ymax": 0.37}
    SPC_PLANT033        = {"xmin": 0.44, "ymin": 0.26, "xmax": 0.49, "ymax": 0.31}
    SPC_PLANT034        = {"xmin": 0.44, "ymin": 0.32, "xmax": 0.49, "ymax": 0.37}
    SPC_PLANT015        = {"xmin": 0.26, "ymin": 0.26, "xmax": 0.31, "ymax": 0.31}
    SPC_PLANT015_SUB05  = {"xmin": 0.26, "ymin": 0.32, "xmax": 0.31, "ymax": 0.37}
    SPC_PLANT022        = {"xmin": 0.32, "ymin": 0.26, "xmax": 0.37, "ymax": 0.31}
    SPC_PLANT022_SUB05  = {"xmin": 0.32, "ymin": 0.32, "xmax": 0.37, "ymax": 0.37}
    SPC_PLANT031        = {"xmin": 0.38, "ymin": 0.26, "xmax": 0.43, "ymax": 0.31}
    SPC_PLANT031_SUB05  = {"xmin": 0.38, "ymin": 0.32, "xmax": 0.43, "ymax": 0.37}

    # ANIMAL
    SPC_ANIMAL_TOO_FAR  = {"xmin": 0.00, "ymin": 0.38, "xmax": 0.12, "ymax": 0.49}
    SPC_ANIMAL001       = {"xmin": 0.13, "ymin": 0.38, "xmax": 0.24, "ymax": 0.49}
    SPC_ANIMAL002       = {"xmin": 0.26, "ymin": 0.38, "xmax": 0.37, "ymax": 0.49}
    SPC_ANIMAL003       = {"xmin": 0.38, "ymin": 0.38, "xmax": 0.49, "ymax": 0.49}
    SPC_ANIMAL004       = {"xmin": 0.51, "ymin": 0.38, "xmax": 0.62, "ymax": 0.49}
    SPC_ANIMAL005       = {"xmin": 0.63, "ymin": 0.38, "xmax": 0.74, "ymax": 0.49}
    SPC_ANIMAL006       = {"xmin": 0.76, "ymin": 0.38, "xmax": 0.81, "ymax": 0.43}
    SPC_ANIMAL007       = {"xmin": 0.76, "ymin": 0.44, "xmax": 0.81, "ymax": 0.49}
    SPC_ANIMAL65535     = {"xmin": 0.94, "ymin": 0.38, "xmax": 0.99, "ymax": 0.43}
    
    # NO SPECIES e.g. black background color only
    NO_SPECIES          = {"xmin": 0.88, "ymin": 0.88, "xmax": 0.99, "ymax": 0.99}
    
    # A selection region that wraps around the seam of a 360-degree panorama.
    SPC_PLANT008_WRAP   = {"xmin": 0.99, "ymin": 0.13, "xmax": 1.12, "ymax": 0.24}

    # Collections.
    PLANTS = [
        'SPC_PLANT001', 'SPC_PLANT002', 'SPC_PLANT003', 'SPC_PLANT004', 'SPC_PLANT005', 'SPC_PLANT006', 
        'SPC_PLANT007', 'SPC_PLANT008', 'SPC_PLANT009', 'SPC_PLANT010', 'SPC_PLANT011', 'SPC_PLANT012',
        'SPC_PLANT013', 'SPC_PLANT014', 'SPC_PLANT015', 'SPC_PLANT016', 'SPC_PLANT017'
    ]
    ANIMALS = [
        'SPC_ANIMAL001', 'SPC_ANIMAL002', 'SPC_ANIMAL003', 'SPC_ANIMAL004', 'SPC_ANIMAL005', 'SPC_ANIMAL006'
    ]

    # Special rects for testing.
    TWO_PLANTS              = {"xmin": 0.13, "ymin": 0.01, "xmax": 0.32, "ymax": 0.12}
    ANIMAL_AND_SOME_MANMADE = {"xmin": 0.13, "ymin": 0.38, "xmax": 0.24, "ymax": 0.60}

    @classmethod
    def for_species_key(cls, species_key):
        try:
            rect = getattr(cls, species_key)
        except AttributeError:
            raise Exception("Unknown species_id when mapping to rect data [%s]" % species_key)
        return rect

# Route path names.
class routes(object):
    FASTEST_STORY_ROVER1 = "fastest_story_rover1.json"
    FASTEST_STORY_ROVER2 = "fastest_story_rover2.json"
    FASTEST_STORY_ROVER3 = "fastest_story_rover3.json"

    @classmethod
    def struct(cls, route_file_name):
        with open(os.path.join(ROUTES_DIR, route_file_name)) as f:
            return xjson.load(f)

def get_ctx(deployment=DEVELOPMENT_DEPLOYMENT):
    """ Return an object compatible with the db modules 'ctx' object. 
        Each call to this method returns a new 'ctx' object, with no opened database
        connections."""
    return read_config(deployment)

## User loading, creation and deletion debugging/testing tools.
def get_user_by_email(ctx, email):
    """
    Return the User object for the given email address.
    Optionally supply the ctx to load the User object from if a consistent view
    of the database is required. E.g. if a transaction commit will be required
    for changes made to the returned User object.
    The User caches the ctx object for lazy loading which means it lives beyond the
    lifetime of this function if supplied as a parameter.
    """
    with db.conn(ctx) as ctx:
        try:
            r = db.row(ctx, 'get_user_id_by_email', email=email)
        except db.TooFewRowsError:
            return None
        user_id = get_uuid(r['user_id'])
    return user.user_from_context(ctx, user_id)

def get_user_by_facebook_uid(ctx, facebook_uid):
    """
    Return the User object for the given Facebook ID.
    Optionally supply the ctx to load the User object from if a consistent view
    of the database is required. E.g. if a transaction commit will be required
    for changes made to the returned User object.
    The User caches the ctx object for lazy loading which means it lives beyond the
    lifetime of this function if supplied as a parameter.
    """
    with db.conn(ctx) as ctx:
        try:
            r = db.row(ctx, 'get_user_id_by_facebook_uid', uid=facebook_uid)
        except db.TooFewRowsError:
            return None
        user_id = get_uuid(r['user_id'])
    return user.user_from_context(ctx, user_id)

def get_user_by_edmodo_uid(ctx, edmodo_uid):
    """
    Return the User object for the given Edmodo ID.
    Optionally supply the ctx to load the User object from if a consistent view
    of the database is required. E.g. if a transaction commit will be required
    for changes made to the returned User object.
    The User caches the ctx object for lazy loading which means it lives beyond the
    lifetime of this function if supplied as a parameter.
    """
    with db.conn(ctx) as ctx:
        try:
            r = db.row(ctx, 'get_user_id_by_edmodo_uid', uid=edmodo_uid)
        except db.TooFewRowsError:
            return None
        user_id = get_uuid(r['user_id'])
    return user.user_from_context(ctx, user_id)

def get_all_user_ids(ctx):
    """ Return a list of {user_id:binary user_id} rows for every user currently known to the database. """
    return db._run_query_string(ctx, "SELECT user_id FROM users")

# These are tables that have data tied directly to a user_id
DELETE_USER_ID_TABLES = ['chips', 'deferred', 'messages', 'missions', 'rovers', 'target_sounds', 'target_image_rects',
                         'target_images', 'target_metadata', 'targets', 'species', 'user_map_tiles',
                         'users_notification', 'users_progress', 'achievements', 'users_metadata', 'capabilities',
                         'vouchers', 'users_shop', 'invoices', 'transactions', 'purchased_products']
# These are tables which require a join or more detail to delete the user data and are handled with custom queries.
DELETE_JOIN_TABLES = ['landers', 'invitations', 'gifts', 'invitation_gifts', 'users_password', 'users_facebook',
                      'users_edmodo', 'users', 'highlighted_targets', 'transaction_gateway_data']
# These tables should not have anything deleted from them when a user is deleted.
DELETE_IGNORE_TABLES = ['_yoyo_migration', 'email_queue', 'edmodo_groups']
# This is the union of all of the defined tables to handle when deleting. This is used to detect if a new table
# has been added to the schema but was not handled by the deletion code yet.
DELETE_KNOWN_TABLES = set(DELETE_USER_ID_TABLES + DELETE_JOIN_TABLES + DELETE_IGNORE_TABLES)

def delete_user_and_data(ctx, user_id, include_user_table=True):
    """ Delete the given user_id and all data associated with it.
        NOTE: This also deletes all of the user's shop data, which we might not want to do in production
        if we allow user's to delete themselves. """
    # Delete the user map tiles created by the renderer if any were created for the user.
    map_tiles_user = pkg_resources.resource_filename('front', '../var/renderer/map_tiles_user')
    user_part = "%s/%s" % (str(user_id)[0:2], user_id)
    dir_path = map_tiles_user + "/" + user_part
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

    # Delete rover related data.
    db._run_query_string(ctx, "DELETE FROM landers USING landers\
                               INNER JOIN rovers\
                               WHERE landers.lander_id = rovers.lander_id AND rovers.user_id=:user_id", user_id=user_id)

    # Delete transaction gateway data.
    db._run_query_string(ctx, "DELETE FROM transaction_gateway_data USING transaction_gateway_data\
                               INNER JOIN transactions\
                               WHERE transaction_gateway_data.transaction_id = transactions.transaction_id AND\
                               transactions.user_id=:user_id", user_id=user_id)

    # Find any invite or gift that this user either sent or received.
    invite_ids = db._run_query_string(ctx, "SELECT invite_id FROM invitations WHERE (sender_id=:user_id OR recipient_id=:user_id)", user_id=user_id)
    gift_ids = db._run_query_string(ctx, "SELECT gift_id FROM gifts WHERE (creator_id=:user_id OR redeemer_id=:user_id)", user_id=user_id)

    # Delete every invite gift associated with this user, along with any entries in the invitation_gifts join table.
    for invite_id in (get_uuid(r['invite_id']) for r in invite_ids):
        db._run_query_string(ctx, "DELETE FROM invitations WHERE invite_id=:invite_id", invite_id=invite_id)
        db._run_query_string(ctx, "DELETE FROM invitation_gifts WHERE invite_id=:invite_id", invite_id=invite_id)
    for gift_id in (get_uuid(r['gift_id']) for r in gift_ids):
        db._run_query_string(ctx, "DELETE FROM gifts WHERE gift_id=:gift_id", gift_id=gift_id)
        db._run_query_string(ctx, "DELETE FROM invitation_gifts WHERE gift_id=:gift_id", gift_id=gift_id)

    # And also clear/set to NULL any inviter_id that was set to the user being deleted.
    db._run_query_string(ctx, "UPDATE users SET inviter_id=NULL WHERE inviter_id=:user_id", user_id=user_id)

    # Delete remaining user data.
    for table_name in DELETE_USER_ID_TABLES:
        # Table name can't be escaped as the named query would normally do.
        db._run_query_string(ctx, "DELETE FROM %s WHERE user_id=:user_id" % table_name, user_id=user_id)

    # If requested, remove the actual users entry as well.
    if include_user_table:
        db._run_query_string(ctx, "DELETE FROM users_password WHERE user_id=:user_id", user_id=user_id)
        db._run_query_string(ctx, "DELETE FROM users_facebook WHERE user_id=:user_id", user_id=user_id)
        db._run_query_string(ctx, "DELETE FROM users_edmodo WHERE user_id=:user_id", user_id=user_id)
        db._run_query_string(ctx, "DELETE FROM users WHERE user_id=:user_id", user_id=user_id)

def restart_user_by_id(ctx, user_id):
    """ Restart a users gamestate, by deleting all their previous data (but not their users table
        or authenticationd data) and running the initial user code, including bringing their users.epoch forward. """
    delete_user_and_data(ctx, user_id, include_user_table=False)
    new_epoch = gametime.now() - timedelta(hours=Constants.EPOCH_START_HOURS)
    db._run_query_string(ctx, "UPDATE users SET epoch=:epoch WHERE user_id=:user_id", user_id=user_id, epoch=new_epoch)
    user.new_user_setup(ctx, user_id, send_validation_email=False)

def make_user_admin_by_id(ctx, user_id):
    """ Make a given user_id an admin user. """
    db._run_query_string(ctx, "UPDATE users SET dev=1 WHERE user_id=:user_id", user_id=user_id)

def list_all_db_tables(ctx):
    """ List all the currently defined table names in the database. """
    rows = db._run_query_string(ctx, "SHOW TABLES")
    table_names = [r.values()[0] for r in rows]
    return table_names

## Gametime.now manipulation debugging/testing tools.
def advance_now(**kwargs):
    """ Advance the clock using the same parameters you would pass to timedelta
    e.g., seconds=x, minutes=y, hours=z """
    gametime.set_now(gametime.now() + timedelta(**kwargs))

def rewind_now(**kwargs):
    """ Rewind the clock using the same parameters you would pass to timedelta
    e.g., seconds=x, minutes=y, hours=z """
    gametime.set_now(gametime.now() - timedelta(**kwargs))

## Advancing game debugging/testing tools.
def user_has_pending_game_actions(ctx, u):
    """ Returns True if this user has any pending 'actions' in the current game. Actions is currently
        defined as unprocessed targets, future chips or future deferred actions, but this definition might change. """
    actions = 0
    actions += db._run_query_string(ctx, "SELECT COUNT(*) AS count FROM targets, rovers\
                                          WHERE processed=0 AND rovers.rover_id = targets.rover_id AND\
                                          rovers.user_id=:user_id", user_id=u.user_id)[0]['count']
    actions += db._run_query_string(ctx, "SELECT COUNT(*) AS count FROM deferred\
                                          WHERE user_id=:user_id", user_id=u.user_id)[0]['count']
    # Future chips are those that would be delivered at least 5 seconds into the future.
    future_chips = utils.usec_db_from_dt(gametime.now() + timedelta(seconds=5))
    actions += db._run_query_string(ctx, "SELECT COUNT(*) AS count FROM chips\
                                          WHERE user_id=:user_id AND time > :since",
                                          user_id=u.user_id, since=future_chips)[0]['count']
    return actions > 0

def advance_game_for_user_by_seconds(ctx, u, seconds):
    """ Advance a user's gamestate by the given number of seconds. This does not render pending targets, but
        it does run deferreds, rewind the user.epoch field, and make any chips that should have been delivered
        between gametime.now and 'seconds' available right now (they are 'activated').
        NOTE: gametime.now will be frozen by a call to this function. If the caller wants to return to normal
        operation they should call gametime.unset_now after this function returns. """
    # These demark the two points in wall-clock-time time that we will be advancing through.
    start_time = gametime.now()
    end_time = gametime.now() + timedelta(seconds=seconds)

    # Freeze gametime.now so nothing gets missed.
    gametime.set_now(start_time)

    # Process any deferred actions that should be run during the window.
    deferred_rows = run_deferred_and_advance_now_until(ctx, u, until=end_time)

    # Now move the user's game forward by moving the epoch value and any non-gamestate
    # datetimes in the database forward by the "seconds" amount.
    # NOTE: We ignore created/updated fields as those are never used in the gamestate.
    # We also ignore targets.locked_at, chips.time, and users_notification.digest_window_start, digest_last_sent
    # as these are either safe to ignore or will be handled in other code.
    db._run_query_string(ctx, "UPDATE deferred SET run_at=run_at - INTERVAL :seconds SECOND\
                               WHERE user_id=:user_id",
                               seconds=seconds, user_id=u.user_id)
    db._run_query_string(ctx, "UPDATE user_map_tiles SET expiry_time=expiry_time - INTERVAL :seconds SECOND\
                               WHERE user_id=:user_id",
                               seconds=seconds, user_id=u.user_id)
    db._run_query_string(ctx, "UPDATE targets SET render_at=render_at - INTERVAL :seconds SECOND\
                               WHERE user_id=:user_id",
                               seconds=seconds, user_id=u.user_id)

    # Restore gametime.now to be start_time so that chips are issued/rolled back to 'now'.
    gametime.set_now(start_time)

    # Rewind the user's epoch value, so that all gamestate data will appear to have moved forward
    # by "seconds", relative to the new epoch value.
    new_epoch = u.epoch - timedelta(seconds=seconds)
    db._run_query_string(ctx, "UPDATE users SET epoch=:epoch WHERE user_id=:user_id", user_id=u.user_id, epoch=new_epoch)

    # 'activate'/send all chips being modified a few seconds into the future. We want to be sure that
    # if the client's last_seen_chip_time is identical to gametime.now() or if a fetch chips is happening
    # concurrent with this advance game process that these chips do not get lost in the shuffle.
    activate_time = gametime.now() + timedelta(seconds=CHIP_ACTIVATION_DELTA)

    # Send the epoch time change chip at activate_time to be sure the client sees it with
    # the other activated chips.
    # We want the epoch MOD to be applied before any of the activated chips are processed as some of them might
    # depend on the value of epoch being up-to-date. Since its 'seq' value might be > than chips being activated,
    # set its 'time' value to be a few microseconds before all of the other activated chips.
    chips.modify_in_future(ctx, u, u, deliver_at=activate_time - timedelta(microseconds=EPOCH_ACTIVATION_DELTA), epoch=new_epoch)
    u.set_silent(epoch = new_epoch) # Make our state mirror the database's.

    # Add a few seconds of padding between start_time and when the chips are going to be rewound to, which
    # is the moment they will be 'activated'. This guard is here so that if any actions are performed by
    # a currently active client right now, those chips will not be rewound/bundled into any chips being
    # activated from the future by this code. This means that the epoch MOD chip that was just sent is
    # not modified.
    start_of_chips = start_time + timedelta(seconds=CHIP_ACTIVATION_DELTA)

    # Snapshot the list of pending chips BEFORE they have had their time rewound.
    activated_chips = chips.get_chips(ctx, u, start_of_chips, end_time, True)

    # 'Activate' all chips for this user between the supplied start and end datetimes by
    # setting the time field to gametime.now() such that the next fetch_chips from the client will
    # see all of these chips. Note that this does not change the autoincrementing seq field, which
    # should preserve the order of the chips.
    micros = seconds * 1000000
    db._run_query_string(ctx, "UPDATE chips SET time=:now WHERE user_id=:user_id AND time > :start and time <= :end",
                               now=utils.usec_db_from_dt(activate_time),
                               user_id=u.user_id,
                               start=utils.usec_db_from_dt(start_of_chips),
                               end=utils.usec_db_from_dt(end_time))
    # Rewind any remaining chips in the database for this user by the number of seconds
    # we have moved the game forward.
    db._run_query_string(ctx, "UPDATE chips SET time=time - :micros\
                               WHERE user_id=:user_id AND time > :end",
                               user_id=u.user_id, micros=micros, end=utils.usec_db_from_dt(end_time))

    return (deferred_rows, activated_chips)

def run_deferred_and_advance_now_until(ctx, u, until):
    """
    Find all rows in the deferred table where the run_at time has passed for the given user and
    run the deferred action. gametime.now is set to the deferred actions run_at value to simulate
    the production environment when run from a cronjob.
    NOTE: gametime.now will be set to until at the end of this function, regardless of what happens.
    :param ctx: The database context.
    :param until: datetime Run deferred actions with run_at times older than this.
    Returns a list of DeferredRow instances that were run or any empty list.
    """
    with db.conn(ctx) as ctx:
        # The SQL handles returning these in sorted order, oldest first.
        rows = db.rows(ctx, 'debug/select_deferred_since_by_user_id', user_id=u.user_id, since=until)
        processed = []
        for row in rows:
            deferred_row = deferred.DeferredRow(**row)

            # Set the gametime's concept of now to a few seconds after this deferred was supposed to run,
            # to emulate the cronjob having just run and seen this deferred for the first time.
            gametime.set_now(deferred_row.run_at)

            # Process this deferred action.
            deferred.process_row(ctx, u, deferred_row)

            # If no exception ocurred for this deferred, delete it from the database and
            # commit the transaction.
            deferred_row.delete(ctx)
            processed.append(deferred_row)
    # Set the gametime to be the end of the window deferreds were run to.
    gametime.set_now(until)
    return processed

def flush_deferred_until(ctx, u, until):
    """
    Flush the deferred actions where the run_at is before 'until'.
    NOTE: These actions are NOT run, they are just deleted.
    :param ctx: The database context.
    :param until: datetime Flush deferred actions with run_at times older than this.
    Returns a list of DeferredRow instances that were flushed or any empty list.
    """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'debug/select_deferred_since_by_user_id', user_id=u.user_id, since=until)
        processed = []
        for row in rows:
            deferred_row = deferred.DeferredRow(**row)
            deferred_row.delete(ctx)
            processed.append(deferred_row)
    return processed

## Renderer debugging/testing tools.
def render_all_due_targets_for_user(ctx, u, run_renderer=False):
    """ Render all unprocessed targets for the given user whose render_at time has been arrived at.
        Returns a list of the processed targets, if any. """
    processing = []
    render_after = gametime.now()
    rows = db.rows(ctx, 'debug/select_unprocessed_targets_by_user_id', render_after=render_after, user_id=u.user_id)
    for r in rows:
        rover_id = get_uuid(r['rover_id'])
        rover = u.rovers[rover_id]
        target_id = get_uuid(r['target_id'])
        target = rover.targets[target_id]
        processing.append(target)

    if len(processing) > 0:
        if run_renderer:
            # FUTURE: Ideally the real renderer would allow us to tell it a target_id to process and
            # then we could call render_target_for_user here passing in run_renderer flag.
            try:
                run_real_renderer()
            except:
                # Unlock every target that was known to possibly be processed so that it
                # can be reprocessed on another attempt.
                db.rollback(ctx)
                for t in processing:
                    db.run(ctx, 'debug/update_target_unlock', target_id=t.target_id)
                db.commit(ctx)
                raise
        else:
            for t in processing:
                if 'TGT_FEATURE_PANORAMA' in t.metadata:
                    t.mark_processed_with_scene(scene.TESTING_PANORAMA, metadata=t.metadata)
                elif 'TGT_FEATURE_INFRARED' in t.metadata:
                    t.mark_processed_with_scene(scene.TESTING_INFRARED, metadata=t.metadata)
                else:
                    t.mark_processed_with_scene(scene.TESTING, metadata=t.metadata)
    return processing

def render_target_for_user(ctx, u, target, render_scene=scene.TESTING, run_renderer=False):
    """ Render a specific target for a given user instance. """
    if run_renderer:
        raise Exception("Rendering a specific target using the real renderer is currently unsupported.")
        # run_real_renderer(target_id=target.target_id)
        # NOTE: To make this work we would still need to run mark_processed_with_scene so that the
        # Target objects data is updated since the renderer runs in a different process and
        # database transaction.
    else:
        # Fake render the target.
        target.mark_processed_with_scene(render_scene, metadata=target.metadata)

# The renderer process does not currently return a non-0 exit value on failure, so search for specific
# strings in the output to detect known failure cases.
CONNECTION_FAILED = "Couldn't connect to server"
FAILURES = ["Warning: Assertion failed"]
def run_real_renderer():
    """ Run the real renderer process. The renderer will expect whatever web server it is configured
        to use for the renderer web service to be running. """
    p = subprocess.Popen([RENDERER_CMD], cwd=RENDERER_PATH, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, stdin=subprocess.PIPE)
    o, e = p.communicate()
    result = p.wait()
    if CONNECTION_FAILED in o:
        host = re.search(r'.*Verbose output: About to connect\(\) to (.*) \(.*', o).group(1)
        raise Exception("Renderer Failed! Could not connect to web server running on %s" % host)
    for f in FAILURES:
        if f in o:
            failures = [found for found in re.findall(r'.*%s.*' % f, o, re.I) for f in FAILURES]
            raise Exception("Renderer Failed! Failures reported by process: \n%s" % "\n".join(failures))
    if result != 0:
        raise Exception("Renderer Failed!\nstdout=[%s]\nstderr=[%s]" % (o, e))
    return o

def mark_targets_for_rerender(ctx, targets):
    """ Mark a list of Target objects for reprocessing by the renderer process. """
    for t in targets:
        t.mark_for_rerender()
