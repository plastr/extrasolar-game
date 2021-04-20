# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import uuid, itertools
from front import gift_types
from front.lib import get_uuid, db, urls, gametime, secure_tokens
from front.models import chips
from front.callbacks import run_callback, GIFT_CB

# Secure token namespaces.
GIFT_NAMESPACE = "extrasolar.tokens.gift"

def create_new_gift(ctx, creator, gift_type, annotation, campaign_name=None):
    """ 
    Create a new gift for the given creator user.
    """
    assert gift_type in gift_types.ALL, "Unknown gift_type when attempting to create %s" % gift_type
    params = {}
    # Use a random version 4 UUID for gifts instead of our usual time based version 1 so that
    # gift_ids are much harder to predict to a potential attacker.
    params['gift_id'] = uuid.uuid4()
    params['creator_id'] = creator.user_id
    params['redeemer_id'] = None
    params['gift_type'] = gift_type
    params['annotation'] = annotation
    params['campaign_name'] = campaign_name
    params['created'] = gametime.now()
    params['redeemed_at'] = None

    with db.conn(ctx) as ctx:
        db.run(ctx, "insert_gift", **params)
        gift = creator.gifts_created.create_child(**params)
        # NOTE: Do not send chips for gifts as they are not in the gamestate currently.
        # In the FUTURE if we put gifts into the gamestate we will need to call gift.send_chips right here.
    return gift

class GiftError(Exception): pass

class Gift(chips.Model):
    id_field = 'gift_id'
    fields = frozenset(['creator_id', 'redeemer_id', 'gift_type', 'name', 'description', 'annotation', 'created', 'redeemed_at',
                        'campaign_name', 'creator', 'redeemer', 'invite'])
    server_only_fields = frozenset(['creator', 'redeemer', 'invite'])
    unmanaged_fields = frozenset(['creator', 'redeemer', 'invite'])
    # Returns the creator User object for this specific Gift subclass. Must be overvide _load_creator in subclass.
    # Use this property instead of using the 'user' property that would be available in other Models as that might be
    # ambigious between 'creator' and 'redeemer'.
    creator = chips.LazyField("creator", lambda m: m._load_creator())
    # Returns the redeemer User object for this specific Gift subclass. Must be overvide _load_redeemer in subclass.
    # Use this property instead of using the 'user' property that would be available in other Models as that might be
    # ambigious between 'creator' and 'redeemer'.
    redeemer = chips.LazyField("redeemer", lambda m: m._load_redeemer())
    # This property returns the lazy loaded Invite object attached to this gift, if there is one,
    # returning None otherwise. See has_invite() to determine if this gift attached to an invite.
    # NOTE: The invite.user returned by this property is not guaranteed to be the same as self.user (the gift
    # creator) as it is possible to send an invite from a 'system' user but have the gift creator be a real admin.
    invite = chips.LazyField("invite", lambda m: m._load_invite())
    # These fields are meant to be user facing and are set based on the specific gift type, e.g a voucher gift
    # might get these from the underlying voucher type. Set by callbacks in gift_callbacks.
    name = chips.LazyField("name", lambda m: m._load_name())
    description = chips.LazyField("description", lambda m: m._load_description())

    def __init__(self, gift_id, **params):
        # If the UUID data is coming straight from the database row, convert it to a UUID instance.
        gift_id = get_uuid(gift_id)
        params['creator_id'] = get_uuid(params['creator_id'])
        params['redeemer_id'] = get_uuid(params['redeemer_id'], allow_none=True)
        super(Gift, self).__init__(gift_id=gift_id, **params)

    def has_invite(self):
        return self.invite is not None

    def was_redeemed(self):
        return self.redeemer_id is not None

    def has_campaign_name(self):
        return self.campaign_name != None

    @classmethod
    def gift_token_for_gift_id(cls, gift_id):
        return secure_tokens.make_token(GIFT_NAMESPACE, gift_id)

    @property
    def gift_token(self):
        return self.gift_token_for_gift_id(self.gift_id)

    def is_valid_gift_token(self, token):
        return secure_tokens.check_token(GIFT_NAMESPACE, token, self.gift_id)

    def url_gift_redeem(self):
        return urls.gift_redeem(self.gift_id, self.gift_token)

    def url_gift_redeem_new_user(self):
        return urls.gift_redeem_new_user(self.gift_id, self.gift_token)

    def url_gift_redeem_existing_user(self):
        return urls.gift_redeem_existing_user(self.gift_id, self.gift_token)

    def can_user_redeem(self, redeemer):
        """ NOTE: Calls through to can_user_redeem_gift in gift_callbacks. """
        return run_callback(GIFT_CB, "can_user_redeem_gift", self.gift_type, redeemer=redeemer, gift=self)

    def mark_redeemed_by_user(self, redeemer):
        """ Mark this Gift as having been redeemed by the given User. """
        assert not self.was_redeemed()
        # Be sure that only redeemers who are validated as being allowed to redeem this gift are allowed to.
        # NOTE: Callers should call can_user_redeem themselves before getting to this method to return
        # a nicer user facing error.
        ok, error = self.can_user_redeem(redeemer)
        if not ok:
            raise GiftError(error)

        now = gametime.now()
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_gift_set_redeemer', gift_id=self.gift_id, redeemer_id=redeemer.user_id, redeemed_at=now)
            self.redeemer_id = redeemer.user_id # Make our state mirror the database's
            self.redeemed_at = now

            # Create a new Gift instance based on the fields of this gift being redeemed, to represent
            # this gift in the redeemers gifts_redeeemd collection.
            params = {}
            for f in itertools.chain([self.id_field], self.fields):
                # Skip all of the lazy fields, e.g. the inviter, name etc.
                if f not in self.lazy_fields:
                    params[f] = getattr(self, f)
            redeemer.gifts_redeemed.create_child(**params)

            # NOTE: Do not send chips for gifts as they are not in the gamestate currently.
            # In the FUTURE if we put gifts into the gamestate we will need to call gift.send_chips right here.

            # If this gift has a campaign name associated with it and if the redeemer does not already
            # have a campaign name value, set it.
            if self.has_campaign_name() and not redeemer.has_campaign_name():
                redeemer.add_metadata("MET_CAMPAIGN_NAME", self.campaign_name)

            # Inform the callbacks that this gift was redeemed.
            run_callback(GIFT_CB, "gift_was_redeemed", self.gift_type, ctx=ctx, creator=self.creator, redeemer=redeemer, gift=self)

    ## Lazy load attribute methods.
    def _load_creator(self):
        raise NotImplementedError

    def _load_redeemer(self):
        raise NotImplementedError

    def _load_invite(self):
        # Have to import user_module this way to avoid a cyclic dependency import error.
        from front.models import user as user_module
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, "get_invite_id_by_gift_id", gift_id=self.gift_id)
        if len(rows) == 0:
            return None
        # We do not assume the sender of the invitation is the gift creator so load the
        # invite sender and get the Invite object from their invitations collection.
        invite_id = get_uuid(rows[0]['invite_id'])
        sender = user_module.user_from_invite_id(self.ctx, invite_id)
        return sender.invitations[invite_id]

    def _load_name(self):
        return run_callback(GIFT_CB, "gift_name", self.gift_type, gift=self)

    def _load_description(self):
        return run_callback(GIFT_CB, "gift_description", self.gift_type, gift=self)

# These are the specific subclasses of Gift meant to for either the user.gifts_created or
# user.gifts_redeemed collections.
# The main purpose of these subclasses is to provide the correct implementations for the creator and redeemer
# lazy loaders based upon whether this given gift came from a gifts_created or gifts_redeemed collection.
class GiftCreated(Gift):
    @property
    def ctx(self):
        return self.creator.ctx

    def _load_creator(self):
        # self.parent is user.gifts_created, the parent of that is the User itself.
        return self.parent.parent

    def _load_redeemer(self):
        if self.redeemer_id is None:
            return None
        # Have to import user_module this way to avoid a cyclic dependency import error.
        from front.models import user as user_module
        with db.conn(self.ctx) as ctx:
            return user_module.user_from_context(ctx, self.redeemer_id)

class GiftRedeemed(Gift):
    @property
    def ctx(self):
        return self.redeemer.ctx

    def _load_creator(self):
        # Have to import user_module this way to avoid a cyclic dependency import error.
        from front.models import user as user_module
        with db.conn(self.ctx) as ctx:
            return user_module.user_from_context(ctx, self.creator_id)

    def _load_redeemer(self):
        # self.parent is user.gifts_redeemed, the parent of that is the User itself.
        return self.parent.parent
