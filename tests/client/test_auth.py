# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re
from front.tests import base
from front.tests.base import PROTECTED_URL

from front import InitialMessages
from front.lib import urls
from front.models import user as user_module
from front.resource.auth import password as password_node

class TestSignup(base.TestCase):
    def test_get_html(self):
        # just verify that there's something like an html form in there
        response = self.app.get(urls.auth_signup())
        form = response.forms['form_signup']
        self.assertEqual(form.action, urls.auth_signup())
        self.assertEqual(form.method, 'POST')
        self.assert_('signup_email' in form.fields)
        self.assert_('signup_password' in form.fields)

    def test_signup_user(self):
        self.signup_user('testuser@example.com', 'password', first_name='MyFirstName', last_name='MyLastName')
        user = self.get_logged_in_user()
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertEqual(user.first_name, 'MyFirstName')
        self.assertEqual(user.last_name, 'MyLastName')
        self.assertEqual(user.campaign_name, '')

    def test_signup_user_with_campaign_name(self):
        self.signup_user('testuser@example.com', 'password', campaign_name="testing_campaign")
        user = self.get_logged_in_user()
        self.assertEqual(user.campaign_name, 'testing_campaign')

    def test_signup_user_strip_lowercase(self):
        self.signup_user(' TeStuSeR@examplE.Com  ', 'password', first_name=' WhiteSpace  ', last_name=' WhiteSpace  ')
        user = self.get_logged_in_user()
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertEqual(user.first_name, 'WhiteSpace')
        self.assertEqual(user.last_name, 'WhiteSpace')

    def test_signup_user_and_validate(self):
        self.signup_user('testuser@example.com', 'password', first_name='MyFirstName', last_name='MyLastName')
        user = self.get_logged_in_user()
        self.assertEqual(user.email, 'testuser@example.com')
        self.assertEqual(user.first_name, 'MyFirstName')
        self.assertEqual(user.last_name, 'MyLastName')
        self.assertFalse(user.valid)
        # Clear the application recieved email.
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.clear_sent_emails()

        # Loading / before validation when logged in should display unauthorized warning.
        response = self.app.get(urls.auth_signup_complete())
        self.assertTrue('No Available Rovers' in response)

        # Loading /ops should redirect to / with unauthorized/invalid warning.
        response = self.app.get(urls.ops())
        response = response.follow()
        self.assertEqual(urls.root(), response.request.path)

        # Send the verify email.
        self.advance_game(minutes=InitialMessages.EMAIL_VERIFY_DELAY_MINUTES)
        self.assertEqual(len(self.get_sent_emails()), 1)
        # Pull the verify/backdoor URL out of the verify email body.
        backdoor_url = re.search(user.url_validate(), self.get_sent_emails()[-1].body_html).group(0)
        self.clear_sent_emails()

        # Load a bogus validation token and verify we get an error.
        bogus_backdoor_url = urls.validate('bogus')
        self.expect_log('front.models.user', 'Invalid token when attempting user validation.*')
        response = self.app.get(bogus_backdoor_url)
        response = response.follow()
        self.assertTrue(urls.root() in response.request.path)

        # Follow the backdoor link. The user should now be validated.
        response = self.app.get(backdoor_url)
        user = self.get_logged_in_user()
        self.assertTrue(user.valid)
        # Send and verify the welcome email.
        self.advance_game(minutes=InitialMessages.EMAIL_WELCOME_DELAY_MINUTES)
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.clear_sent_emails()

        # Load the backdoor URL again and verify we are redirected to /ops.
        response = self.app.get(backdoor_url)
        response = response.follow()
        self.assertTrue(urls.ops() in response.request.path)

        # Load a bogus validation token and verify we redirect to /ops (as we are logged in).
        response = self.app.get(bogus_backdoor_url)
        response = response.follow()
        self.assertTrue(urls.ops() in response.request.path)

        # Loading / should now redirect to /ops as well.
        response = self.app.get(urls.root())
        response = response.follow()
        self.assertTrue(urls.ops() in response.request.path)

        # Now signout and try the real and bogus backdoor URLs, both of which should redirect to /.
        self.logout_user()

        response = self.app.get(backdoor_url)
        response = response.follow()
        self.assertEqual(urls.root(), response.request.path)

        response = self.app.get(bogus_backdoor_url)
        response = response.follow()
        self.assertEqual(urls.root(), response.request.path)

    def test_signup_user_and_simple_login_not_valid(self):
        # Signing up a user which is not yet validated and using the simple login page should
        # still result in the user being redirect to the root page and seeing the Unauthorized Access page.
        self.signup_user('testuser@example.com', 'password')

        # Loading / before validation when logged in should display unauthorized warning.
        response = self.app.get(urls.auth_signup_complete())
        self.assertTrue('No Available Rovers' in response)

        # Logging in via the simple login page before validation should redirect to the over capacity page
        # and display unauthorized warning on root.
        self.logout_user()
        response = self.login_user('testuser@example.com', 'password', req_url=urls.auth_login_simple())
        response = response.follow()
        self.assertTrue('No Available Rovers' in response)
        self.assertEqual(urls.auth_signup_complete(), response.request.path)

    def test_signup_user_twice(self):
        self.signup_user('testuser2@example.com', 'password2')
        # Filling out the signup form with the same information for a valid user should result in a login.
        self.logout_user()
        response = self.signup_user('testuser2@example.com', 'password2', redirect_to=PROTECTED_URL)
        self.assertEqual(response.request.path, PROTECTED_URL)

        # Filling out the signup form with an existing email but wrong password should result in a failed login.
        self.logout_user()
        response = self.signup_user('testuser2@example.com', 'wrong_password', redirect_to=None)
        self.assert_("already taken" in response)

    def test_signup_user_bogus_email(self):
        response = self.signup_user('invalid&domain', 'password', redirect_to=None)
        self.assertTrue('Email address does not appear valid' in response)

    def test_signup_user_unicode_password(self):
        self.signup_user('testuser@example.com', 'pa\xd9\xadword', redirect_to=None)
        self.logout_user()
        self.login_user('testuser@example.com', 'pa\xd9\xadword')
        self.assert_logged_in(self.app.get(PROTECTED_URL))

    def test_signup_redirection(self):
        response = self.signup_user('testuser3@example.com', 'password3', redirect_to=PROTECTED_URL)
        self.assertEqual(response.request.path, PROTECTED_URL)

    def test_signups_enabled_setting(self):
        # Grab the form before disabling signups to be sure POST also fails.
        response = self.app.get(urls.root())
        self.assertTrue('form_signup' in response)
        form = response.forms['form_signup']
        form['signup_email'] = 'testuser@example.com'
        form['first_name'] = "MyFirstName"
        form['last_name'] = "MyLastName"
        form['signup_password'] = "password"
        form['signup_age'] = True
        form['signup_terms'] = True

        original_value = password_node.SIGNUPS_ENABLED
        password_node.SIGNUPS_ENABLED = False

        # Attempting to post a new signup form when signups are disabled which should raise an Exception.
        self.assertRaises(AssertionError, form.submit)
        # The signup_form should not be rendered on the root page either.
        response = self.app.get(urls.root())
        self.assertTrue('form_signup' not in response)

        # Restore whatever the original value was.
        password_node.SIGNUPS_ENABLED = original_value

    def test_signup_logs_in(self):
        self.signup_user('testuser4@example.com', 'password4')
        self.assert_logged_in(self.app.get(PROTECTED_URL))

class TestLogin(base.TestCase):
    def setUp(self):
        super(TestLogin, self).setUp()
        self.create_validated_user('testuser@example.com', 'pw')
        self.logout_user()

    def test_protected_page(self):
        # Attempting to load an auth protected page while not logged in should redirect to the
        # simple login page, not the root login/signup page.
        response = self.app.get(PROTECTED_URL)
        self.assert_not_logged_in(response)
        response = response.follow()
        self.assertEqual(urls.auth_login_simple(), response.request.path)
        # And now login and verify everything worked.
        response = self.login_user('testuser@example.com', 'pw', req_url=urls.auth_login_simple(), redirect_to=PROTECTED_URL)
        self.assert_logged_in(response)
        self.assertEqual(PROTECTED_URL, response.request.path)

    def test_logged_in_failure(self):
        response = self.login_user('testuser@example.com', 'not_my_password', redirect_to=None, status=401)
        self.assert_("Email or password incorrect" in response)
        self.assert_not_logged_in(self.app.get(PROTECTED_URL))

    def test_logged_in_blank(self):
        response = self.login_user('testuser@example.com', '', redirect_to=None, status=401)
        self.assert_("Required data not provided" in response)
        response = self.login_user('', 'pw', redirect_to=None, status=401)
        self.assert_("Required data not provided" in response)

    def test_logged_strip_lowercase(self):
        self.login_user(' TeStuSeR@examplE.Com  ', 'pw')
        self.assert_logged_in(self.app.get(PROTECTED_URL))

    def test_logged_in_page(self):
        self.login_user('testuser@example.com', 'pw')
        self.assert_logged_in(self.app.get(PROTECTED_URL))

    def test_login_redirection(self):
        response = self.login_user('testuser@example.com', 'pw', redirect_to=PROTECTED_URL)
        self.assertEqual(response.request.path, PROTECTED_URL)

    def test_login_simple(self):
        response = self.login_user('testuser@example.com', 'pw', redirect_to=PROTECTED_URL, req_url=urls.auth_login_simple())
        self.assertEqual(response.request.path, PROTECTED_URL)

        # Attempting to load the simple login page with a valid session should redirect to the root which
        # if the user is valid will send them to ops.
        response = self.app.get(urls.auth_login_simple())
        response = response.follow()
        self.assertEqual(response.request.path, urls.root())
        response = response.follow()
        self.assertEqual(response.request.path, urls.ops())

        self.logout_user()
        response = self.login_user('testuser@example.com', 'not_my_password', redirect_to=None, status=401, req_url=urls.auth_login_simple())
        self.assert_("Email or password incorrect" in response)

class TestLogout(base.TestCase):
    def setUp(self):
        super(TestLogout, self).setUp()
        self.signup_user('testuser@example.com', 'pw')

    def test_logout_post(self):
        self.app.post(urls.auth_logout())
        self.assert_not_logged_in(self.app.get(PROTECTED_URL))

    def test_logout_get(self):
        self.app.get(urls.auth_logout())
        self.assert_not_logged_in(self.app.get(PROTECTED_URL))
        self.app.get(urls.auth_logout())

class TestPasswordReset(base.TestCase):
    def setUp(self):
        super(TestPasswordReset, self).setUp()
        self.create_validated_user('testuser@example.com', 'pw')

    def test_password_reset(self):
        user = self.get_logged_in_user()
        email = user.email
        # Start from logged out state.
        self.logout_user()

        # Load the reset page and make a request to reset this accounts password.
        response = self.app.get(urls.request_password_reset())
        form = response.forms['form_request_password_reset']
        # Try a bogus email first.
        form['email'] = "nosuchuser@example.com"
        response = form.submit()
        response = response.follow()
        self.assertTrue("There is no user for that email." in response)
        # And now the actual email.
        form['email'] = email
        response = form.submit()
        response = response.follow()
        self.assertTrue("Email sent." in response)
        self.assertTrue("form_request_password_reset" not in response)

        # Verify the reset email was sent and pull the reset URL out of the email.
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertTrue("Password Reset" in self.get_sent_emails()[0].subject)
        RESET_PATTERN = re.compile(r'<a href="' + urls.tools_absolute_root() + '/(reset.*)">')
        url_password_reset = "/" + RESET_PATTERN.search(self.get_sent_emails()[0].body_html).group(1)

        # Follow the reset link and set the new password.
        response = self.app.get(url_password_reset)
        form = response.forms['form_password_reset']
        form['new_password'] = "new_password"
        response = form.submit()
        response = response.follow()
        # Successfully changing the password should show a success page with a link to ops.
        # The user should also have been logged in.
        self.assertTrue("Your password has been changed." in response)
        response = response.click(href=urls.ops())
        self.assert_logged_in(response)

        # Now logout.
        self.logout_user()
        # Try the old password, which should error 401
        response = self.login_user('testuser@example.com', 'pw', redirect_to=None, status=401)
        # Try the new password, which should redirect to /ops as expected.
        response = self.login_user('testuser@example.com', 'new_password')
        response = response.follow()
        self.assert_logged_in(response)

        # Logout again.
        self.logout_user()

        # Token should be invalid now that the password hash has changed.
        self.expect_log('front.resource.auth.password', 'Invalid token when attempting password reset.*')
        response = self.app.get(url_password_reset)
        self.assertTrue("Password reset link has expired or is invalid." in response)

    def test_password_reset_expired(self):
        user = self.get_logged_in_user()
        url_password_reset = user.url_password_reset()
        # Start from logged out state.
        self.logout_user()

        # Token should be good up till RESET_EXPIRE
        self.advance_now(seconds=user_module.RESET_EXPIRE)
        response = self.app.get(url_password_reset)

        # Token should have expired after a second past RESET_EXPIRE.
        self.advance_now(seconds=1)
        self.expect_log('front.resource.auth.password', 'Invalid token when attempting password reset.*')
        response = self.app.get(url_password_reset)
        self.assertTrue("Password reset link has expired or is invalid." in response)

    def test_password_reset_bad_link(self):
        # Get the reset password url from the user object.
        user = self.get_logged_in_user()
        bogus_url_password_reset = user.url_password_reset() + "bogus"

        # Start from logged out state.
        self.logout_user()
        self.expect_log('front.resource.auth.password', 'Invalid token when attempting password reset.*')
        response = self.app.get(bogus_url_password_reset)
        self.assertTrue("Password reset link has expired or is invalid." in response)

        # Verify a bad POST also fails.
        response = self.app.post(bogus_url_password_reset, status=400)
