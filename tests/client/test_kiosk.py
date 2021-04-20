# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base
from front.tests.base import PROTECTED_URL

from front.lib import urls
from front.resource import kiosk_node

class TestKiosk(base.TestCase):
    URL_BASE = urls.kiosk()
    URL_COMPLETE = urls.kiosk_complete()
    URL_COMPLETE_EXISTS = urls.kiosk_complete_exists()
    KIOSK_MODE = kiosk_node.KioskNode.KIOSK_MODE
    # Set in setUp as pulled from ini on initialization of stack.
    CAMPAIGN_NAME = None
    def setUp(self):
        super(TestKiosk, self).setUp()
        self.CAMPAIGN_NAME = kiosk_node.KioskNode.CAMPAIGN_NAME

    def test_get_html(self):
        # just verify that there's something like an html form in there
        response = self.app.get(self.URL_BASE)
        self.assert_('KIOSK_MODE = "%s"' % self.KIOSK_MODE in response)
        form = response.forms['form_signup']
        self.assertEqual(form.method, 'POST')
        self.assert_('signup_email' in form.fields)
        self.assert_('signup_password' in form.fields)

    def test_signup_user(self):
        self.assertEqual(len(self.get_sent_emails()), 0)
        response = self.app.get(self.URL_BASE)
        form = response.forms['form_signup']
        form['signup_email'] = 'testuser@example.com'
        form['first_name'] = "MyFirstName"
        form['last_name'] = "MyLastName"
        form['signup_password'] = "password"
        form['signup_age'] = True
        form['signup_terms'] = True
        response = form.submit()
        # The kiosk signed up user should redirect back to /kiosk/complete and should be logged in.
        response = response.follow()
        self.assertEqual(self.URL_COMPLETE, response.request.path_qs)
        self.assert_logged_in(self.app.get(PROTECTED_URL))
        # Be sure the signup email was sent.
        self.assertEqual(len(self.get_sent_emails()), 1)
        # Every kiosk signed up user should get a known campaign name metadata key.
        user = self.get_user_by_email('testuser@example.com')
        self.assertEqual(user.campaign_name, self.CAMPAIGN_NAME)

        # Attempting to kiosk signup again with the new users credentials should redirect to
        # /kiosk/complete with a query parameter rather than logging in and redirecting to /ops which is
        # the normal signup behavior.
        response = form.submit()
        response = response.follow()
        self.assertEqual(self.URL_COMPLETE_EXISTS, response.request.path_qs)
        self.assert_logged_in(self.app.get(PROTECTED_URL))
        self.assertTrue('already received your application' in response)

        # Reload the /kiosk page, which should log us out.
        response = self.app.get(self.URL_BASE)
        self.assert_not_logged_in(self.app.get(PROTECTED_URL))

    def test_signup_exising_user_bad_password(self):
        self.create_user('testuser@example.com', 'password')

        response = self.app.get(self.URL_BASE)
        form = response.forms['form_signup']
        form['signup_email'] = 'testuser@example.com'
        form['first_name'] = "MyFirstName"
        form['last_name'] = "MyLastName"
        form['signup_password'] = "bad_password"
        form['signup_age'] = True
        form['signup_terms'] = True
        response = form.submit()
        # Should still be on the /kiosk page but as signup_error and a special <span>.
        self.assertTrue('already taken' in response)
        self.assertTrue('signup_error_server' in response)

    def test_signup_user_stomps_campaign(self):
        # If an explicit campaign name is passed to the kiosk, verify the correct thing happens.
        campaign_name = 'some_campaign'
        response = self.app.get(urls.add_campaign_name_url_param(self.URL_BASE, campaign_name))
        form = response.forms['form_signup']
        form['signup_email'] = 'testuser@example.com'
        form['first_name'] = "MyFirstName"
        form['last_name'] = "MyLastName"
        form['signup_password'] = "password"
        response = form.submit()
        # The campaign name passed in through the URL should override the one defined in the configuration.
        user = self.get_user_by_email('testuser@example.com')
        self.assertEqual(user.campaign_name, campaign_name)

    def test_signup_user_bogus_email(self):
        response = self.app.get(self.URL_BASE)
        form = response.forms['form_signup']
        form['signup_email'] = 'invalid&domain'
        form['first_name'] = "MyFirstName"
        form['last_name'] = "MyLastName"
        form['signup_password'] = "password"
        form['signup_age'] = True
        form['signup_terms'] = True
        response = form.submit()
        self.assertTrue('Email address does not appear valid' in response)

class TestDemo(TestKiosk):
    URL_BASE = urls.demo()
    URL_COMPLETE = urls.demo_complete()
    URL_COMPLETE_EXISTS = urls.demo_complete_exists()
    KIOSK_MODE = kiosk_node.DemoNode.KIOSK_MODE
    # Set in setUp as pulled from ini on initialization of stack.
    CAMPAIGN_NAME = None
    def setUp(self):
        super(TestDemo, self).setUp()
        self.CAMPAIGN_NAME = kiosk_node.DemoNode.CAMPAIGN_NAME
