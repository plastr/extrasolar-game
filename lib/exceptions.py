# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import traceback, os
from wsgiref.util import request_uri

from front import VERSION
from front.lib import email_module, gametime, urls

import logging
logger = logging.getLogger(__name__)

# The email template name used when composing the exception email.
TEMPLATE_NAME = "EMAIL_ADMIN_EXCEPTION"

# Note: These values should be initialized outside of this module, likely during application init.
_EXCEPTION_EMAIL_ADDRESS = None

def init_module(exception_email_address):
    global _EXCEPTION_EMAIL_ADDRESS
    _EXCEPTION_EMAIL_ADDRESS = exception_email_address

class notify_on_exception(object):
    """
    Context manager which emails an exception report to an email address configured in this module
    if that address has been set. This modules init_module must be called for an email to be sent
    with the desired recipient address passed as the value.
    :param context: dict, optional additional data to provide to exception email template e.g.
        the WSGI environ dictionary.
    :param parse_context: func, optional function to parse the context object before being supplied to
        the template.
    Use as::
        exceptions.init_module('test@example.com')
        with db.notify_on_exception():
            run_some_code()
    """
    def __init__(self, context=None, parse_context=None):
        self.context = context
        self.parse_context = parse_context

    def __enter__(self):
        return self

    def __exit__(self, exception_type, value, tb):
        # If there is no exception email configured do nothing.
        if _EXCEPTION_EMAIL_ADDRESS is None:
            return

        # If there was and exception and an email address configured, notify
        # about the exception.
        if exception_type is not None:
            try:
                template_data = {
                    'gametime': gametime.now(),
                    'version': VERSION,
                    'hostname': os.uname()[1],
                    'exception_type': exception_type,
                    'value': value,
                    'traceback_list': traceback.format_tb(tb)
                }
                if self.context is not None:
                    if self.parse_context is not None:
                        template_data.update(self.parse_context(self.context))
                    else:
                        template_data.update(self.context)
                email_module.send_alarm(_EXCEPTION_EMAIL_ADDRESS, TEMPLATE_NAME, template_data=template_data)
            except:
                logger.exception("Notifying on exception failed to address: %s", _EXCEPTION_EMAIL_ADDRESS);

class NotifyExceptionMiddleware(object):
    """
    A WSGI middlware compatible object which wraps the WSGI application in a context manager
    which emails an exception report to an email address configured in this module if that address has been set.
    """
    def __init__(self, app, config=None):
        self.app = app
        config = config or {}

    def __call__(self, environ, start_response):
        with notify_on_exception(context=environ, parse_context=parse_environ):
            return self.app(environ, start_response)

def parse_environ(e):
    parsed = {
        'has_request': True,
        'request_url': request_uri(e)
    }
    if 'beaker.session' in e:
        if 'user_id' in e['beaker.session']:
            user_id = e['beaker.session']['user_id']
            parsed.update({
                'has_logged_in_user': True,
                'user_id': user_id,
                'url_admin_user': urls.tools_absolute_root() + urls.admin_user(user_id)
            })
    return parsed
