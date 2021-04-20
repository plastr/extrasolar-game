# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
# This module provides backend services to various admin functionality.
import collections
from datetime import timedelta
from front.lib import db, get_uuid, gametime, utils, urls, money
from front.models import user as user_module
from front.models import target as target_module
from front.models import gift as gift_module
from front.models import invite as invite_module
from front.backend import deferred, email_queue
from front.backend.shop import transaction

# The user attribues of the admin inviter account. See get_admin_inviter_user.
ADMIN_INVITER_EMAIL      = "robert@exoresearch.com"
ADMIN_INVITER_PASSWORD   = "b67430ba9c613e2472ae1ccb"
ADMIN_INVITER_FIRST_NAME = "Robert"
ADMIN_INVITER_LAST_NAME  = "Turing"

class FoundUser(object):
    fields = frozenset(['user_id', 'email', 'first_name', 'last_name', 'valid', 'last_accessed_approx', 'auth'])

    def __init__(self, row):
        for field in self.fields:
            if field == "user_id":
                value = get_uuid(row[field])
            elif field == "last_accessed_approx":
                value = utils.format_time_approx(utils.seconds_between_datetimes(row['last_accessed'], gametime.now()))
            else:
                value = row[field]
            setattr(self, field, value)

class RecentUser(object):
    fields = frozenset(['user_id', 'email', 'first_name', 'last_name', 'valid', 'last_accessed_approx', 'auth', 
                        'target_count', 'image_rects_count', 'voucher_count', 'metadata'])

    def __init__(self, row, metadata):
        for field in self.fields:
            if field == "user_id":
                value = get_uuid(row[field])
            elif field == "last_accessed_approx":
                value = utils.format_time_approx(utils.seconds_between_datetimes(row['last_accessed'], gametime.now()))
            elif field == "auth":
                value = row['authentication']
            elif field == "metadata":
                value = metadata
            else:
                value = row[field]
            setattr(self, field, value)

    @property
    def campaign_name(self):
        campaign_name = self.metadata.get('MET_CAMPAIGN_NAME')
        return campaign_name if campaign_name is not None else ""
    def has_campaign_name(self):
        return self.metadata.get('MET_CAMPAIGN_NAME') != None

class RecentTarget(target_module.TargetRow):
    fields = frozenset(['target_id', 'user_id', 'email', 'processed', 'picture', 'classified', 'user_created', 'neutered',
                        'highlighted', 'start_time', 'arrival_time', 'locked_at',
                        'arriving_approx', 'created_approx', 'render_at_approx',
                        'metadata', 'images'])

    def __init__(self, row, images, metadata):
        for field in self.fields:
            if field in ["target_id", 'user_id']:
                value = get_uuid(row[field])
            elif field == "created_approx":
                value = utils.format_time_approx(utils.seconds_between_datetimes(row['created'], gametime.now()))
            elif field == "render_at_approx":
                value = utils.format_time_approx(utils.seconds_between_datetimes(row['render_at'], gametime.now()))
            elif field == "arriving_approx":
                epoch_now = utils.seconds_between_datetimes(row['epoch'], gametime.now())
                arriving_in = row['arrival_time'] - epoch_now
                if arriving_in <= 0:
                    value = "Arrived"
                else:
                    value = utils.format_time_approx(arriving_in)
            elif field == "images":
                value = images
            elif field == "metadata":
                value = metadata
            else:
                value = row[field]
            setattr(self, field, value)

class RecentInvite(object):
    fields = frozenset(['invite_id', 'sender_id', 'recipient_id', 'recipient_email', 'recipient_last_name', 'recipient_first_name',
                        'campaign_name', 'sent_at', 'accepted_at', 'gift_type', 'sender_user_email', 'recipient_user_email'])

    def __init__(self, row):
        for field in self.fields:
            if field in ["invite_id", "sender_id", "recipient_id"]:
                value = get_uuid(row[field], allow_none=True)
            else:
                value = row[field]
            setattr(self, field, value)
    def was_accepted(self):
        return self.accepted_at is not None
    def has_campaign_name(self):
        return self.campaign_name is not None
    def has_gift(self):
        return self.gift_type is not None
    def url_invite_accept(self):
        token = invite_module.Invite.invite_token_for_invite_id(self.invite_id)
        return urls.invite_accept(self.invite_id, token)

class RecentGift(object):
    fields = frozenset(['gift_id', 'creator_id', 'redeemer_id', 'gift_type', 'annotation', 'campaign_name', 'created',
                        'redeemed_at', 'creator_user_email', 'redeemer_user_email'])

    def __init__(self, row):
        for field in self.fields:
            if field in ["gift_id", "creator_id", "redeemer_id"]:
                value = get_uuid(row[field], allow_none=True)
            else:
                value = row[field]
            setattr(self, field, value)
    def was_redeemed(self):
        return self.redeemed_at is not None
    def has_campaign_name(self):
        return self.campaign_name is not None
    def url_gift_redeem(self):
        token = gift_module.Gift.gift_token_for_gift_id(self.gift_id)
        return urls.gift_redeem(self.gift_id, token)

def recent_users(ctx, limit, last_accessed_hours=None, campaign_name=None):
    """ Return a limited list of User objects sorted by last_accessed """
    if last_accessed_hours is not None:
        last_accessed_after = gametime.now() - timedelta(hours=last_accessed_hours)
    else:
        last_accessed_after = None
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'admin/select_users_recent', last_accessed_after=last_accessed_after,
                       campaign_name=campaign_name, limit=limit)
        if len(rows) == 0:
            return []
        oldest_user_accessed = rows[-1]['last_accessed']
        metadata_rows = db.rows(ctx, 'admin/select_users_metadata_recent', oldest_user_accessed=oldest_user_accessed)
    # Map the user_id to a user metadata dictionary.
    user_metadatas = collections.defaultdict(dict)
    for r in metadata_rows:
        user_metadatas[get_uuid(r['user_id'])][r['key']] = r['value']

    users = []
    for r in rows:
        metadata = user_metadatas[get_uuid(r['user_id'])]
        users.append(RecentUser(r, metadata))
    return users

def recent_targets(ctx, limit, oldest_recent_target_days):
    """ Return a limited list of Target objects whose render_at has been arrived at, sorted by render_at. """
    with db.conn(ctx) as ctx:
        render_after_end   = gametime.now()
        # Use oldest_recent_target_days to filter the total number of target rows examined as in
        # production this greatly reduces the query time (since LIMIT is applied after all rows have been examined).
        render_after_start = render_after_end - timedelta(days=oldest_recent_target_days)
        rows = db.rows(ctx, 'admin/select_targets_recent',
            render_after_start=render_after_start, render_after_end=render_after_end, limit=limit)
        if len(rows) == 0:
            return []
        # Similarly to the above query, filter these queries on both the oldest and newest target selected
        # which greatly reduces the query time in production.
        newest_target_render_at = rows[0]['render_at']
        oldest_target_render_at = rows[-1]['render_at']
        images_rows = db.rows(ctx, 'admin/select_target_images_recent',
            oldest_target_render_at=oldest_target_render_at, newest_target_render_at=newest_target_render_at)
        metadata_rows = db.rows(ctx, 'admin/select_target_metadata_recent',
            oldest_target_render_at=oldest_target_render_at, newest_target_render_at=newest_target_render_at)
    # Map the target_id to a target images dictionary.
    target_images = collections.defaultdict(dict)
    for r in images_rows:
        target_images[get_uuid(r['target_id'])][r['type']] = r['url']
    # Map the target_id to a target metadata dictionary.
    target_metadatas = collections.defaultdict(dict)
    for r in metadata_rows:
        target_metadatas[get_uuid(r['target_id'])][r['key']] = r['value']

    targets = []
    for r in rows:
        target_id = get_uuid(r['target_id'])
        images = target_images[target_id]
        metadata = target_metadatas[target_id]
        targets.append(RecentTarget(r, images, metadata))
    return targets

def recent_transactions(ctx, limit):
    """ Return a limited list of Transaction objects sorted by created """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'admin/select_transactions_recent', limit=limit)
    return [transaction.Transaction.from_db_row(ctx, r) for r in rows]

def all_transactions_amount(ctx):
    """ Return the sum of the amount field of all transactions as a Money object.
        NOTE: It is assumed that all transactions are in the same currency. """
    with db.conn(ctx) as ctx:
        amount_sum = db.row(ctx, 'admin/sum_all_transactions_amount')['all_transactions_amount_sum']
    if amount_sum is None:
        return money.from_amount_and_currency(0, 'USD')
    else:
        return money.from_amount_and_currency(amount_sum, 'USD')

def search_for_users(ctx, search_term, limit):
    """ Find all users whose first_name, last_name or email contain the given search term. """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, "admin/select_users_from_search", search_term=search_term, limit=limit)
    return [FoundUser(r) for r in rows]

def all_users_count(ctx):
    """ Return a count of all users currently in the system """
    with db.conn(ctx) as ctx:
        return db.row(ctx, "admin/count_total_users")['all_users_count']

def recent_gifts(ctx, limit, creator_id=None):
    """ Return a limited list of Gift objects sorted by created """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'admin/select_gifts_recent', limit=limit, creator_id=creator_id)
    gifts = []
    for r in rows:
        gifts.append(RecentGift(r))
    return gifts

def recent_invites(ctx, limit, sender_id=None):
    """ Return a limited list of Invitations objects sorted by sent_at """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'admin/select_invites_recent', limit=limit, sender_id=sender_id)
    invites = []
    for r in rows:
        invites.append(RecentInvite(r))
    return invites

def pending_deferreds(ctx):
    """ Return all deferreds currently not run/waiting to be processed as a list of DeferredRow objects,
        ordered by run_at. """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'admin/select_pending_deferreds')
    deferreds = []
    for r in rows:
        d = deferred.DeferredRow(**r)
        # Save the user's email address as an additional field on the DeferredRow object for more friendly display
        d.user_email = r['email']
        deferreds.append(d)
    return deferreds

def queued_emails(ctx):
    """ Return all emails currently waiting to be processed as a list of QueuedRow objects,
        ordered by created. """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'email_queue/select_unsent_queued_emails')
    queued_emails = []
    for r in rows:
        e = email_queue.QueuedRow(**r)
        # Compute the amount of time this email has been sitting in the queue.
        e.delayed_seconds = max(0, utils.seconds_between_datetimes(e.created, gametime.now()))
        queued_emails.append(e)
    return queued_emails

def get_admin_inviter_user(ctx):
    """ Return the 'admin inviter' user, which at least currently is a Robert Turing user. See ADMIN_INVITER_EMAIL
        and related constants for the user's data. If this user does not currently exist, the user is created
        and validated. The purpose of this user is to be used for sending invitations as an administrator with
        possibly attached gifts without having to use the store. """
    with db.conn(ctx) as ctx:
        admin_inviter = user_module.user_from_email(ctx, ADMIN_INVITER_EMAIL)
        if admin_inviter is not None:
            return admin_inviter
        admin_inviter = user_module.create_and_setup_password_user(ctx, ADMIN_INVITER_EMAIL, ADMIN_INVITER_PASSWORD,
                                                                   ADMIN_INVITER_FIRST_NAME, ADMIN_INVITER_LAST_NAME,
                                                                   mark_valid=True)
        return admin_inviter

def send_admin_invite_with_gift_type(ctx, admin_user, invite_params, gift_type=None, annotation=None, campaign_name=None):
    """ Send an 'admin invitation', which is an invitation sent from the 'admin user' as defined in ADMIN_INVITER_EMAIL,
        currently Robert Turing. Optionally, a gift will be created and attached to this invitation, and the gift
        creator will be the currently logged in admin user (as passed in via the admin_user parameter). To attach
        a gift set the gift_type to a valid GFT_ key and provide the gift annotation. """
    assert admin_user.is_admin(), "Only admins can create invites/gifts [%s]" % admin_user.user_id
    admin_inviter = get_admin_inviter_user(ctx)
    # If requested to attach a gift, set the gift creator to the current admin user, not the system admin inviter.
    if gift_type is not None:
        gift = create_admin_gift_of_type(ctx, admin_user, gift_type, annotation, campaign_name=campaign_name)
    else:
        gift = None
    # But send the invite as the system admin inviter.
    invite = invite_module.create_new_invite(ctx, admin_inviter, gift=gift, admin_invite=True,
                                             campaign_name=campaign_name, **invite_params)
    return invite

def create_admin_gift_of_type(ctx, admin_user, gift_type, annotation, campaign_name=None):
    """ Create a gift with the given admin user as the gift creator and return the Gift object. """
    assert admin_user.is_admin(), "Only admins can create gifts [%s]" % admin_user.user_id
    gift = gift_module.create_new_gift(ctx, admin_user, gift_type, annotation, campaign_name=campaign_name)
    return gift
