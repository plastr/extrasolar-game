# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""This is a class representing the data behind a single user."""
import uuid
from datetime import timedelta
import collections
from collections import Counter

from front import Constants, activity_alert_types, species_types, models
from front.lib import db, get_uuid, gametime, utils, secure_tokens, urls
from front.models import chips, rover, mission, message, species, progress
from front.models import achievement, capability, voucher, maptile, invite, gift, shop
from front.models import region as region_module
from front.callbacks import run_callback, USER_CB

import logging
logger = logging.getLogger(__name__)

# Secure token namespaces and expiration times, in seconds.
VALIDATE_NAMESPACE       = "extrasolar.tokens.email_validate"
RESET_NAMESPACE          = "extrasolar.tokens.password_reset"
UNSUBSCRIBE_NAMESPACE    = "extrasolar.tokens.unsubscribe"
RESET_EXPIRE       = utils.in_seconds(days=3)

def user_from_request(request):
    """
    Factory function to load a UserModel instance from a Request object. The session will
    first be checked for a cached UserModel, otherwise a UserModel will be loaded using the user_id
    from the session object.
    Returns the UserModel instance or None if no user could be found based on the request information.

    :param request: The Request object.
    """
    user = request.environ.get('front.user')
    if user is None:
        user_id = user_id_from_request(request)
        with db.conn(request) as ctx:
            # If the session user_id does not identify a real record (e.g. user was deleted),
            # clear the user_id from the session.
            if not db.row(ctx, "user_id_exists", user_id=user_id)['exist']:
                from front.resource.auth import log_user_out
                log_user_out(request)
                return None
        user = user_from_context(request, user_id)
        request.environ['front.user'] = user
    return user

def user_id_from_request(request):
    """ Given a request object, return the UUID for the logged in user.
        Returns None if the user is not logged in. """
    sess = request.environ.get('beaker.session')
    return sess.get('user_id', None)

def user_from_email(ctx, email):
    """ Given a database context and an email address, return a UserModel instance.
        Returns None if there is no user for that email. """
    return _get_user_from_query_by_field(ctx, "get_user_id_by_email", "user_id", email=email)

def user_from_target_id(ctx, target_id):
    """ Given a database context and a target_id UUID, return a UserModel instance.
        Returns None if the target or user does not exist. """
    return _get_user_from_query_by_field(ctx, "get_user_id_by_target_id", "user_id", target_id=target_id)

def user_from_invite_id(ctx, invite_id):
    """ Given a database context and an invite_id UUID, return a UserModel instance.
        Returns None if the invite or user does not exist. """
    return _get_user_from_query_by_field(ctx, "get_user_id_by_invite_id", "sender_id", invite_id=invite_id)

def creator_from_gift_id(ctx, gift_id):
    """ Given a database context and a gift_id UUID, return a UserModel instance for the gift creator.
        Returns None if the gift or user does not exist. """
    return _get_user_from_query_by_field(ctx, "get_creator_id_by_gift_id", "creator_id", gift_id=gift_id)

def user_from_invoice_id(ctx, invoice_id):
    """ Given a database context and an invoice_id UUID, return a UserModel instance.
        Returns None if the invoice or user does not exist. """
    return _get_user_from_query_by_field(ctx, "get_user_id_by_invoice_id", "user_id", invoice_id=invoice_id)

def user_from_facebook_uid(ctx, uid):
    """ Given a database context and a Facebook user's ID, return a UserModel instance.
        Returns None if the user does not exist. """
    return _get_user_from_query_by_field(ctx, "get_user_id_by_facebook_uid", "user_id", uid=uid)

def user_from_edmodo_uid(ctx, uid):
    """ Given a database context and an Edmodo user's ID, return a UserModel instance.
        Returns None if the user does not exist. """
    return _get_user_from_query_by_field(ctx, "get_user_id_by_edmodo_uid", "user_id", uid=uid)

def _get_user_from_query_by_field(ctx, query_name, field, check_exists=False, **params):
    """ Given a database context, a query name and query params, and the field holding the user_id
        return a UserModel instance.
        Returns None if the row holding the user_id does not exist.
        NOTE: It is assumed if there is a row holding the user_id then the User for that user_id
        does exist and a User will be returned wrapping that user_id. This is done to avoid another query
        verifying the existence of the user_id in the users table. Pass check_exists=True to this function to
        change this behavior and verify users table existence. """
    with db.conn(ctx) as ctx:
        try:
            r = db.row(ctx, query_name, **params)
        except db.TooFewRowsError:
            return None
    return user_from_context(ctx, get_uuid(r[field]), check_exists=check_exists)

def user_from_context(ctx, user_id, check_exists=False):
    """
    Factory function to load a UserModel instance from database context. The context can either be
    an already opened database connection or the current application configuration, including the
    database configuration. If a number of models are being created or persisted in the same transaction
    or inside of a nested transaction, for instance during initial user creation and setup, then context 
    should be the database connection.

    :param ctx: The database context.
    :param user_id: The UUID object for this user.
    :param check_exists: Optionally this function can check to see if the user exists before returning.
        The function will return None if the user does not exist. This should be set to True if the
        user_id provided is passed from a player (is user data).
    """
    if check_exists:
        with db.conn(ctx) as ctx:
            if not db.row(ctx, "user_id_exists", user_id=user_id)['exist']:
                return None
    return UserModel(ctx, user_id)

def insert_new_user(ctx, email, first_name, last_name, invite=None, gift=None, mark_valid=False, auth="PASS"):
    """ Insert the bare users entry for a new user. Intended to be used only
        by this module and unit tests.
        If mark_valid is True, the user will start with the 'valid' field set to 1, meaning that
        the email address has been validated etc.
        :param invite: An optional Invite object if this new user signed up via an invitation.
        :param gift: An optional Gift object if this new user signed up redeeming a gift (either direct or via invite)."""
    user_id = uuid.uuid1()
    # The players rover is said to have touched down EPOCH_START_HOURS hours ago.
    now = gametime.now()
    epoch = now - timedelta(hours=Constants.EPOCH_START_HOURS)
    valid = 1 if mark_valid else 0

    # If this new user signed up via an invitation, record which user invited them.
    inviter_id = invite.sender_id if invite is not None else None

    db.run(ctx, "insert_user", user_id=user_id, email=email, valid=valid,
           first_name=first_name, last_name=last_name, auth=auth, epoch=epoch, created=gametime.now(),
           last_accessed=now, viewed_alerts_at=None, inviter_id=inviter_id, invites_left=Constants.INITIAL_INVITATIONS)
    return user_id

def new_user_setup(ctx, user_id, invite=None, gift=None, send_validation_email=True):
    """ Perform additional configuration of a new user. Factored out so that multiple authentication
        systems could be supported.
        :param invite: An optional Invite object if this new user signed up via an invitation.
        :param gift: An optional Gift object if this new user signed up redeeming a gift (either direct or via invite)."""
    # Load the User object and create the validation key code.
    user = user_from_context(ctx, user_id)

    # Create the users_notification table. Enable all notification types by default for a new user and
    # activity_alert_window_start to 10 minutes in the future so none of the game data we are about to
    # created will be notified on.
    ten_minutes_in_future = gametime.now() + timedelta(minutes=10)
    db.run(ctx, "notifications/insert_users_notification",
           user_id=user.user_id,
           wants_activity_alert=1,
           activity_alert_window_start=ten_minutes_in_future,
           activity_alert_last_sent=None,
           activity_alert_frequency=activity_alert_types.DEFAULT,
           lure_alert_last_checked=None,
           wants_news_alert=1)

    # Create the users_shop table which holds shop payment information.
    db.run(ctx, "shop/insert_users_shop", user_id=user.user_id, stripe_customer_id=None, stripe_customer_data=None)

    # Trigger the user_created callback.
    run_callback(USER_CB, "user_created", ctx=ctx, user=user, send_validation_email=send_validation_email)

    # If this user was created in response to an invitation, mark the invitation as having been accepted
    # and trigger the user_accepted_invite callback.
    if invite is not None:
        invite.mark_accepted_by_user(user)

    # If the user had a gift available during signup, redeem that gift now.
    # NOTE: If for any reason this gift cannot be redeemed by the new user, then a GiftError will be raised,
    # the database rolled back, and an error shown to the user.
    if gift is not None:
        gift.mark_redeemed_by_user(user)

    return user

def create_and_setup_password_user(ctx, email, pw, first_name, last_name, mark_valid=True):
    """ Create a new password authenticating User with the given properties. By default it will also be marked
        valid as if it had followed the backdoor email.
        NOTE: This function is only intended to be used in debug/testing/admin situations and not for real users. """
    from front.resource.auth import password
    new_id = password.insert_password_user(ctx, email, pw, first_name, last_name, mark_valid=mark_valid)
    user = new_user_setup(ctx, new_id, send_validation_email=not mark_valid)
    return user

class UserModel(chips.Model):
    id_field = chips.RootId('user')
    fields = frozenset(['user_id', 'email', 'first_name', 'last_name', 'epoch', 'auth', 'valid', 'dev',
                        'last_accessed', 'activity_alert_frequency', 'viewed_alerts_at',
                        'invites_left', 'inviter_id', 'inviter', 'current_voucher_level', 'shop'])
    computed_fields = {
        'viewed_alerts_at_date' : models.EpochDatetimeField('viewed_alerts_at')
    }
    collections = frozenset(['rovers', 'missions', 'messages', 'species', 'regions', 'progress', 'achievements',
                             'capabilities', 'vouchers', 'map_tiles', 'invitations', 'gifts_created', 'gifts_redeemed'])
    # The gifts_created and gifts_redeemed collections are server only for now.
    server_only_fields = frozenset(['user_id', 'last_accessed', 'gifts_created', 'gifts_redeemed'])

    email            = chips.LazyField("email",             lambda m: m._load_user_attributes()['email'])
    first_name       = chips.LazyField("first_name",        lambda m: m._load_user_attributes()['first_name'])
    last_name        = chips.LazyField("last_name",         lambda m: m._load_user_attributes()['last_name'])
    epoch            = chips.LazyField("epoch",             lambda m: m._load_user_attributes()['epoch'])
    auth             = chips.LazyField("auth",              lambda m: m._load_user_attributes()['authentication'])
    valid            = chips.LazyField("valid",             lambda m: m._load_user_attributes()['valid'])
    dev              = chips.LazyField("dev",               lambda m: m._load_user_attributes()['dev'])
    last_accessed    = chips.LazyField("last_accessed",     lambda m: m._load_user_attributes()['last_accessed'])
    viewed_alerts_at = chips.LazyField("viewed_alerts_at",  lambda m: m._load_user_attributes()['viewed_alerts_at'])
    invites_left     = chips.LazyField("invites_left",      lambda m: m._load_user_attributes()['invites_left'])
    inviter_id       = chips.LazyField("inviter_id",        lambda m: get_uuid(m._load_user_attributes()['inviter_id'], allow_none=True))
    # This field stores data about the inviter user (if exists) meant for the gamestate. Data in this value
    # should not require loading across database shards (if sharding on user_id).
    inviter          = chips.LazyField("inviter",           lambda m: m._load_inviter_attributes())
    # This field stores the full User object for the inviter user (if exists). This is meant to be used only in
    # admin or debugging situations as if users are sharded this would mean crossing shards.
    inviter_user     = chips.LazyField("inviter_user",      lambda m: m._load_inviter_user())
    # A lazy dict of all map tiles for this user, keyed off of the map tile key (zoom,x,y). All tiles, whether
    # current displayed or in the past/future at included in this list.
    all_map_tiles    = chips.LazyField("all_map_tiles",     lambda m: m._load_all_map_tiles())
    # Not a chips.Collection, just a lazy loaded server side only dict.
    metadata         = chips.LazyField("metadata",          lambda m: m._load_user_metadata())
    # Never send the password_hash to the client or put in the gamestate.
    password_hash    = chips.LazyField("password_hash",     lambda m: m._load_password_hash())
    # This loads from the users_notification table.
    activity_alert_frequency = chips.LazyField("activity_alert_frequency", lambda m: m._load_activity_alert_frequency())
    # Set the current_voucher_level (a voucher_key) based on current state of user's vouchers collection.
    current_voucher_level = chips.LazyField("current_voucher_level", lambda m: m._load_current_voucher_level())
    # Load the singleton Store model object.
    shop             = chips.LazyField("shop", lambda m: m._load_shop())

    def __init__(self, ctx, user_id):
        super(UserModel, self).__init__(
                user_id=get_uuid(user_id),
                rovers=RoverCollection.load_later('rovers', self._load_rovers),
                missions=MissionCollection.load_later('missions', self._load_missions),
                messages=MessageCollection.load_later('messages', self._load_messages),
                species=SpeciesCollection.load_later('species', self._load_species),
                regions=RegionCollection.load_later('regions', self._load_regions),
                progress=ProgressCollection.load_later('progress', self._load_progress),
                achievements=AchievementCollection.load_later('achievements', self._load_achievements),
                capabilities=CapabilityCollection.load_later('capabilities', self._load_capabilities),
                vouchers=VoucherCollection.load_later('vouchers', self._load_vouchers),
                map_tiles=MapTileCollection.load_later('map_tiles', self._load_map_tiles),
                invitations=InviteCollection.load_later('invitations', self._load_invitations),
                gifts_created=GiftCreatedCollection.load_later('gifts_created', self._load_gifts_created),
                gifts_redeemed=GiftRedeemedCollection.load_later('gifts_redeemed', self._load_gifts_redeemed))
        # Store the database context for lazy loading of attributes.
        self._ctx = ctx
        # Used to cache lazy loaded user attributes from a database row.
        self._user_attributes = None

    @property
    def ctx(self):
        """ Return the database context used to load this user. This is provided to every child model
            of this user via the UserChild mixin. """
        return self._ctx

    @property
    def activity_alert_frequency_window(self):
        """ The size of the user's current notification frequency setting in seconds. """
        return activity_alert_types.windows[self.activity_alert_frequency]

    def is_admin(self):
        return self.dev == 1

    @property
    def campaign_name(self):
        campaign_name = self.metadata.get('MET_CAMPAIGN_NAME')
        return campaign_name if campaign_name is not None else ""

    def has_campaign_name(self):
        return self.metadata.get('MET_CAMPAIGN_NAME') != None

    # Secure token definitions.
    @property
    def validation_token(self):
        return secure_tokens.make_token(VALIDATE_NAMESPACE, self.user_id)

    def url_validate(self):
        return urls.validate(self.validation_token)

    def url_api_validate(self):
        return urls.api_validate(self.validation_token)

    @property
    def password_reset_token(self):
        return secure_tokens.make_token_with_timestamp(RESET_NAMESPACE, self.user_id, self.password_hash)

    def is_valid_password_reset_token(self, token, timestamp):
        return secure_tokens.check_token_with_timestamp(RESET_NAMESPACE, token, timestamp, RESET_EXPIRE,
                                                        self.user_id, self.password_hash)

    def url_password_reset(self):
        (token, timestamp) = self.password_reset_token
        return urls.password_reset(self.user_id, token, timestamp)

    def change_password_hash(self, new_password_hash):
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_user_password', password=new_password_hash, user_id=self.user_id)

    @property
    def unsubscribe_token(self):
        return secure_tokens.make_token(UNSUBSCRIBE_NAMESPACE, self.user_id)

    def is_valid_unsubscribe_token(self, token):
        return secure_tokens.check_token(UNSUBSCRIBE_NAMESPACE, token, self.user_id)

    def url_unsubscribe(self):
        return urls.unsubscribe(self.user_id, self.unsubscribe_token)

    def url_admin(self):
        return urls.admin_user(self.user_id)

    def url_admin_map(self):
        return urls.admin_user_map(self.user_id)

    def url_public_profile(self):
        return urls.user_public_profile(self.user_id)

    @property
    def epoch_now(self):
        """ Return the current UTC time as an 'epoch' value (seconds after the user epoch). """
        return utils.seconds_between_datetimes(self.epoch, gametime.now())

    def after_epoch_as_datetime(self, seconds_after_epoch):
        """ Return a seconds since epoch value (integer) as a datetime object using the
            user's epoch value to perform the conversion. """
        return self.epoch + timedelta(seconds=seconds_after_epoch)

    def seconds_between_now_and_after_epoch(self, seconds_after_epoch):
        """ Return the number of seconds (integer) between now and the seconds since epoch
            value provided (integer). Returned value will be negative seconds_after_epoch is earlier
            than 'now'."""
        return seconds_after_epoch - self.epoch_now

    def first_move_possible_at(self):
        """ Returns the seconds since user.epoch that this user was able to make their first move.
            A number of initial moves are created automatically by the system to simulate the lander
            landing and the rover deploying and looking around and this value factors that in. """
        return self.progress[progress.names.PRO_USER_CREATED].achieved_at

    @property
    def activated_at_date(self):
        """ Returns the actual wallclock time this user was activated (first able to make a move). """
        return self.after_epoch_as_datetime(self.first_move_possible_at())

    @property
    def time_since_activated(self):
        """ Returns the number of seconds that have elapsed time between when this user
            was activated (first able to make a move) and now. """
        return utils.seconds_between_datetimes(self.activated_at_date, gametime.now())

    @property
    def time_since_last_accessed(self):
        """ Returns the number of seconds that have elapsed time between when this user
            was last 'active' and now. """
        return utils.seconds_between_datetimes(self.last_accessed, gametime.now())

    def total_distance_traveled(self):
        """ Returns the total distance, in meters, this user's rovers have traveled in the game so far.
            This method only considers targets which have been arrived at as of the current gametime. """
        return sum(r.distance_traveled() for r in self.rovers.itervalues())

    def total_distance_will_have_traveled(self):
        """ Returns the total distance, in meters, this user's rovers will have traveled in the game so far.
            This method INCLUDES targets which have been created but not yet been arrived at. """
        return sum(r.distance_will_have_traveled() for r in self.rovers.itervalues())

    def validate_with_token(self, token):
        """ Mark this user as validated (email verified) if the given token is valid.
            Returns False if the token is invalid. """
        valid = secure_tokens.check_token(VALIDATE_NAMESPACE, token, self.user_id)
        if not valid:
            logger.error("Invalid token when attempting user validation. (%s, %s)", self.user_id, token)
            return False

        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_user_valid', user_id=self.user_id)
            self.valid = 1  # Make our state mirror the database's.
            # No reason to send a chip since this field is not serialized.
            run_callback(USER_CB, "user_validated", ctx=ctx, user=self)

        return True

    def add_metadata(self, key, value=""):
        """
        Attach arbitrary metadata to this user object, using the given key and optional value.
        The keys should have a MET_ namespace.
        If the given key has already been assigned to this user, then its value and created
        time are updated/replaced.
        """
        assert key.startswith("MET_"), "Metadata keys must start with a MET_ prefix."
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'insert_or_update_users_metadata', user_id=self.user_id, key=key, value=value, created=gametime.now())
        # Make our state mirror the database's
        self.metadata[key] = value

    def clear_metadata(self, key):
        """
        Clear any metadata for the given given from this user object. This will delete the key and value comopletely.
        The keys should have a MET_ namespace.
        """
        assert key.startswith("MET_"), "Metadata keys must start with a MET_ prefix."
        # Make our state mirror the database's
        # Do this before deleting from the database so that the lazy loader has populated the metadata dictionary.
        del self.metadata[key]
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'delete_users_metadata', user_id=self.user_id, key=key)
    
    def has_target_with_metadata_key(self, key):
        with db.conn(self.ctx) as ctx:
            r = db.row(ctx, 'count_targets_with_metadata_key', metadata_key=key, user_id=self.user_id)
            return r['key_count'] > 0

    def set_activity_alert_frequency(self, activity_alert_frequency):
        """
        Set this user's activity alert settings to the given frequency.
        See front.activity_alert_types for possible frequency values.
        """
        assert activity_alert_frequency in activity_alert_types.ALL
        if activity_alert_frequency == activity_alert_types.OFF:
            with db.conn(self.ctx) as ctx:
                db.run(ctx, 'notifications/update_user_notifications', user_id=self.user_id,
                    activity_alert_frequency=activity_alert_frequency, wants_activity_alert=0)
        else:
            with db.conn(self.ctx) as ctx:
                db.run(ctx, 'notifications/update_user_notifications', user_id=self.user_id,
                    activity_alert_frequency=activity_alert_frequency, wants_activity_alert=1)

        self.activity_alert_frequency = activity_alert_frequency # Make our state mirror the database's
        self.send_chips(self.ctx, self)

    def update_last_accessed(self):
        """ Update this users last_accessed field to be gametime.now(). """
        now = gametime.now()
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_user_last_accessed', user_id=self.user_id, now=now)
        self.set_silent(last_accessed = now) # Make our state mirror the database's
        # Server only field so no chip.

    def update_viewed_alerts_at(self):
        """ Update this users viewed_alerts_at field to be 'now' in terms of their epoch. """
        epoch_now = self.epoch_now
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_user_viewed_alerts_at', user_id=self.user_id, epoch_now=epoch_now)
        self.viewed_alerts_at = epoch_now # Make our state mirror the database's
        self.send_chips(self.ctx, self)

    def increment_invites_left(self, delta=1):
        """ Increment this users invites_left field by 1. """
        new_invites_left = self.invites_left + delta
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_user_invites_left', user_id=self.user_id, invites_left=new_invites_left)
        self.invites_left = new_invites_left # Make our state mirror the database's
        self.send_chips(self.ctx, self)

    def decrement_invites_left(self, delta=1):
        """ Decrement this users invites_left field by 1. """
        assert self.invites_left > 0
        new_invites_left = self.invites_left - delta
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_user_invites_left', user_id=self.user_id, invites_left=new_invites_left)
        self.invites_left = new_invites_left # Make our state mirror the database's
        self.send_chips(self.ctx, self)

    def current_voucher_level_prepare_refresh(self):
        """
        Call this method anytime current_voucher_level's value might have changed, for instanceif a new
        voucher was delivered. See current_voucher_level_refresh.
        """
        self.current_voucher_level

    def current_voucher_level_refresh(self):
        """
        Update the lazy current_voucher_level field if it has changed and send a MOD chip.
        Call this method anytime this field's value might have changed, for instance if a new voucher was delivered.
        Call current_voucher_level_prepare_refresh before calling this method.
        """
        callback_value = run_callback(USER_CB, "user_current_voucher_level", ctx=self.ctx, user=self)
        if callback_value != self.current_voucher_level:
            self.current_voucher_level = callback_value
            with db.conn(self.ctx) as ctx:
                self.send_chips(ctx, self)

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'settings_notifications':urls.user_settings_notifications(),
                'update_viewed_alerts_at':urls.user_update_viewed_alerts_at()
            }
        return struct

    def load_gamestate_row_cache(self):
        """
        Ask the user object to load and cache all of the gamestate data so that only a few
        queries are executed instead of a large number of queries for every collection lazy loader.
        For example, targets have 4 collection like fields, each of which executes a query, so as the number
        of targets in the gamestate grows, the number of queries multiply by 4 (at least).
        The results are cached in u.ctx.row_cache and used in the lazy loader functions.
        """
        # Be sure the ctx is wrapped so there is a row_cache.
        with db.conn(self.ctx) as ctx:
            ctx.row_cache.set_rows_from_query(ctx, lambda r: [get_uuid(r['rover_id'])],
                                              "gamestate/select_targets_by_user_id", user_id=self.user_id)
            ctx.row_cache.set_rows_from_query(ctx, lambda r: [get_uuid(r['target_id'])],
                                              "gamestate/select_target_sounds_by_user_id", user_id=self.user_id)
            ctx.row_cache.set_rows_from_query(ctx, lambda r: [get_uuid(r['target_id'])],
                                              "gamestate/select_target_image_rects_by_user_id", user_id=self.user_id)
            ctx.row_cache.set_rows_from_query(ctx, lambda r: [get_uuid(r['target_id'])],
                                              "gamestate/select_target_images_by_user_id", user_id=self.user_id)
            ctx.row_cache.set_rows_from_query(ctx, lambda r: [get_uuid(r['target_id'])],
                                              "gamestate/select_target_metadata_by_user_id", user_id=self.user_id)

    def species_count(self, only_subspecies_id=None):
        '''
        Returns a Counter object of the number of times a given species_id was
        detected in all targets for this user.
        :param only_subspecies_id: int, if included, limit counts to this subspecies type.
        '''
        count = Counter()
        for rover in self.rovers.itervalues():
            for target in rover.targets.itervalues():
                if not target.picture:
                    continue
                count += target.species_count(only_subspecies_id=only_subspecies_id)
        return count

    def subspecies_count_for_species(self, species_id):
        '''
        Returns a Counter object of the number of times a given subspecies_id was
        observed for the indicated species.
        :param species_id: int, the id of the species that we're interested in.
        '''
        count = Counter()
        for rover in self.rovers.itervalues():
            for target in rover.targets.itervalues():
                if not target.picture:
                    continue
                count += target.subspecies_count_for_species(species_id=species_id)
        return count

    def all_picture_targets(self, user_created_only=False):
        """ Returns a list of all targets with pictures for this user, processed or not, arrived at or not,
            sorted by arrival_time. 
            If user_created_only is True then only targets created by the user and not any automated process,
            like initial rover targets, will be returned. """
        pictures = []
        for r in self.rovers.itervalues():
            pictures += r.targets.pictures()
        if user_created_only:
            pictures = [t for t in pictures if t.was_user_created()]
        return sorted(pictures, key=lambda t: t.arrival_time)

    def all_arrived_picture_targets(self):
        """ Returns a list of all targets with pictures for this user which are processed and
            have been arrived at sorted newest first, by arrival_time. """
        pictures = []
        for r in self.rovers.itervalues():
            pictures += r.targets.processed_pictures()
        return sorted(pictures, key=lambda t: t.arrival_time, reverse=True)

    def all_image_rects(self):
        """ Returns a list of all image_rects captured by this user. """
        rects = []
        for t in self.all_picture_targets():
            rects += t.image_rects.values()
        return rects

    def all_image_rects_with_species(self):
        """ Returns a list of all image_rects that identified at least one species. """
        return [r for r in self.all_image_rects() if r.has_species()]

    def get_edmodo_teacher_credentials(self):
        """ In order for a user to be authorized to access classroom data, they must be
            a teacher that's authenticated with Edmodo. For other users, return None.
            Return the access_token, user_token, and a boolean that indicates whether
            to use the sandbox servers.
        """
        if self.auth == 'EDMO':
            with db.conn(self.ctx) as ctx:
                try:
                    r = db.row(ctx, 'get_edmodo_teacher_credentials', user_id=self.user_id)
                    return {'access_token':r['access_token'], 'user_token':r['user_token'], 'sandbox':r['sandbox']==1}
                except db.TooFewRowsError:
                    return None
        return None

    ## Crosslink Methods.
    # Use the following set of routines to create links between various UI screens.  Note that
    # these routines don't actually create an anchor.  Rather, they create spans with all the 
    # data necessary for creating an anchor in the ce4.ui.update_crosslinks routine on the client.
    # This two-step process allows static template data to be sent from the server while the
    # client can adapt the links based on the available gamestate data.
    def crosslink_region(self, linked_text, *region_names):
        '''
        Pack the data necessary to create a link to a map region on the client.
        :param linked_text: str, The text that will be linked
        :param *region_names: a list of region names.  On the client, the first valid region
            in the list will be linked to.
        '''
        for region_name in region_names:
            assert region_module.is_known_region_id(region_name)
        region_links = ":".join(region_names);
        return "<span class='ce4_crosslink ce4_crosslink_region' data-region-type='" + region_links + "'>" + linked_text + "</span>";

    def crosslink_message(self, linked_text, msg_type):
        '''
        Pack the data necessary to create a link to a message on the client.
        :param linked_text: str, The text that will be linked
        :param msg_type: str, A valid message type.
        '''
        assert message.is_known_msg_type(msg_type)
        return "<span class='ce4_crosslink ce4_crosslink_message' data-msg-type='" + msg_type + "'>" + linked_text + "</span>";

    def crosslink_mission(self, linked_text, mission_definition):
        '''
        Pack the data necessary to create a link to a mission on the client.
        :param linked_text: str, The text that will be linked
        :param mission_definition: str, A valid mission definition.
        '''
        assert mission.is_known_mission_definition(mission_definition)
        return "<span class='ce4_crosslink ce4_crosslink_mission' data-mission-definition='" + mission_definition + "'>" + linked_text + "</span>";

    def crosslink_catalog(self, linked_text, species_key):
        '''
        Pack the data necessary to create a link to the species within the catalog on the client.
        :param linked_text: str, The text that will be linked
        :param species_key: str, A valid species key, e.g., SPC_PLANT015.
        '''
        assert species.is_known_species_key(species_key)
        return "<span class='ce4_crosslink ce4_crosslink_catalog' data-species-key='" + species_key + "'>" + linked_text + "</span>";

    def crosslink_store(self, linked_text):
        '''
        Pack the data necessary to create a link to the store from text in a template.
        :param linked_text: str, The text that will be linked
        '''
        return "<span class='ce4_crosslink ce4_crosslink_store'>" + linked_text + "</span>";

    def crosslink_profile(self, linked_text):
        '''
        Pack the data necessary to create a link to the profile from text in a template.
        :param linked_text: str, The text that will be linked
        '''
        return "<span class='ce4_crosslink ce4_crosslink_profile'>" + linked_text + "</span>";

    def crosslink_map(self, linked_text):
        '''
        Pack the data necessary to create a link to the map from text in a template.
        :param linked_text: str, The text that will be linked
        '''
        return "<span class='ce4_crosslink ce4_crosslink_map'>" + linked_text + "</span>";

    ## End Crosslink Methods.

    ## Public Profile Methods.
    # Methods in this namespace are intended to be used in the public profile page or similar user facing page.
    def profile_approx_time_since_activated(self):
        """ Returns a string which is a user friendly description of the amount of time
            that has elapsed time between when this user
            was activated (first able to make a move) and now. """
        return utils.format_time_approx(self.time_since_activated)

    def profile_approx_time_since_last_accessed(self):
        """ Returns a string which is a user friendly description of the amount of time
            that has elapsed time between when this user
            was last 'active' in the game and now. """
        return utils.format_time_approx(self.time_since_last_accessed)

    def profile_total_distance_traveled_rounded(self):
        return round(self.total_distance_traveled(), 1)
    ## End Public Profile Methods.

    ## Lazy load attribute methods.
    def _load_user_attributes(self):
        if self._user_attributes is None:
            with db.conn(self.ctx) as ctx:
                self._user_attributes = db.row(ctx, "get_user_row", user_id=self.user_id)
        return self._user_attributes

    def _load_user_metadata(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, "select_user_metadata", user_id=self.user_id)
        return dict(((r['key'], r['value']) for r in rows))

    def _load_password_hash(self):
        if self.auth == "PASS":
            with db.conn(self.ctx) as ctx:
                r = db.row(ctx, 'get_user_password_by_user_id', user_id=self.user_id)
                return r['password']
        else:
            return None

    def _load_activity_alert_frequency(self):
        with db.conn(self.ctx) as ctx:
            r = db.row(ctx, 'notifications/get_users_notification_by_user_id', user_id=self.user_id)
            return r['activity_alert_frequency']

    def _load_inviter_attributes(self):
        if self.inviter_id is None:
            return {}
        else:
            return {'url_public_profile': urls.user_public_profile(self.inviter_id)}

    def _load_inviter_user(self):
        if self.inviter_id is None:
            return None
        else:
            return user_from_context(self.ctx, self.inviter_id)

    def _load_current_voucher_level(self):
        return run_callback(USER_CB, "user_current_voucher_level", ctx=self.ctx, user=self)

    def _load_shop(self):
        with db.conn(self.ctx) as ctx:
            row = db.row(ctx, "shop/get_user_shop", user_id=self.user_id)
            return shop.Shop(**row)

    ## Lazy load collection methods.
    def _load_rovers(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_rovers_by_user_id', user_id=self.user_id)
        return rows

    def _load_messages(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_messages_by_user_id', user_id=self.user_id)
        return rows

    def _load_missions(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_missions_by_user_id', user_id=self.user_id)
        missions = [mission.Mission(user=self, **row) for row in rows]
        missions_dict = dict([(m.get_id(), m) for m in missions])

        # Wire up the mission hierarchy.
        for m in missions_dict.itervalues():
            if m.parent_id is not None:
                mission_parent = missions_dict.get(m.parent_id)
                if not mission_parent:
                    logger.error("Data fail, user %s has sub-mission %s without parent %s",
                        self.user_id, m.mission_id, m.parent_id)

                if mission_parent == m:
                    logger.error("Data fail, mission %s is its own parent.", m.mission_id)
                m.set_silent(mission_parent = mission_parent)
                mission_parent.parts.append(m)
                # Keep the children parts list in sorted order (where higher number means earlier
                # part of the mission)
                mission_parent.parts = sorted(mission_parent.parts, key=lambda m: m.sort, reverse=True)

        return missions

    def _load_species(self):
        all_subspecies_ids = {}
        all_target_ids = {}
        for rover in self.rovers.itervalues():
            for target in rover.targets.itervalues():
                if not target.picture:
                    continue
                for image_rect in target.image_rects.itervalues():
                    for species_id in image_rect.detected_species():
                        # If this image_rect has any detected subspecies add them to a mapping
                        # from species_id to the set of all detected_subspecies.
                        subspecies_ids = image_rect.detected_subspecies()
                        if species_id in subspecies_ids:
                            all_subspecies_ids.setdefault(species_id, set()).update(subspecies_ids[species_id])
                        # Save the (rover_id, target_id) tuple which will be provided to the Species
                        # model. This is used on the client to conveniently find which targets a
                        # species has been detected in.
                        all_target_ids.setdefault(species_id, set()).add((rover.rover_id, target.target_id))

        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_species_by_user_id', user_id=self.user_id)
        user_species = []
        for row in rows:
            # Both of these default to the empty set if there is a species that was identified
            # but no longer has image_rects containing it (if image_rect deletion is supported again).
            subspecies_ids = all_subspecies_ids.get(row['species_id'], set())
            target_ids = all_target_ids.get(row['species_id'], set())
            user_species.append(species.Species(subspecies_ids=subspecies_ids, target_ids=target_ids, user=self, **row))
        return user_species

    def _load_regions(self):
        # Gather the various current region_id/RegionPacks from the callbacks.
        region_descriptions = progress.run_region_list_callbacks(self.ctx, self)
        for m in self.missions.itervalues():
            region_descriptions += m.region_list_callback()

        # Now convert the region 'descriptions' (region_id, constructor_data) into
        # actual Region objects, ready to be added to the chips model hierarchy.
        regions = []
        for region_id, constructor_args in region_descriptions:
            regions.append(region_module.from_id(region_id, **constructor_args))
        return regions

    def _load_progress(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_progress_by_user_id', user_id=self.user_id)
        return rows

    def _load_achievements(self):
        # Then load the persisted data, namely if and when an achievement has been achieved.
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_achievements_by_user_id', user_id=self.user_id)
        # Convert the rows into a map from achievement_key to data for achievements that
        # have been achieved.
        achieved = {}
        for r in rows:
            achieved[r['achievement_key']] = {'achieved_at': r['achieved_at'], 'viewed_at': r['viewed_at']}

        achievements = []
        for achievement_key in achievement.all_achievement_definitions():
            # Use default values of None for the date values if this achievement has not
            # been achieved yet.
            params = achieved.get(achievement_key, {'achieved_at': None, 'viewed_at': None})
            achievements.append(achievement.Achievement(achievement_key=achievement_key, **params))
        return achievements

    def _load_capabilities(self):
        # Then load the persisted data, namely if a capability has been used.
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_capabilities_by_user_id', user_id=self.user_id)
        # Convert the rows into a map from capability_key to the rest of the persisted capability data.
        used = {}
        for r in rows:
            used[r['capability_key']] = {'uses': r['uses']}

        capabilities = []
        for capability_key in capability.all_capability_definitions():
            # Use default value of 0 if this achievement has not been used yet.
            params = used.get(capability_key, {'uses': 0})
            capabilities.append(capability.Capability(capability_key=capability_key, user=self, **params))
        return capabilities

    def _load_vouchers(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_vouchers_by_user_id', user_id=self.user_id)
        return rows

    def _load_map_tiles(self):
        # This will only grab the "current" map tiles for a given map tile key (zoom,x,y).
        # There may still be expired map tiles in the database or future map tiles waiting
        # for the rover to arrive at a target, but those are filtered by this select.
        # NOTE: current map tiles includes the target data leeway window, meaning that
        # tiles will be in the gamestate slightly before the target has been officially
        # arrived at so that the user will see all the data as soon as it is available
        # even if the chip fetch is slightly delayed.
        arrived_before = self.epoch_now + Constants.TARGET_DATA_LEEWAY_SECONDS
        expired_after = gametime.now() - timedelta(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_user_map_tiles_by_user_id', user_id=self.user_id,
                                arrived_before=arrived_before, expired_after=expired_after)
        return rows

    def _load_all_map_tiles(self):
        # Not technically a chip.Collection, instead this lazy field holds all map tile data currently in the database
        # for every (x,y,zoom) regardless of arrival_time or expiry_time.
        # Returns a dict mapping (x,y,zoom) to all the rows for that tile key.
        tiles = collections.defaultdict(list)
        # These are sorted by arrival_time in the query.
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_all_user_map_tiles_by_user_id', user_id=self.user_id)
        for r in rows:
            tile = maptile.MapTileRow(**r)
            tiles[tile.tile_key].append(tile)
        return tiles

    def _load_invitations(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_invites_by_user_id', sender_id=self.user_id)
        return rows

    def _load_gifts_created(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_gifts_by_creator_id', creator_id=self.user_id)
        return rows

    def _load_gifts_redeemed(self):
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, 'select_gifts_by_redeemer_id', redeemer_id=self.user_id)
        return rows

    def __repr__(self):
        # User is a root model so the superclass __repr__ get_id won't return the user_id.
        return "%s(%s)" % (self.__class__.__name__, self.user_id)


## User Collection classes.
class RoverCollection(chips.Collection):
    model_class = rover.Rover

    def find_target_by_id(self, target_id):
        """ Search all rovers for the given target_id. Return None if not found. """
        # Start with the active rovers so as not to lazy load the inactive rovers if not needed.
        for r in self.active():
            if target_id in r.targets:
                return r.targets[target_id]
        for r in self.inactive():
            if target_id in r.targets:
                return r.targets[target_id]
        # Not found.
        return None

    def iter_targets(self, newest_first=False):
        """ Iterate through every target sorted by_arrival_time for every rover,
            starting with the most recently activated rover. """
        for r in self.by_activated_at():
            for t in r.targets.by_arrival_time(newest_first=newest_first):
                yield t

    def iter_processed_pictures(self, newest_first=False):
        """ Iterate through every processed picture target which has been arrived at,
            sorted by_arrival_time for every rover,
            starting with the most recently activated rover. """
        for r in self.by_activated_at():
            for t in r.targets.processed_pictures(newest_first=newest_first):
                yield t

    def by_activated_at(self, newest_first=True):
        """ Get the list of all rovers, sorted by activated_at, newest first. """
        return sorted([r for r in self.values()], key=lambda r: r.activated_at, reverse=newest_first)

    def active(self):
        """
        Get the list of all active rovers, sorted by the activated_at, oldest rover first.
        May be a list with 0 or more elements.
        """
        return [r for r in self.by_activated_at(newest_first=False) if r.active]

    def inactive(self):
        """
        Get the list of all active rovers, sorted by activated_at, oldest rover first.
        May be a list with 0 or more elements.
        """
        return [r for r in self.by_activated_at(newest_first=False) if not r.active]

    def callback_values_prepare_refresh(self):
        """
        Call this before making any gamestate changes which might show up when
        capability_features_refresh is called. e.g. capability unlimited or available values are changing.
        This forces all of the rovers to be lazy loaded and any of their lazy fields to be loaded
        so that any callback derived values can be tracked and chips sent.
        """
        for r in self.itervalues():
            r.capabilities_changing()

    def callback_values_refresh(self):
        """
        Call this after making any gamestate changes which might change any of the callback derived rover fields
        e.g. min_target_seconds.
        NOTE: Be sure to call capability_features_prepare_refresh before making any of the
        relevant gamestate changes so that all rovers and fields have been lazy loaded and any changes
        can be tracked and chips sent.
        """
        for r in self.itervalues():
            r.capabilities_changed()

class MissionCollection(chips.Collection):
    model_class = mission.Mission

    def all_by_started_at(self):
        """ Return all missions, sorted by started_at. """
        return sorted([m for m in self.itervalues()], key=lambda m: m.started_at)

    def get_only_by_definition(self, mission_definition):
        """
        Search all current missions for this user and return one mission that matches the provided
        of the mission definition. If more than one mission matches the mission definition an exception is raised.
        Returns None if no mission matches.
        param mission_definition: The mission definition string. See mission.py. e,g MIS_TUT01a
        """
        found = [m for m in self.itervalues() if m.mission_definition == mission_definition]
        assert(len(found) < 2)
        if len(found) == 1:
            return found[0]
        else:
            return None

    def done(self, root_only=False):
        """
        Return all missions that have been marked done.
        :param root_only: Optionally only return 'root' missions.
        """
        if root_only:
            return [m for m in self.itervalues() if m.is_done() and m.is_root_mission()]
        else:
            return [m for m in self.itervalues() if m.is_done()]

    def not_done(self, root_only=False):
        """
        Return all missions that have not been been marked done.
        :param root_only: Optionally only return 'root' missions.
        """
        if root_only:
            return [m for m in self.itervalues() if not m.is_done() and m.is_root_mission()]
        else:
            return [m for m in self.itervalues() if not m.is_done()]

class MessageCollection(chips.Collection):
    model_class = message.Message

    @property
    def user(self):
        return self.parent

    def unread(self):
        """ Return any messages which are unread. """
        return [m for m in self.itervalues() if not m.was_read()]

    def all_by_sent_at(self):
        """ Return all messages, sorted by sent_at. """
        return sorted([m for m in self.itervalues()], key=lambda m: m.sent_at)

    def by_type(self, msg_type):
        """
        Search all current message for this user and return one message that matches the provided
        of the message type. If more than one message matches the message type an exception is raised.
        Returns None if no message matches.
        param msg_type: The message type string. See message.py. e.g. MSG_WELCOME
        """
        assert message.is_known_msg_type(msg_type)
        found = [m for m in self.itervalues() if m.msg_type == msg_type]
        assert(len(found) < 2)
        if len(found) == 1:
            return found[0]
        else:
            return None

    def keycode_for_msg_type(self, msg_type):
        """ Convenience shortcut to messages.keycode_for_msg_type for locked messags. Asserts the provided
            msg_type exists in the template data, but it is not required that that message is currently in
            the gamestate/has been received by the user. """
        assert message.is_known_msg_type(msg_type)
        return message.keycode_for_msg_type(msg_type, self.user)

    def has_been_queued_or_delivered(self, msg_type):
        """
        Returns True if a Message of the the given msg_type has either already been delivered
        to this user or is queued to be delivered in the future, False otherwise.
        """
        if self.by_type(msg_type) is not None:
            return True
        if message.has_been_queued(self.user.ctx, self.user, msg_type):
            return True
        return False

class SpeciesCollection(chips.Collection):
    model_class = species.Species

    def target_count_for_id(self, species_id):
        """ Return a count of the number of target images this species_id has been identified in.
            Returns 0 if this species_id has not been identified. """
        assert isinstance(species_id, int)
        found = self.get(species_id, None)
        if found is None:
            return 0
        else:
            return len(found.target_ids)

    def target_count_for_key(self, species_key):
        """ Return a count of the number of target images this species_key has been identified in.
            Returns 0 if this species_key has not been identified. """
        assert isinstance(species_key, basestring)
        return self.target_count_for_id(species.get_id_from_key(species_key))

    def all_by_detected_at(self):
        """ Return all species, sorted by detected_at. """
        return sorted([m for m in self.itervalues()], key=lambda m: m.detected_at)

    def unviewed(self):
        """ Return any species which are unviewed. """
        return [s for s in self.itervalues() if not s.was_viewed()]

    def of_type(self, species_type):
        """ Return all Species objects of the given species type. """
        return [s for s in self.itervalues() if s.type == species_type]

    def plants(self):
        return self.of_type(species_types.PLANT)

    def animals(self):
        return self.of_type(species_types.ANIMAL)

class RegionCollection(chips.Collection):
    model_class = region_module.Region

    def delete_by_id(self, region_id):
        """
        Regions are special in that they are in no way backed by the database. This
        helper makes it safe to "delete" (or hide) a Region for a given user. The Region
        needs to also be filtered in _load_regions, this helper will only remove it from
        the runtime Collection and issue a chip.
        """
        region = self[region_id]
        self.delete_child(region)
        region.send_chips(region.ctx, region.user)

class ProgressCollection(chips.Collection):
    model_class = progress.Progress

    def has_achieved(self, progress_key):
        """Return True if the given progress key has been achieved by this User."""
        return progress_key in self

    def value_for_key(self, progress_key):
        """Helper to return the value field for a given progress key."""
        return self[progress_key].value

class AchievementCollection(chips.Collection):
    model_class = achievement.Achievement

    def achieved(self):
        """ Return all achievements that have been achieved, sorted by achieved_at. """
        return sorted([a for a in self.itervalues() if a.was_achieved()], key=lambda a: a.achieved_at)

    def not_achieved(self):
        """ Return all achievements that have not yet been achieved. """
        return [a for a in self.itervalues() if not a.was_achieved()]

    def unviewed_and_achieved(self):
        """ Return any achievements which are unviewed and achieved. """
        return [a for a in self.achieved() if not a.was_viewed()]

class CapabilityCollection(chips.Collection):
    model_class = capability.Capability

    def provides_rover_feature(self, metadata_key):
        """ Returns the list of capabilites that provide the given rover feature and are available. """
        return [c for c in self.itervalues() if c.provides_rover_feature(metadata_key) and c.is_available()]

    def provides_rover_feature_has_uses(self, metadata_key):
        """ Returns the list of capabilites that provide the given rover feature and have uses left. """
        return [c for c in self.provides_rover_feature(metadata_key) if c.has_uses()]

    def available_and_unlimited_prepare_refresh(self):
        """
        Call this before making any gamestate changes which might show up when
        available_and_unlimited_refresh is called. e.g. rover counts or purchases which would
        change the available or unlimited values of a capability.
        This forces all of the capabilites to be lazy loaded and get their 'current' available
        and unlimited values so any changes can be tracked and chips sent.
        """
        len(self)

    def available_and_unlimited_refresh(self):
        """
        Call this after making any gamestate changes which might change the available or unlimited
        values of a capabilitiy. e.g. rover counts or purchases.
        NOTE: Be sure to call available_and_unlimited_prepare_refresh before making any of the
        relevant gamestate changes so that all capabilities have been lazy loaded and any changes
        can be tracked and chips sent.
        """
        for c in self.itervalues():
            c.available_and_unlimited_refresh()

class VoucherCollection(chips.Collection):
    model_class = voucher.Voucher

    def by_delivered_at(self):
        """ Return the list of Vouchers sorted by delivered_at, newest first. """
        return sorted(self.values(), key=lambda v: v.delivered_at, reverse=True)

class MapTileCollection(chips.Collection):
    model_class = maptile.MapTile

class InviteCollection(chips.Collection):
    model_class = invite.Invite

class GiftCreatedCollection(chips.Collection):
    model_class = gift.GiftCreated

    def by_created(self):
        """ Return the list of Gifts sorted by created, newest first. """
        return sorted(self.values(), key=lambda g: g.created, reverse=True)

class GiftRedeemedCollection(chips.Collection):
    model_class = gift.GiftRedeemed

    def by_created(self):
        """ Return the list of Gifts sorted by created, newest first. """
        return sorted(self.values(), key=lambda g: g.created, reverse=True)
