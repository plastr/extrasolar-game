# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re
import facebook

from front import gift_types, InitialMessages
from front.tests import base
from front.tests.base import VOUCHER_KEY_S1_GIFT
from front.lib import db, urls
from front.models import chips
from front.backend import admin

class TestFacebookSignup(base.TestCase):
    def setUp(self):
        super(TestFacebookSignup, self).setUp()
        #self.create_user('testuser@example.com', 'pw')

    def test_signup_facebook(self):
        # Login our test user.
        facebook_token = self.get_facebook_token()
        self.login_user_facebook(access_token=facebook_token)
        user = self.get_logged_in_user()
        self.assertEqual(user.first_name, 'Testy')
        self.assertEqual(user.last_name, 'McTesterson')
        self.assertEqual(user.email, 'testy_obocldh_mctesterson@tfbnw.net')
        self.assertEqual(user.campaign_name, '')
        self.assertFalse(user.valid)

        # We expect that 1 email has been sent.
        self.assertEqual(len(self.get_sent_emails()), 1)

    def test_facebook_password_reset(self):
        # Login our test user and make sure he has the email we expect.
        facebook_token = self.get_facebook_token()
        self.login_user_facebook(access_token=facebook_token)
        user = self.get_logged_in_user()
        self.assertEqual(user.email, 'testy_obocldh_mctesterson@tfbnw.net')

        # Now logout and try a password reset.
        self.logout_user()
        form = self.app.get(urls.request_password_reset()).forms['form_request_password_reset']
        form['email'] = 'testy_obocldh_mctesterson@tfbnw.net'
        response = form.submit()
        response = response.follow()
        self.assertTrue("The user for the email you entered logs in with Facebook." in response)

    def test_facebook_gift_redeem_existing(self):
        # Create an admin gift as the 'testuser@example.com' admin user.
        self.create_user('testuser@example.com', 'pw')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                admin_user = self.get_logged_in_user(ctx=ctx)
                self.make_user_admin(admin_user)
                gift = admin.create_admin_gift_of_type(ctx, admin_user, gift_types.GFT_S1_PASS, "Testing Gift")

        # Logout the admin user
        self.logout_user()

        # Login our Facebook test user.
        facebook_token = self.get_facebook_token()
        self.login_user_facebook(access_token=facebook_token)
        user = self.get_logged_in_user()
        self.assertEqual(user.email, 'testy_obocldh_mctesterson@tfbnw.net')

        # Send the verify email.
        self.advance_game(minutes=InitialMessages.EMAIL_VERIFY_DELAY_MINUTES)
        # Pull the verify/backdoor URL out of the verify email body.
        backdoor_url = re.search(user.url_validate(), self.get_sent_emails()[-1].body_html).group(0)
        assert backdoor_url
        
        # Follow the backdoor link. The user should now be validated.
        response = self.app.get(backdoor_url)
        user = self.get_logged_in_user()
        self.assertTrue(user.valid)
        
        # Visit the gift redemption URL and attach the gift to this account.
        response = self.app.get(gift.url_gift_redeem())
        response = response.click(href=gift.url_gift_redeem_existing_user())
        form = response.forms['form_facebook']
        form['facebook_token'] = facebook_token

        # After a couple of redirects, we should land at /ops
        response = form.submit(status=303)
        response = response.follow()
        response = response.follow()
        self.assertTrue('<title>Extrasolar</title>' in response)

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        vouchers = gamestate['user']['vouchers']

        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)
        found_chips = self.chips_for_path(['user', 'vouchers', '*'])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['voucher_key'], VOUCHER_KEY_S1_GIFT)
