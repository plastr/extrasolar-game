# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# NOTE: This module is called email_module as naming it email
# can cause a conflict with the builtin email module name.
import os, pkg_resources
from mako import lookup

from front.lib import urls, email_ses
from front.backend import deferred, email_queue
from front.data import load_yaml_and_header, validate_struct, schemas, assets
from front.callbacks import run_callback, EMAIL_CB

# Currently used dispatcher object. See init_module.
_DISPATCHER = None

# The path relative to this package where the email template data is stored.
_EMAIL_PATH = pkg_resources.resource_filename('front', 'templates/emails')
_EMAIL_TYPE_FILENAME = "email_types.yaml"

# Template cache.
_template_lookup = lookup.TemplateLookup(directories=[_EMAIL_PATH], input_encoding='utf-8', output_encoding='utf-8')
# Fields in msg_types which support Mako templating.
TEMPLATE_FIELDS = ['subject', 'body']

def send_now(ctx, user, email_type, template_data={}):
    """
    Send an email message to the given user now.
    :param ctx: The database context.
    :param user: User instance to whom the message will be sent.
    :param email_type: str defining this email template e.g EMAIL_WELCOME. Defined in email_types.json
    :param template_data: dict, values that will be merged into the template.
    """
    # Check with the should_send callback to make sure now is the right time to deliver this
    # email to this user and to collect any template context data.
    should_send, template_context = run_callback(EMAIL_CB, "should_send", email_type, ctx=ctx, user=user)
    if not should_send:
        return None

    # If the user doesn't have an email address, don't send.
    if not user.email:
        return None

    # Add the user to the template data.
    template_data['user'] = user

    # Merge in any template context data from the should_send callback.
    template_data.update(template_context)

    # Send to the user email address.
    email_message = send_now_to_address(ctx, user.email, email_type, template_data)

    # Inform the callbacks that this email was sent or queued.
    run_callback(EMAIL_CB, "was_sent_or_queued", email_type, ctx=ctx, user=user, email_message=email_message)

def send_now_to_address(ctx, address, email_type, template_data={}):
    """
    Send an email message to the given email address. Might be added to an email sending queue if enabled.
    :param ctx: The database context.
    :param address: The email address to send this message to.
    :param email_type: str defining this email template e.g EMAIL_WELCOME. Defined in email_types.json
    :param template_data: dict, values that will be merged into the template.
    """
    email_message = EmailMessage.from_email_type(address, email_type, template_data)
    _DISPATCHER.send_email_message(ctx, email_message)
    return email_message

def send_alarm(address, email_type, template_data={}):
    """
    Send an email message to the given email address immediately, bypassing any queues or database system.
    :param address: The email address to send this message to.
    :param email_type: str defining this email template e.g EMAIL_WELCOME. Defined in email_types.json
    :param template_data: dict, values that will be merged into the template.
    """
    email_message = EmailMessage.from_email_type(address, email_type, template_data)
    _DISPATCHER.send_email_alarm(email_message)
    return email_message

def send_later(ctx, user, email_type, delay, template_data={}):
    """
    Request that an email be sent after a given delay.
    :param ctx: The database context.
    :param user: User instance to whom the message will be sent.
    :param email_type: str defining this email template e.g EMAIL_WELCOME. Defined in email_types.json
    :param delay: int, Number of seconds to wait before sending message.
    :param template_data: dict, values that will be merged into the template.
    """
    deferred.run_later(ctx, deferred.types.EMAIL, email_type, user, delay)

# Class to hold email payload data, mostly used internally by the email modules and testing systems.
class EmailMessage(object):
    def __init__(self, email_from, email_to, subject, body_html):
        self.email_from = email_from
        self.email_to   = email_to
        self.subject    = subject
        self.body_html  = body_html

    @classmethod
    def from_email_type(cls, email_to, email_type, template_data={}):
        # Load the email type configuration
        email_details = _get_email_type(email_type)

        # Add default values to template data.
        template_data['urls'] = urls
        template_data['assets'] = assets
        return cls(
            email_from = email_details['sender'],
            email_to   = email_to,
            subject    = _render_template(email_details, 'subject', template_data),
            body_html  = _render_template(email_details, 'body', template_data)
        )

## These classes implement different behavior when sending emails, mainly to allow for different behavior
## in development, testing, and production modes. They are not meant to be public API.
class EchoDispatcher(object):
    def __init__(self, quiet=False):
        self.quiet = quiet

    def send_email_message(self, ctx, email_message):
        if not self.quiet:
            print "Email would have been sent to email_queue:"
            print "From: " + email_message.email_from
            print "To: " + email_message.email_to
            print "Subject: " + email_message.subject
            print "Body: " + email_message.body_html

    def send_email_alarm(self, email_message):
        self.send_email_message(None, email_message)

class QueueDispatcher(object):
    def send_email_message(self, ctx, email_message):
        # Send normal messages to the email queue.
        email_queue.enqueue_email_message(ctx, email_message)

    def send_email_alarm(self, email_message):
        # Send alarms immediately to the SES module for delivery.
        email_ses.send_email(email_message.email_from, email_message.email_to,
                             email_message.subject, email_message.body_html)

def set_echo_dispatcher(quiet=False):
    global _DISPATCHER
    _DISPATCHER = EchoDispatcher(quiet=quiet)

def set_capture_dispatcher(capture_dispatcher):
    """ The supplied object must conform to the 'Dispatcher' API, see send_email_message and send_email_alarm. """
    global _DISPATCHER
    _DISPATCHER = capture_dispatcher

def set_queue_dispatcher():
    global _DISPATCHER
    _DISPATCHER = QueueDispatcher()

def _get_all_email_types():
    """ Return the email type descriptions as loaded from the YAML data file. """
    return _g_email_types

def _get_email_type(email_type):
    """
    Return the email type details as a dictionary for the given email type.
    :param email_type: str defining this email e.g EMAIL_VERIFY. Defined in email_types.json
    """
    return _get_all_email_types()[email_type]

def _render_template(email_type, field, template_data=None):
    """
    Render an email field (e.g. from, subject, body) using the given email type data and field name.
    E.g. {id:EMAIL_VERIFY}, 'body'

    :param email_type: dict The email type data.
    :param field: str The field name being rendered, e.g. body or subject.
    :param template_data: dict the template data to supply during rendering.
    """
    if template_data is None:
        template_data = {}
    # Create a unique key for this email id and field, e.g. EMAIL_VERIFY::body
    template_uri = _template_uri(email_type, field)
    template = _template_lookup.get_template(template_uri)
    return template.render(**template_data)

def _template_uri(email_type, field):
    return email_type['id'] + "::" + field

_g_email_types = None
def init_module(dispatcher_type):
    # Set the initial dispatcher type/mode from the config parameter.
    if dispatcher_type == "ECHO":
        set_echo_dispatcher()
    elif dispatcher_type == "QUEUE":
        set_queue_dispatcher()
    else:
        raise Exception("Unknown email module dispatcher in .ini [%s]" % dispatcher_type)

    global _g_email_types
    if _g_email_types is not None: return

    _g_email_types = {}
    header, yaml_documents = load_yaml_and_header(os.path.join(os.path.join(_EMAIL_PATH, _EMAIL_TYPE_FILENAME)))

    # The header is the subjects mappings
    SENDERS = header['SENDERS']

    for email_type in yaml_documents:
        # Insert the real sender name.
        email_type['sender'] = SENDERS[email_type['sender']]

        assert email_type['id'] not in _g_email_types # Email ids must be unique.
        _g_email_types[email_type['id']] = email_type

        # Populate all of the templates as well.
        for field in TEMPLATE_FIELDS:
            if field in email_type:
                _template_lookup.put_string(_template_uri(email_type, field), email_type[field])

    # Pass the email_types structure through the validator.
    validate_struct(_g_email_types, schemas.EMAIL_TYPES)
