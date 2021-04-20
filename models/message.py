# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os, pkg_resources
import uuid

from mako import lookup

from front import models
from front.lib import db, get_uuid, urls, utils
from front.backend import deferred
from front.data import load_yaml_and_header, validate_struct, schemas, assets
from front.models import chips
from front.callbacks import run_callback, MESSAGE_CB

import logging
logger = logging.getLogger(__name__)

# The path relative to this package where the message data is stored.
MESSAGES_PATH = pkg_resources.resource_filename('front', 'templates/messages')
MESSAGE_TYPE_FILENAME = "message_types.yaml"

# Template cache.
_template_lookup = lookup.TemplateLookup(directories=[MESSAGES_PATH], input_encoding='utf-8', output_encoding='utf-8')
# Fields in msg_types which support Mako templating.
TEMPLATE_FIELDS = ['subject', 'body', 'body_locked']

# message style definitions.
class styles(object):
    DEFAULT     = "DEFAULT"
    LOCKED_DOCS = "LOCKED_DOCS"
    LIVE_CALL   = "LIVE_CALL"
    PASSWORD    = "PASSWORD"
    VIDEO       = "VIDEO"
    AUDIO       = "AUDIO"
    ATTACHMENT  = "ATTACHMENT"
    ALL = set([DEFAULT, LOCKED_DOCS, LIVE_CALL, PASSWORD, VIDEO, AUDIO, ATTACHMENT])

def send_all_now(ctx, user, msg_types):
    """
    Send all of the message types for this user now. The messages will be delivered in the order
    they are given, with just enough time between them to guarantee sort order.
    """
    # Leave enough seconds before now for every message being sent to be sent a second apart.
    send_at = user.epoch_now - utils.in_seconds(seconds=len(msg_types))
    for msg_t in msg_types:
        send_now(ctx, user, msg_t, _sent_at=send_at)
        send_at += utils.in_seconds(seconds=1) # One second between messages.

def send_now(ctx, user, msg_type, _sent_at=None):
    """
    This creates a new Message object and persists it. The message will have a sent_at time
    of "now".
    NOTE: If the should_deliver callback for this msg_type returns False then this message will NOT
    be delivered to this user and None will be returned from this function.
    NOTE: If the given msg_type has already been sent to this user, then this function will log
    a warning and return None indicating the message already existed. This behavior exists so that if the ordering
    of when messages are sent is changed on the live system to reflect for instance a change in the story, then
    if a user had already received a message in the previous version of the story it will not raise an exception here,
    hopefully allowing a smoother migration experience for existing users to the new story version.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param msg_type: str defining this message e.g MSG_WELCOME. Defined in message_types.json
    :param _sent_at: datetime object. Optionally override the sent_at time. This is *private API*.
        Use send_all_now or similar methods instead of setting this yourself.
    """
    # As we change the story script, sometimes we change the order when a message is being sent
    # in the game. This guard is intended to make that migration more smooth. NOTE: It is critical
    # that a given MSG_ key always refers to the same 'message concept'.
    if user.messages.by_type(msg_type) is not None:
        logger.warning("Refusing to send exising msg_type to user. [%s][%s]", msg_type, user.user_id)
        return None

    # Check with the should_deliver callback to make sure now is the right time to deliver this
    # message to this user.
    should_deliver = run_callback(MESSAGE_CB, "should_deliver", msg_type, ctx=ctx, user=user)
    if not should_deliver:
        return None

    if _sent_at is None:
        _sent_at = user.epoch_now

    # Lookup message description from the JSON file.
    msg_details = get_message_type(msg_type)
    params = {}
    params['message_id'] = uuid.uuid1()
    params['msg_type'] = msg_type
    params['sent_at'] = _sent_at
    params['read_at'] = None

    # Set the initial value of 'locked' based on 'needs_password'.
    params['locked'] = msg_details['needs_password']

    with db.conn(ctx) as ctx:
        # user_id is only used when creating the Message in the database, it is not loaded
        # by chips as the user.messages collection takes care of assigning a User to a Message.
        db.run(ctx, "insert_message", user_id=user.user_id, **params)
        m = user.messages.create_child(**params)
        # Send a chip for this message being added.
        m.send_chips(ctx, user)

        # Inform the callbacks that this message was sent.
        run_callback(MESSAGE_CB, "was_delivered", m.msg_type, ctx=ctx, user=user, message=m)
    return m

def send_later(ctx, user, msg_type, delay):
    """
    Request that a message be sent after a given delay.
    :param ctx: The database context.
    :param user: User instance to whom the message will be sent.
    :param msg_type: str defining this message e.g MSG_WELCOME. Defined in message_types.json
    :param delay: int, Number of seconds to wait before sending message.
    """
    deferred.run_later(ctx, deferred.types.MESSAGE, msg_type, user, delay)

def has_been_queued(ctx, user, msg_type):
    """
    Return True if the given msg_type has been queued for delivery for this user in the future,
    False otherwise.
    """
    return deferred.is_queued_to_run_later_for_user(ctx, deferred.types.MESSAGE, msg_type, user)

def keycode_for_msg_type(msg_type, user):
    """
    Returns the keycode string for the given msg_type. Used for locked messages.
    The keycode is derived from the msg_type and the user's uuid and is
    unique per msg_type and user. It is not stored in the database.
    """
    return utils.keycode_for_namespace('messages.keycode', msg_type, user.user_id)

class Message(chips.Model, models.UserChild):
    id_field = 'message_id'
    fields = frozenset(['msg_type', 'style', 'sender', 'sender_key', 'subject', 'sent_at', 'read_at',
                        'locked', 'needs_password'])
    computed_fields = {
        'sent_at_date': models.EpochDatetimeField('sent_at'),
        'read_at_date': models.EpochDatetimeField('read_at')
    }

    # user_id is a database only field.
    def __init__(self, message_id, user_id=None, **params):
        # If the UUID data is coming straight from the database row, convert it to a UUID instance.
        message_id = get_uuid(message_id)

        # Populate the fields which come from the message types data.
        msg_details = get_message_type(params['msg_type'])
        params['style'] = msg_details['style']
        params['sender'] = msg_details['sender']
        params['sender_key'] = msg_details['sender_key']
        params['subject'] = _render_template(msg_details['id'], 'subject')
        params['needs_password'] = msg_details['needs_password']

        super(Message, self).__init__(message_id=message_id, **params)

    @property
    def user(self):
        # self.parent is user.messages, the parent of that is the User itself
        return self.parent.parent

    @property
    def keycode(self):
        """
        Returns this messages keycode. See keycode_for_msg_type.
        """
        return keycode_for_msg_type(self.msg_type, self.user)

    def unlock(self, password):
        """
        Attempt to unlock this message with the given password. Returns a dict ready to be JSONified
        with an html payload and whether the unlock was successful.

        :param ctx: The database context.
        :param password: str the password to try and unlock with.
        """
        if not self.is_locked():
            logger.warning("Refusing to unlock unlocked message. [%s][%s]", self.msg_type, self.user.user_id)
            # Still return success to the caller though so the client doesn't freak out.
            return True, self.body_rendered()

        # Validate the provided password, lowercasing any alphabetic characters.
        if self.keycode == password.upper():
            with db.conn(self.ctx) as ctx:
                # Mark the database as unlocked.
                db.run(ctx, "update_message_locked", message_id=self.message_id, locked=0)
                self.locked = 0  # Make our state mirror the database's.
                self.send_chips(ctx, self.user)

                # Inform the callbacks that this message was unlocked.
                run_callback(MESSAGE_CB, "was_unlocked", self.msg_type, ctx=self.ctx, user=self.user, message=self)

            # And return the unlocked message content.
            return True, self.body_rendered()
        else:
            return False, self.body_rendered()

    def was_read(self):
        return self.read_at != None

    def is_locked(self):
        return self.locked != 0

    def does_need_password(self):
        return self.needs_password != 0

    def forward_to(self, recipient):
        run_callback(MESSAGE_CB, "forwarded_to", self.msg_type, self.ctx, self.user, message=self, recipient=recipient)

    def url_unlock(self):
        '''Construct the url we want to call to unlock this message.'''
        return urls.message_unlock(self.message_id)

    def url_forward(self):
        '''Construct the url we want to call to forward this message.'''
        return urls.message_forward(self.message_id)

    @property
    def url_sender_icon_small(self):
        return assets.sender_icon_url_for_dimension(self.sender_key, 27, 27)

    @property
    def url_sender_icon_large(self):
        return assets.sender_icon_url_for_dimension(self.sender_key, 72, 72)

    @property
    def url_icon(self):
        ''' Note: This logic should match the corresponding routine in message.js. '''
        if self.style == 'LIVE_CALL' and self.is_locked():
            return assets.message_icon_url('CALL_LOCKED')
        elif self.style == 'LIVE_CALL':
            return assets.message_icon_url('CALL_UNLOCKED')
        elif self.style == 'LOCKED_DOCS' and self.is_locked():
            return assets.message_icon_url('LOCKED')
        elif self.style == 'LOCKED_DOCS':
            return assets.message_icon_url('UNLOCKED')
        elif self.style == 'PASSWORD' and self.is_locked():
            return assets.message_icon_url('LOCKED')
        elif self.style == 'PASSWORD':
            return assets.message_icon_url('UNLOCKED')
        elif self.style == 'VIDEO':
            return assets.message_icon_url('VIDEO')
        elif self.style == 'AUDIO':
            return assets.message_icon_url('AUDIO')
        elif self.style == 'ATTACHMENT':
            return assets.message_icon_url('ATTACHMENT')
        return None

    def embed_video(self, video_id):
        '''Construct the HTML for embedding a video in a message.'''
        return '''<div class="message-video"><iframe src="https://player.vimeo.com/video/%s" width="800" height="450" frameborder="0"
            webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe></div>''' % (video_id)

    def embed_audio(self, video_id):
        '''Construct the HTML for embedding a video in a message.'''
        return '''<div class="message-video"><iframe src="https://player.vimeo.com/video/%s" width="600" height="100" frameborder="0"
            webkitAllowFullScreen mozallowfullscreen allowFullScreen></iframe></div>''' % (video_id)

    def embed_image(self, filename, width, height, optStyle=None):
        '''Construct the HTML for embedding an image in a message.
        :param filename: Image name within the messages image asset directory.
        :param width: Image width.
        :param height: Image height.
        :param optStyle: Optionally, CSS style parameters to include in the image tag.
        '''
        style = ''
        if optStyle:
            style = 'style="%s"' % optStyle
        return '<div class="message-image"><img src="/static/img/messages/%s" width=%d height=%d %s></div>' % (filename, width, height, style)

    def embed_blog_link(self, blog, link_text):
        '''Construct the HTML for linking to a blog post.'''
        return '<a href="http://www.exoresearch.com/blog/%s" target="_blank">%s</a>' % (blog, link_text)

    def embed_store_link(self, link_text):
        '''Construct the HTML for opening the store dialog.'''
        return '<a style="cursor: pointer;" onclick="ce4.ui.store.dialogOpen();">%s</a>' % (link_text)

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {
                'message_content': urls.message_content(self.message_id),
                'message_forward': self.url_forward()
            }
            if self.is_locked():
                struct['urls']['message_unlock'] = self.url_unlock()

    def load_content(self):
        """ Generates the message body from the template and returns a dict ready to be JSONified.
        :param ctx: The database context.
        """
        # Mark the message as read if it was not already.
        self.mark_as_read(self.ctx)
        return self.body_rendered()

    def body_rendered(self):
        # Render the body template for this message, either the locked body or unlocked body.
        if self.does_need_password() and self.is_locked():
            # This message requires authentication and is still locked
            return _render_template(self.msg_type, 'body_locked', {'msg': self})
        else:
            # This message does not require authentication or is unlocked
            return _render_template(self.msg_type, 'body', {'msg': self})

    def mark_as_read(self, ctx):
        # Only mark read if not already marked read.
        if self.read_at is not None:
            return

        with db.conn(ctx) as ctx:
            epoch_now = self.user.epoch_now
            db.run(ctx, "update_message_read_at", message_id=self.message_id, read_at=epoch_now)
            self.read_at = epoch_now  # Make our state mirror the database's.
            # Send a chip for the read_at change.
            self.send_chips(ctx, self.user)
            # Inform the callbacks that this message was read.
            run_callback(MESSAGE_CB, "was_read", self.msg_type, ctx=ctx, user=self.user, message=self)

    def append_attachment(self, filename, link_text):
        """
        Return a string that will serve as a link to an attached file within the message.
        """
        url = urls.message_attachment_root() + '/' + filename
        return "<div class='msg_attachment'><a href='%s' target='_blank'><img src='/static/img/messages/pdf.png'>%s</a></div>" % (url, link_text)

def is_known_msg_type(msg_type):
    """ Returns True if the given msg_type was defined in the message definitions. """
    return msg_type in _get_all_message_types()

def get_message_type(msg_type):
    """
    Return the message type details as a dictionary for the given message type.

    :param msg_type: str defining this message e.g MSG_WELCOME. Defined in message_types.json
    """
    return _get_all_message_types()[msg_type]

def _get_all_message_types():
    """ Return the decoded message type descriptions from the JSON data file. """
    return _g_msg_types

def _add_message_type(msg_type, msg_details):
    # Perform some additional validation, namely that
    # properties required by needs_password are present if needs_password is true.
    if msg_details['needs_password'] == 1:
        try:
            msg_details['body_locked']
        except KeyError, e:
            raise ValueError("If Message type 'needs_password' field is true, %s field is required. type=[%s]" % (str(e), msg_type))
    # Populate all of the templates as well.
    for field in TEMPLATE_FIELDS:
        if field in msg_details:
            _template_lookup.put_string(_template_uri(msg_type, field), msg_details[field])
    _g_msg_types[msg_type] = msg_details

def _render_template(msg_type, field, template_data=None):
    """
    Render a message field (e.g. from, subject, body) using the given msg_type and field name.
    E.g. MSG_WELCOME, 'body'

    :param msg_type: str The msg_type string to be rendered.
    :param field: str The field name being rendered, e.g. body or subject.
    :param template_data: dict the template data to supply during rendering.
    """
    if template_data is None:
        template_data = {}
    # Add in the default template keys that are available to every template.
    template_data['urls'] = urls

    # Create a unique key for this message id and field, e.g. MSG_WELCOME::body
    template_uri = _template_uri(msg_type, field)
    template = _template_lookup.get_template(template_uri)
    return template.render(**template_data)

def _template_uri(msg_type, field):
    return msg_type + "::" + field

_g_msg_types = None
def init_module():
    global _g_msg_types
    if _g_msg_types is not None: return

    _g_msg_types = {}
    header, yaml_documents = load_yaml_and_header(os.path.join(MESSAGES_PATH, MESSAGE_TYPE_FILENAME))

    # The header is the subjects mappings
    SENDERS = header['SENDERS']

    for msg_type in yaml_documents:
        # Default value for needs_password
        if msg_type.get('needs_password') is None:
            msg_type['needs_password'] = 0
        # Keep the sender key from the msg_types as a sender_key value so the client can use it.
        msg_type['sender_key'] = msg_type['sender']
        # Insert the real sender name.
        msg_type['sender'] = SENDERS[msg_type['sender']]
        # If no style attribute was provided, set it to the default.
        if msg_type.get('style') is None:
            msg_type['style'] = styles.DEFAULT
        else:
            assert msg_type['style'] in styles.ALL, "style must be a known value [%s]" % msg_type['style']

        assert msg_type['id'] not in _g_msg_types # msg_type must be unique.
        _add_message_type(msg_type['id'], msg_type)

    # Pass the msg_types structure through the validator.
    validate_struct(_g_msg_types, schemas.MESSAGE_TYPES)
