# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import cgi, uuid
from front import Constants
from front.lib import get_uuid, db, urls, patterns, utils, gametime, secure_tokens
from front.models import chips
from front.callbacks import run_callback, USER_CB

# Secure token namespaces.
INVITE_NAMESPACE = "extrasolar.tokens.invitation"

# The maximum length of the recipient_message.
MAX_LEN_MESSAGE = 2000

def validate_invite_params(sender, recipient_email, recipient_first_name, recipient_last_name, recipient_message,
                           attaching_gift=False, admin_invite=False):
    """ 
    Validate the given invitation parameters before the invitation is created. The given parameters are
    assumed to have come from the user and will be escaped to disable any HTML and will be truncated as
    needed or otherwise modified. If a given parameter is invalid and cannot be fixed None will be returned
    from this function along with a user facing error message.
    Returns a new dict object with the invite parameters as values.
    """
    # If the sending user has no more invitations left, return an error. Invitations with gifts or admin invitations
    # can always be sent.
    if not attaching_gift and not admin_invite:
        if sender.invites_left <= 0:
            return None, utils.tr("No more invitations are available.")

    params = {}
    params['recipient_email']      = recipient_email[:Constants.MAX_LEN_EMAIL]
    # The recipient fields (especially _message) are untrusted strings coming from a player to be emailed in
    # an HTML email message to any random email address so at the very least let's escape any HTML in there
    # (like an href to some malware or a <script> tag).
    params['recipient_first_name'] = cgi.escape(recipient_first_name)[:Constants.MAX_LEN_FIRST]
    params['recipient_last_name']  = cgi.escape(recipient_last_name)[:Constants.MAX_LEN_LAST]
    params['recipient_message']    = cgi.escape(recipient_message)[:MAX_LEN_MESSAGE]

    # If the email address doesn't look right let's fail back to the inviter so that the invited user
    # has a greater chance of getting through the signup page.
    if not patterns.is_email_address(params['recipient_email']):
        return None, utils.tr("Invalid email address for invitation.")

    return params, None

def create_new_invite(ctx, sender, recipient_email, recipient_first_name, recipient_last_name, recipient_message,
                      gift=None, admin_invite=False, campaign_name=None):
    """ 
    Create a new invitation for the given sender.
    NOTE: Call validate_invite_params before calling this function.
    :param gift: An optional Gift object if this new invite should have a gift attached to it.
    """
    params = {}
    # Use a random version 4 UUID for invites instead of our usual time based version 1 so that
    # invite_ids are much harder to predict to a potential attacker.
    params['invite_id'] = uuid.uuid4()
    params['sender_id'] = sender.user_id
    params['recipient_id'] = None
    params['recipient_email'] = recipient_email
    params['recipient_first_name'] = recipient_first_name
    params['recipient_last_name'] = recipient_last_name
    params['campaign_name'] = campaign_name
    params['sent_at'] = gametime.now()
    params['accepted_at'] = None

    with db.conn(ctx) as ctx:
        # Create and persist the invite object.
        db.run(ctx, "insert_invite", **params)
        # Pass the gift object through to the initialization of the invite model instance. This will populate
        # the lazy loaded value with whatever the gift value is (could be None if there was no gift attached).
        # This saves a database load for this particular invite's lazy loaded gift object since it is known
        # whether there is a gift attached or not at this moment.
        invite = sender.invitations.create_child(gift=gift, **params)

        # If a gift was attached to this invite, insert it into the join table.
        if gift is not None:
            db.run(ctx, "insert_invitation_gift", invite_id=params['invite_id'], gift_id=gift.gift_id)
            # Since there is a gift attached, inform that gift that this invite is its pair.
            # This saves a database load for this particular gift's lazy loaded invite object since it is known
            # whether there is an invite pair for this gift or not at this moment.
            gift.set_silent(invite=invite)

        # Send a chip for this invite being added.
        invite.send_chips(ctx, sender)

        # Now that the invite has been created, decrement the senders invites_left counter.
        # If this invite has a gift attachement or is an admin invite do nothing.
        if gift is None and not admin_invite:
            sender.decrement_invites_left()

        # Inform the callbacks that this invite was created.
        run_callback(USER_CB, "user_created_invite", ctx=ctx, sender=sender, invite=invite, recipient_message=recipient_message)

    return invite

class Invite(chips.Model):
    id_field = 'invite_id'
    fields = frozenset(['sender_id', 'recipient_id', 'recipient_email', 'recipient_last_name', 'recipient_first_name',
                        'sent_at', 'accepted_at', 'campaign_name', 'sender', 'recipient', 'gift'])
    server_only_fields = frozenset(['sender', 'recipient', 'gift', 'campaign_name'])
    unmanaged_fields = frozenset(['sender', 'recipient', 'gift'])
    # This property returns the lazy loaded Gift object attached to this invitation, if there is one,
    # returning None otherwise. See has_gift() to determine if there was a gift attached to this invite.
    # NOTE: The gift.user returned by this property is not guaranteed to be the same as self.user (the invite
    # sender) as it is possible to send an invite from a 'system' user but have the gift creator be a real admin.
    gift = chips.LazyField("gift", lambda m: m._load_gift())
    # Lazy load the sender and recipient user model.
    # Use these properties instead of using the 'user' property that would be available in other Models as that might be
    # ambigious between 'sender' and 'recipient'.
    sender = chips.LazyField("sender", lambda m: m._load_sender())
    recipient = chips.LazyField("recipient", lambda m: m._load_recipient())

    def __init__(self, invite_id, **params):
        # If the UUID data is coming straight from the database row, convert it to a UUID instance.
        invite_id = get_uuid(invite_id)
        params['sender_id'] = get_uuid(params['sender_id'])
        params['recipient_id'] = get_uuid(params['recipient_id'], allow_none=True)
        super(Invite, self).__init__(invite_id=invite_id, **params)

    @property
    def ctx(self):
        return self.sender.ctx

    def has_gift(self):
        return self.gift != None

    def has_recipient_name(self):
        """ Return True if the recipient_first_name is not blank. (might be blank for admin sent invitations)."""
        return len(self.recipient_first_name.strip()) > 0

    def was_accepted(self):
        return self.recipient_id != None

    def has_campaign_name(self):
        return self.campaign_name != None

    @classmethod
    def invite_token_for_invite_id(cls, invite_id):
        return secure_tokens.make_token(INVITE_NAMESPACE, invite_id)

    @property
    def invite_token(self):
        return self.invite_token_for_invite_id(self.invite_id)

    def is_valid_invite_token(self, token):
        return secure_tokens.check_token(INVITE_NAMESPACE, token, self.invite_id)

    def url_invite_accept(self):
        return urls.invite_accept(self.invite_id, self.invite_token)

    def mark_accepted_by_user(self, recipient):
        """ Mark this Invite as having been accepted by the given User. """
        now = gametime.now()
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'update_invite_set_recipient', invite_id=self.invite_id, recipient_id=recipient.user_id, accepted_at=now)
            self.recipient_id = recipient.user_id # Make our state mirror the database's
            self.accepted_at = now
            self.send_chips(ctx, self.sender)

            # If this invitation has a campaign name associated with it and if the recipient does not already
            # have a campaign name value, set it.
            if self.has_campaign_name() and not recipient.has_campaign_name():
                recipient.add_metadata("MET_CAMPAIGN_NAME", self.campaign_name)

            # Inform the callbacks that this invite was accepted.
            run_callback(USER_CB, "user_accepted_invite", ctx=ctx, recipient=recipient, invite=self)

    def modify_struct(self, struct, is_full_struct):
        struct['urls'] = {
            'invite_accept': self.url_invite_accept()
        }

        # Unusually for a 'urls' property, always send all of the URL values, even if is_full_struct is False.
        # This is because when the invite is accepted, this value will actually switch from
        # None to the recipient's public profile URL and we want that change included in the MOD chip.
        if self.was_accepted():
            struct['urls']['recipient_public_profile'] = urls.user_public_profile(self.recipient_id)
        else:
            struct['urls']['recipient_public_profile'] = None

        return struct

    ## Lazy load attribute methods.
    def _load_sender(self):
        # self.parent is user.invites, the parent of that is the User itself.
        return self.parent.parent

    def _load_recipient(self):
        # Have to import user_module this way to avoid a cyclic dependency import error.
        from front.models import user as user_module
        if self.recipient_id is None:
            return None
        with db.conn(self.ctx) as ctx:
            return user_module.user_from_context(ctx, self.recipient_id)

    def _load_gift(self):
        # Have to import user_module this way to avoid a cyclic dependency import error.
        from front.models import user as user_module
        with db.conn(self.ctx) as ctx:
            rows = db.rows(ctx, "get_gift_id_by_invite_id", invite_id=self.invite_id)
        if len(rows) == 0:
            return None
        # We do not assume the sender of the invitation is the gift creator so load the
        # gift creator and get the Gift object from their gifts_created.
        gift_id = get_uuid(rows[0]['gift_id'])
        creator = user_module.creator_from_gift_id(self.ctx, gift_id)
        return creator.gifts_created[gift_id]
