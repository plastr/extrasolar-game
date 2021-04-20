# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# This module is a thin wrapper around Amazon's SES library
from front.external import amazon_ses

import logging
logger = logging.getLogger(__name__)

# Note: These key values should be initialized outside of this module, likely
# during application init. See init_module.
_ACCESS_KEY_ID = None
_SECRET_ACCESS_KEY = None

def init_module(dispatcher_type, access_key, secret_key):
    global _ACCESS_KEY_ID, _SECRET_ACCESS_KEY
    _ACCESS_KEY_ID = access_key
    _SECRET_ACCESS_KEY = secret_key
    # Based on the email_modfule dispatcher type/mode from the config parameter.
    if dispatcher_type == "ECHO":
        _suppress_email_delivery(_echo_deliver_email_to_ses)
    elif dispatcher_type == "QUEUE":
        # This module defaults to QUEUE mode, e.g. sending emails to Amazon SES.
        pass
    else:
        raise Exception("Unknown email module dispatcher in .ini [%s]" % dispatcher_type)

class EmailSendFailed(Exception):
    """
    Exception that is raised when an email is not successfully sent.
    """
    def __init__(self, message):
        Exception.__init__(self, message)
        self.message = message

def send_email(email_from, email_to, subject, body_html):
    # Create the SES email object from the email_module EmailMessage.
    # Will raise an EmailSendFailed if the email failed to be delivered to Amazon SES.
    ses_email_message = amazon_ses.EmailMessage()
    ses_email_message.subject  = subject
    ses_email_message.bodyHtml = body_html
    try:
        return _deliver_email_to_ses(email_from, email_to, ses_email_message)
    # If there was an AmazonError, convert that into an EmailSendFailed.
    except amazon_ses.AmazonError, e:
        msg = "Amazon send mail failed. ErrorType=[%s], code=[%s], message=[%s]" % (e.errorType, e.code, e.message)
        raise EmailSendFailed(msg)

def _deliver_email_to_ses(email_from, email_to, ses_email_message):
    amazonSes = amazon_ses.AmazonSES(_ACCESS_KEY_ID, _SECRET_ACCESS_KEY)
    # Returns a result of type AmazonSendEmailResult or throws an AmazonError.
    return amazonSes.sendEmail(email_from, email_to, ses_email_message)

def _suppress_email_delivery(callback):
    """ Suppress the normal email delivery system by not sending the messages to Amazon SES
        by providing a callback function instead which will have the email_from, email_to and ses_email_message
        passed to it (same API as _deliver_message)"""
    global _deliver_email_to_ses
    _deliver_email_to_ses = callback

def _echo_deliver_email_to_ses(email_from, email_to, ses_email_message):
    print "Email would have been sent to Amazon SES:"
    print "From: " + email_from
    print "To: " + email_to
    print "Subject: " + ses_email_message.subject
    print "Body: " + ses_email_message.bodyHtml
