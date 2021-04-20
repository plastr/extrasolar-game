# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base

from front.lib import exceptions
from front.lib.exceptions import notify_on_exception

class TestExceptions(base.TestCase):
    def test_notify_on_exception(self):
        # Initialize the module so an email will be sent.
        exceptions.init_module("test@example.com")

        # If not exception happened, no email should be sent.
        with notify_on_exception():
            pass
        self.assertEqual(len(self.get_sent_emails()), 0)

        # If an exception happened, an email should have been sent.
        raised = False
        try:
            with notify_on_exception():
                raise Exception("Testing exception system")
        except:
            raised = True
        self.assert_(raised)

        # Check the email for the exception text and traceback (using this file base module name)
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertTrue("Exception" in self.get_sent_emails()[0].subject)
        self.assertTrue("Testing exception system" in self.get_sent_emails()[0].body_html)
        self.assertTrue(__name__.split(".")[-1] in self.get_sent_emails()[0].body_html)

        self.clear_sent_emails()
        # If the module is not configured, no email should be sent.
        exceptions.init_module(None)
        raised = False
        try:
            with notify_on_exception():
                raise Exception("Testing exception system")
        except:
            raised = True
        self.assert_(raised)
        self.assertEqual(len(self.get_sent_emails()), 0)

    def test_notify_exception_middleware(self):
        class RaiseExceptionMiddleware(object):
            def __init__(self, app, config=None):
                self.app = app
                config = config or {}
            def __call__(self, environ, start_response):
                def _error_response(status, response_headers, exc_info=None):
                    raise Exception("Testing exception system")
                self.app(environ, _error_response)

        # Initialize the module so an email will be sent.
        exceptions.init_module("test@example.com")

        # Create and login a user before modifying the WSGI stack and verify that user data is in the
        # exception email since there is a valid session.
        self.create_user('testuser@example.com', 'pw')
        user = self.get_logged_in_user()

        # Wrap the TestApp instance for this test in a middleware that always raises an exception.
        # NOTE: It is assumed that a NotifyExceptionMiddleware is already in this stack.
        self.app.app = RaiseExceptionMiddleware(self.app.app)

        # Verify that an exception raised in the WSGI stack results in an email.
        self._raise_request_exception()
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertTrue("Exception" in self.get_sent_emails()[0].subject)
        self.assertTrue("Testing exception system" in self.get_sent_emails()[0].body_html)
        self.assertTrue(user.url_admin() in self.get_sent_emails()[0].body_html)
        self.assertTrue(__name__.split(".")[-1] in self.get_sent_emails()[0].body_html)

        # Now logout which clears the session data and verify no user data is in the exception email.
        self.clear_sent_emails()
        self.logout_user()
        self._raise_request_exception()
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertTrue("Testing exception system" in self.get_sent_emails()[0].body_html)
        self.assertFalse(user.url_admin() in self.get_sent_emails()[0].body_html)

    def _raise_request_exception(self):
        raised = False
        try:
            self.app.get("/raise_exception")
        except:
            raised = True
        self.assert_(raised)
