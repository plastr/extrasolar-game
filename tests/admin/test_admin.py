# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re

from front.tests import base
from front.tests.base import points, SIX_HOURS, PRODUCT_KEY_S1
from front.tests.base import INVITE_EMAIL, INVITE_FIRST_NAME, INVITE_LAST_NAME
from front.tests.mock_stripe import ChargeAlwaysSuccess, FAKE_CHARGE_ID_1

from front import gift_types
from front.backend import admin as admin_module
from front.backend import email_queue, stats
from front.lib import urls, db, xjson, email_module
from front.models import chips

class TestAdmin(base.TestCase):
    def test_admin_root(self):
        # Signup a user who will have been inactive long enough to have data for the attrition charts.
        self.signup_user('olduser@example.com', 'password')
        self.advance_game(days=stats.MESSAGE_ATTRITION_INACTIVE_DAYS)
        self.logout_user()

        # Signup a non validated user so there is a pending deferred to see when checking the admin deferred page.
        self.signup_user('nonadminuser@example.com', 'password', campaign_name="Test Campaign")
        self.logout_user()
        # Now create and login as the soon to be admin user.
        # Have this user's name contain non-ascii to test message rendering on the admin user page.
        self.create_user('theadminuser@example.com', 'password', first_name="S\xc3\xa9bastien")
        u = self.get_logged_in_user()
        # Deliver a message with a known template which prints the user's name.
        self.send_message_now(u, 'MSG_TEST_SIMPLE')
        # Send an invite so that related queries (for the charts) have data.
        self.set_user_invites_left(1)
        create_invite_url = str(self.get_gamestate()['urls']['create_invite'])
        payload = {
            'recipient_email': INVITE_EMAIL,
            'recipient_first_name': INVITE_FIRST_NAME,
            'recipient_last_name': INVITE_LAST_NAME,
            'recipient_message': 'Hello my friend, you should play this game!'
        }
        response = self.json_post(create_invite_url, payload)
        # Create a target which has metadata to test that data in the queries.
        # Add TGT_RDR keys for the renderer instance name and total time which are used by the renderer
        # utilization chart. Be sure to add a different name for each test target to test the code that
        # sets the instance to 0 utilization when a renderer instance is offline.
        METADATA = {
            'TGT_FEATURE_PANORAMA': '', 'TGT_ADMIN_TEST': '',
            'TGT_RDR_SERVER': "RENDERER_01", 'TGT_RDR_TOTAL_TIME': 12345
        }
        chips_result = self.create_target(arrival_delta=SIX_HOURS, metadata=METADATA, **points.FIRST_MOVE)
        target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        target_id = target['target_id']
        # Advance to that targets render_at time so it appears in the recent targets list.
        self.advance_game(seconds=SIX_HOURS)
        METADATA = {
            'TGT_RDR_SERVER': "RENDERER_02", 'TGT_RDR_TOTAL_TIME': 54321
        }
        self.create_target(arrival_delta=SIX_HOURS, metadata=METADATA, **points.SECOND_MOVE)
        self.advance_game(seconds=SIX_HOURS)

        # A non-admin user cannot load the admin pages.
        response = self.app.get(urls.admin_root(), status=401)
        self.assertTrue('Nothing to see here' in response)
        self.assertTrue(u.email not in response)

        # Now make this user an admin.
        self.make_user_admin(u)

        # Should now be able ot load the admin root.
        response = self.app.get(urls.admin_root())
        self.assertTrue('Version' in response)

        # Purchase a product so the shop admin pages have content.
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=False, charge=charge)

        # The recent user and target data is loaded with an AJAX call
        # to a different URL, check that data.
        recent_users_html, recent_targets_html, recent_transactions_html = self._get_recent_users_and_targets_html()
        self.assertTrue(u.email in recent_users_html)
        # One of the users should have some vouchers and have that CSS style.
        self.assertTrue('user_has_vouchers' in recent_users_html)
        # One of the users should be invalid and have that CSS style.
        self.assertTrue('user_invalid' in recent_users_html)
        self.assertTrue(u.email in recent_targets_html)
        self.assertTrue(u.email in recent_transactions_html)
        self.assertTrue(FAKE_CHARGE_ID_1 in recent_transactions_html)

        # Now verify the recent_users_html has the user's specific admin page URL
        # and follow that link.
        self.assertTrue(u.url_admin() in recent_users_html)
        response = self.app.get(u.url_admin())
        self.assertTrue(u.email in response)
        # The invoice/charge should be on the user's page as well.
        self.assertTrue(FAKE_CHARGE_ID_1 in response)
        self.assertTrue(PRODUCT_KEY_S1 in response)

        # And follow the first link to the user's specific map page.
        response = response.click(href=u.url_admin_map())
        self.assertTrue(u.email in response)

        # Try the recent users filtered by campaign name page as well.
        self.assertTrue(urls.admin_users_by_campaign_name("Test Campaign") in recent_users_html)
        response = self.app.get(urls.admin_users_by_campaign_name("Test Campaign"))
        # Only the user with the campaign name should be in the respnse.
        self.assertTrue("theadminuser@example.com" not in response)
        self.assertTrue("nonadminuser@example.com" in response)
        self.assertTrue("Test Campaign" in response)

        # Now verify the recent_targets_html has a target specific admin page URL and follow that link.
        self.assertTrue(urls.admin_target(target_id) in recent_targets_html)
        response = self.app.get(urls.admin_target(target_id))
        self.assertTrue(target_id in response)
        self.assertTrue(u.email in response)

        # Return to the user's admin page and follow the first invoice link.
        response = self.app.get(u.url_admin())
        response = response.click(href=urls.admin_invoice('.*'))
        self.assertTrue(u.email in response)
        self.assertTrue(FAKE_CHARGE_ID_1 in response)
        self.assertTrue(PRODUCT_KEY_S1 in response)

        # Return to the root admin page and test search users tool.
        response = self.app.get(urls.admin_root())
        form = response.forms['form_search_users']
        # Try a bogus email first.
        form['user_search_term'] = "nosuchuser@example.com"
        response = form.submit()
        response = response.follow()
        self.assertTrue("Found 0 Users" in response)
        # And now the actual email.
        form['user_search_term'] = u.email
        response = form.submit()
        response = response.follow()
        self.assertTrue("Found 1 Users" in response)
        self.assertTrue(u.first_name in response)
        self.assertTrue(u.email in response)
        # And a subset of an actual name which also contains unicode to test query parameter encoding.
        form['user_search_term'] = 'S\xc3\xa9bas'
        response = form.submit()
        response = response.follow()
        self.assertTrue("Found 1 Users" in response)
        self.assertTrue(u.first_name in response)

        # Check that the recent users page works.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_users())
        self.assertTrue(">theadminuser@example.com" in response)

        # Check that the recent targets page works.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_targets())
        self.assertTrue(target_id in response)

        # Check that the deferred page works.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_deferreds())
        # The verify email deferred for the non-admin user should be pending.
        self.assertTrue("nonadminuser@example.com" in response)

        # Check that the email_queue page works.
        # First insert a testing message into the email queue.
        test_email = email_module.EmailMessage('fromuser@example.com', 'touser@example.com', 'Test Subject', 'Test Body')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                # Add an email to the queue.
                email_queue.enqueue_email_message(ctx, test_email)
        # And then load the email_queue page.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_email_queue())
        # The verify the is a pending email.
        self.assertTrue("touser@example.com" in response)

        # Check that the recent transactions page works.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_transactions())
        self.assertTrue(">theadminuser@example.com" in response)
        self.assertTrue(FAKE_CHARGE_ID_1 in response)

        # Check that the basic HTML stats page works. The chart loading API is checked next.
        # Check the debug flag works.
        response = self.app.get(urls.add_query_param_to_url(urls.admin_stats(), debug=''))
        self.assertTrue('"use_debug_data": true' in response)
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_stats())
        self.assertTrue('"use_debug_data": false' in response)

        # Test the chart data API using both the debug data and the real queries.
        def _load_chart_data(chart_name, use_debug_data):
            payload = {'chart_name': chart_name, 'use_debug_data': use_debug_data}
            response = xjson.loads(self.app.post(urls.admin_api_chart_data(),
                                                 content_type=xjson.mime_type,
                                                 params=xjson.dumps(payload)).body)
            return response

        # First with the debug data.
        for chart_name in stats.ALL_CHARTS:
            result = _load_chart_data(chart_name, use_debug_data=True)
            self.assertEqual(result['chart_name'], chart_name)
            self.assertTrue('chart_options' in result)
            self.assertTrue(len(result['chart_data']['rows']) > 0)

        # And then with the real queries.
        # Move gametime forward so that the transaction data/rendered targets etc. are visible for the stat data.
        self.advance_now(days=1)
        for chart_name in stats.ALL_CHARTS:
            result = _load_chart_data(chart_name, use_debug_data=False)
            self.assertEqual(result['chart_name'], chart_name)
            self.assertTrue('chart_options' in result)
            self.assertTrue(len(result['chart_data']['rows']) > 0)

    def test_admin_invites_and_gifts(self):
        self.create_user('theadminuser@example.com', 'password')
        admin_user = self.get_logged_in_user()
        self.make_user_admin(admin_user)
        self.assertEqual(len(admin_user.gifts_created), 0)
        self.assertEqual(len(admin_user.invitations), 0)

        # Click on the new gift link.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_gifts_new())

        # Fill out some bogus form data at first.
        # Completely empty form.
        form = response.forms['form_new_gift']
        response = form.submit(status=400)
        self.assertTrue("Bad parameters" in response)
        # Badly formatted generate number.
        form['generate_number'] = "Not a number"
        form['gift_annotation'] = "Testing gifts"
        form['gift_type'] = gift_types.GFT_ALL_PASS
        self.assertRaises(ValueError, form.submit)
        # 0 number to generate.
        form['generate_number'] = "0"
        response = form.submit(status=400)
        self.assertTrue("Refusing to generate no gifts" in response)
        # Empty gift annotation.
        form['generate_number'] = "1"
        form['gift_annotation'] = ""
        form['gift_type'] = gift_types.GFT_ALL_PASS
        response = form.submit(status=400)
        self.assertTrue("Bad parameters" in response)
        # Short gift annotation.
        form['gift_annotation'] = "Sho"
        response = form.submit(status=400)
        self.assertTrue("Please use an annotation longer than 5 characters" in response)

        # And now fill out the form to create a few ALL gifts.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_gifts_new())
        form = response.forms['form_new_gift']
        form['generate_number'] = "2"
        form['gift_annotation'] = "Testing gifts"
        for k,v in form['gift_type'].options:
            self.assertTrue(k in gift_types.ALL)
        form['gift_type'] = gift_types.GFT_ALL_PASS
        response = form.submit()
        response = response.follow()
        # Check the gifts got created
        admin_user = self.get_logged_in_user()
        self.assertEqual(len(admin_user.gifts_created), 2)
        self.assertEqual(len(admin_user.invitations), 0)
        self.assertEqual(self._admin_inviter_invitations_count(), 0)
        # Should have redirect to the gifts mine page and the gift data should be present.
        self.assertEqual(urls.admin_gifts_mine(), response.request.path_qs)
        self.assertTrue("theadminuser@example.com" in response)
        self.assertTrue("Testing gifts" in response)
        self.assertTrue(gift_types.GFT_ALL_PASS in response)
        # Check the recent gifts page as well.
        response = self.app.get(urls.admin_gifts_recent())
        self.assertTrue("theadminuser@example.com" in response)
        self.assertTrue("Testing gifts" in response)
        self.assertTrue(gift_types.GFT_ALL_PASS in response)

        # Click on the new invite link.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_invites_new())

        # Fill out some bogus form data at first.
        # Completely empty form.
        form = response.forms['form_new_invite']
        response = form.submit(status=400)
        self.assertTrue("Bad parameters" in response)
        form['recipient_emails_and_names'] = "homer@example.com"
        form['gift_type'] = gift_types.GFT_S1_PASS
        # Short gift annotation.
        form['invitation_message'] = "This is a longer one"
        form['gift_annotation'] = "Sho"
        response = form.submit(status=400)
        self.assertTrue("Please use an annotation longer than 5 characters" in response)
        # Short invite message.
        form['gift_annotation'] = "This is a longer one"
        form['invitation_message'] = "Sho"
        response = form.submit(status=400)
        self.assertTrue("Please use an invitation message longer than 5 characters" in response)
        form['invitation_message'] = "This is a longer one"
        # Some bogus looking CSV data.
        form['recipient_emails_and_names'] = "invalid&domain"
        response = form.submit(status=400)
        self.assertTrue("Bad invite entry" in response)
        self.assertTrue("invalid&domain" in response)
        self.assertTrue("Invalid email address" in response)
        # And some unparsable CSV
        form['recipient_emails_and_names'] = "   "
        response = form.submit(status=400)
        self.assertTrue("Unable to parse any invite entries" in response)
        form['recipient_emails_and_names'] = ",\n\,,"
        response = form.submit(status=400)
        self.assertTrue("Bad invite entry" in response)
        form['recipient_emails_and_names'] = "homer@example.com,Homer,Simpson,Extra Field\n"
        response = form.submit(status=400)
        self.assertTrue("Bad invite entry" in response)
        self.assertTrue("Extra Field" in response)

        # And now fill out the form to create a few S1 invite gifts.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_invites_new())
        form = response.forms['form_new_invite']
        form['invitation_message'] = "Welcome to Extrasolar!"
        self.assertEqual(form['gift_type'].value, "No Gift")
        form['gift_type'] = gift_types.GFT_S1_PASS
        form['gift_annotation'] = "Testing invite gifts"
        form['recipient_emails_and_names'] = """
        homer@example.com, Homer J , Simpson
        marge@example.com, Marge 
        bart@example.com
        """
        response = form.submit()
        response = response.follow()
        # Check the gift invites got created
        admin_user = self.get_logged_in_user()
        self.assertEqual(len(admin_user.gifts_created), 5)
        self.assertEqual(len(admin_user.invitations), 0)
        self.assertEqual(self._admin_inviter_invitations_count(), 3)
        # Should have redirect to the system invites page and the gift data should be present.
        self.assertEqual(urls.admin_invites_system(), response.request.path_qs)
        self.assertTrue(admin_module.ADMIN_INVITER_EMAIL in response)
        self.assertTrue(gift_types.GFT_S1_PASS in response)
        self.assertTrue("homer@example.com" in response)
        self.assertTrue("Homer J Simpson" in response)
        self.assertTrue("marge@example.com" in response)
        self.assertTrue("Marge" in response)
        self.assertTrue("bart@example.com" in response)
        # Check the recent invites page as well.
        response = self.app.get(urls.admin_invites_recent())
        self.assertTrue(admin_module.ADMIN_INVITER_EMAIL in response)
        self.assertTrue(gift_types.GFT_S1_PASS in response)
        # Double check the recent gifts page too.
        response = self.app.get(urls.admin_gifts_recent())
        self.assertTrue("theadminuser@example.com" in response)
        self.assertTrue("Testing invite gifts" in response)
        self.assertTrue(gift_types.GFT_S1_PASS in response)

        # Go back and send one invitation with no gift attached.
        # Click on the new invite link.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_invites_new())
        # And fill out the form with no gifts attached.
        form = response.forms['form_new_invite']
        form['invitation_message'] = "Welcome to Extrasolar!"
        self.assertEqual(form['gift_type'].value, "No Gift")
        form['gift_annotation'] = "Testing invite gifts"
        form['recipient_emails_and_names'] = """
        lisa@example.com, Lisa, Simpson
        """
        response = form.submit()
        response = response.follow()
        # Check the gift invites got created
        admin_user = self.get_logged_in_user()
        self.assertEqual(len(admin_user.gifts_created), 5)
        self.assertEqual(len(admin_user.invitations), 0)
        self.assertEqual(self._admin_inviter_invitations_count(), 4)
        # Should have redirect to the system invites page and the gift data should be present.
        self.assertEqual(urls.admin_invites_system(), response.request.path_qs)
        self.assertTrue("Lisa Simpson" in response)
        self.assertTrue("lisa@example.com" in response)
        # Check the recent invites page as well.
        response = self.app.get(urls.admin_invites_recent())
        self.assertTrue("Lisa Simpson" in response)
        self.assertTrue("lisa@example.com" in response)

    def test_admin_invites_and_gifts_with_campaign_name(self):
        self.create_user('theadminuser@example.com', 'password')
        admin_user = self.get_logged_in_user()
        self.make_user_admin(admin_user)
        self.assertEqual(len(admin_user.gifts_created), 0)
        self.assertEqual(len(admin_user.invitations), 0)

        # Fill out the form to create a gift with a campaign name.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_gifts_new())
        form = response.forms['form_new_gift']
        form['generate_number'] = "2"
        form['gift_annotation'] = "Testing gifts"
        form['gift_type'] = gift_types.GFT_NO_PASS
        form['gift_campaign_name'] = "Test Campaign Gift"
        response = form.submit()
        response = response.follow()
        # Check the gifts got created
        admin_user = self.get_logged_in_user()
        self.assertEqual(len(admin_user.gifts_created), 2)
        first_gift = admin_user.gifts_created.values()[0]
        second_gift = admin_user.gifts_created.values()[1]
        self.assertEqual(len(admin_user.invitations), 0)
        # Should have redirect to the gifts mine page and the gift data should be present.
        self.assertEqual(urls.admin_gifts_mine(), response.request.path_qs)
        self.assertTrue("Testing gifts" in response)
        self.assertTrue("Test Campaign Gift" in response)
        # Check the recent gifts page as well.
        response = self.app.get(urls.admin_gifts_recent())
        self.assertTrue("Testing gifts" in response)
        self.assertTrue("Test Campaign Gift" in response)

        # Fill out the form to create a S1 invite with a campaign name and an invite without a gift.
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_invites_new())
        form = response.forms['form_new_invite']
        form['invitation_message'] = "Welcome to Extrasolar!"
        form['invitation_campaign_name'] = "Test Campaign Invite No Gift"
        form['recipient_emails_and_names'] = """
        homer@example.com, Homer J , Simpson
        """
        response = form.submit()
        response = self.app.get(urls.admin_root())
        response = response.click(href=urls.admin_invites_new())
        form = response.forms['form_new_invite']
        form['invitation_message'] = "Welcome to Extrasolar!"
        form['invitation_campaign_name'] = "Test Campaign Invite Gift"
        form['gift_type'] = gift_types.GFT_S1_PASS
        form['gift_annotation'] = "Testing invite gifts"
        form['recipient_emails_and_names'] = """
        lisa@example.com,Lisa, Simpson
        """
        response = form.submit()

        response = response.follow()
        # Check the gift invites got created
        admin_user = self.get_logged_in_user()
        self.assertEqual(len(admin_user.gifts_created), 3)
        self.assertEqual(len(admin_user.invitations), 0)
        self.assertEqual(self._admin_inviter_invitations_count(), 2)
        no_gift_invite = [i for i in self._admin_inviter_invitations() if not i.has_gift()][0]
        gift_invite = [i for i in self._admin_inviter_invitations() if i.has_gift()][0]
        # Should have redirect to the system invites page and the gift data should be present.
        self.assertEqual(urls.admin_invites_system(), response.request.path_qs)
        self.assertTrue(admin_module.ADMIN_INVITER_EMAIL in response)
        self.assertTrue(gift_types.GFT_S1_PASS in response)
        self.assertTrue("homer@example.com" in response)
        self.assertTrue("lisa@example.com" in response)
        self.assertTrue("Test Campaign Invite Gift" in response)
        self.assertTrue("Test Campaign Invite No Gift" in response)
        # Check the recent invites page as well.
        response = self.app.get(urls.admin_invites_recent())
        self.assertTrue("homer@example.com" in response)
        self.assertTrue("lisa@example.com" in response)
        self.assertTrue("Test Campaign Invite" in response)
        self.assertTrue("Test Campaign Invite No Gift" in response)

        # Follow the invite and redeem the gift and verify the user's get their campaign name set.
        self.logout_user()

        # Create a new user and redeem the gift to make sure that user now has a campaign name.
        self.create_user('redeemer@example.com', 'pw')
        user = self.get_logged_in_user()
        self.assertEqual(user.campaign_name, "")        
        response = self.app.get(first_gift.url_gift_redeem())
        response = response.click(href=first_gift.url_gift_redeem_existing_user())
        form = response.forms['form_login']
        form['login_email'].value = "redeemer@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        response = response.follow()
        user = self.get_logged_in_user()
        self.assertEqual(user.campaign_name, "Test Campaign Gift")
        self.logout_user()

        # Create a new user WITH a campaign and redeem the gift to make sure that user's campaign is not changed.
        self.signup_user('hascampaign@example.com', 'pw', campaign_name="Has Campaign")
        user = self.get_logged_in_user()
        self.assertEqual(len(user.gifts_redeemed), 0)
        self.assertEqual(user.campaign_name, "Has Campaign")        
        self.app.get(user.url_validate())
        response = self.app.get(second_gift.url_gift_redeem())
        response = response.click(href=second_gift.url_gift_redeem_existing_user())
        form = response.forms['form_login']
        form['login_email'].value = "hascampaign@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        response = response.follow()
        user = self.get_logged_in_user()
        self.assertEqual(len(user.gifts_redeemed), 1)
        self.assertEqual(user.campaign_name, "Has Campaign")
        self.logout_user()

        # Accept the invite with no gift and check the campaign name of the new user.
        response = self.app.get(no_gift_invite.url_invite_accept())
        form = response.forms['form_signup']
        # These fields should have been filled out.
        self.assertEqual(form['signup_email'].value, "homer@example.com")
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()
        # Since the new user is not authorized (haven't followed the backdoor link), the should
        # be directed to the "over capacity" page and see the rover program is full message.
        response = response.follow()
        self.assertEqual(urls.auth_signup_complete(), response.request.path)
        self.assertTrue('No Available Rovers' in response)
        # The new user should have gotten their campaign name set.
        self.logout_user()
        self.login_user('homer@example.com', 'pw')
        user = self.get_logged_in_user()
        self.assertEqual(user.campaign_name, "Test Campaign Invite No Gift")
        self.assertEqual(len(user.gifts_redeemed), 0)
        self.logout_user()

        # Accept the invite with a gift and check the campaign name of the new user.
        response = self.app.get(gift_invite.url_invite_accept())
        response = response.click(href=gift_invite.gift.url_gift_redeem_new_user())
        form = response.forms['form_signup']
        # These fields should have been filled out.
        self.assertEqual(form['signup_email'].value, "lisa@example.com")
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()
        # The new user should redirect back to / and since they are not authorized (haven't followed the backdoor link),
        # they should see the rover program is full message.
        response = response.follow()
        self.assertEqual(urls.auth_signup_complete(), response.request.path)
        self.assertTrue('No Available Rovers' in response)
        # The new user should have gotten their campaign name set.
        self.logout_user()
        self.login_user('lisa@example.com', 'pw')
        user = self.get_logged_in_user()
        self.assertEqual(len(user.gifts_redeemed), 1)
        self.assertEqual(user.campaign_name, "Test Campaign Invite Gift")

    def test_admin_increment_invites_left(self):
        self.create_user('theadminuser@example.com', 'password')
        self.make_user_admin(self.get_logged_in_user())

        # Attempt to increment a non-existent user.
        payload = {'user_id': '00000000-0000-0000-0000-000000000000'}
        response = xjson.loads(self.app.post(urls.admin_api_user_increment_invites_left(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload), status=400).body)
        self.assertEqual(response['errors'], ['This user does not exist.'])

        # Check invites_left.
        u = self.get_logged_in_user()
        invites_left_before = u.invites_left

        # Use the admin api to increment this users invites_left.
        payload = {'user_id': u.user_id}
        response = xjson.loads(self.app.post(urls.admin_api_user_increment_invites_left(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload)).body)
        self.assertEqual(response, {'invites_left': invites_left_before + 1})

        # Check invites_left after.
        u = self.get_logged_in_user()
        self.assertEqual(u.invites_left, invites_left_before + 1)

    def test_admin_edit_campaign_name(self):
        self.create_user('theadminuser@example.com', 'password')
        self.make_user_admin(self.get_logged_in_user())

        # Attempt to increment a non-existent user.
        payload = {'user_id': '00000000-0000-0000-0000-000000000000', 'campaign_name': 'Test Campaign'}
        response = xjson.loads(self.app.post(urls.admin_api_user_edit_campaign_name(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload), status=400).body)
        self.assertEqual(response['errors'], ['This user does not exist.'])

        # Check campaign name.
        u = self.get_logged_in_user()
        self.assertEqual(u.campaign_name, "")
        self.assertTrue('MET_CAMPAIGN_NAME' not in u.metadata)

        # Use the admin api to change this users campaign name.
        payload = {'user_id': u.user_id, 'campaign_name': "Test Campaign"}
        response = xjson.loads(self.app.post(urls.admin_api_user_edit_campaign_name(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload)).body)
        self.assertEqual(response, {'campaign_name': "Test Campaign"})

        # Check campaign name after.
        u = self.get_logged_in_user()
        self.assertEqual(u.campaign_name, "Test Campaign")
        self.assertTrue('MET_CAMPAIGN_NAME' in u.metadata)

        # Setting the campaign name to a blank string should delete it from the metadata collection.
        payload = {'user_id': u.user_id, 'campaign_name': ""}
        response = xjson.loads(self.app.post(urls.admin_api_user_edit_campaign_name(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload)).body)
        self.assertEqual(response, {'campaign_name': ""})

        # Check campaign name after.
        u = self.get_logged_in_user()
        self.assertEqual(u.campaign_name, "")
        self.assertTrue('MET_CAMPAIGN_NAME' not in u.metadata)

    def test_admin_reprocess(self):
        self.create_user('theadminuser@example.com', 'password')
        self.make_user_admin(self.get_logged_in_user())
        # Need an new target as the initial system created photos are now filtered.
        self.create_target_and_move(**points.FIRST_MOVE)

        # The new target should have been marked processed.
        target = self.get_most_recent_target_from_gamestate()
        target_id = target['target_id']
        self.assertEqual(target['processed'], 1)
        # And the element id with that target should be in the HTML (the Javascript uses this)
        # to issue the request.
        recent_users_html, recent_targets_html, _ = self._get_recent_users_and_targets_html()
        reprocess_id = 'reprocess_' + target_id
        self.assertTrue(reprocess_id in recent_targets_html)

        response = self._post_reprocess(target_id)
        self.assertEqual(response, {})
        target = self.get_target_from_gamestate(target_id)
        self.assertEqual(target['processed'], 0)
        # The element id for the just reprocessed target should NOT be in the HTML anymore.
        recent_users_html, recent_targets_html, _ = self._get_recent_users_and_targets_html()
        self.assertTrue(reprocess_id not in recent_targets_html)

        # Attempt to reprocess a non-existent target.
        response = self._post_reprocess('00000000-0000-0000-0000-000000000000', status=400)
        self.assertEqual(response['errors'], ['This target does not exist.'])

        # Attempt to reprocess a non-picture target.
        target = self.get_targets_from_gamestate()[0]
        self.assertEqual(target['picture'], 0)
        response = self._post_reprocess(target['target_id'], status=400)
        self.assertEqual(response['errors'], ['Only picture targets can be reprocessed.'])

        # Create a new target and neuter it then attempt to reprocess a neutered target.
        result = self.create_target(**points.SECOND_MOVE)
        chip_value = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        target_id = chip_value['target_id']
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                u = self.get_logged_in_user(ctx=ctx)
                target = u.rovers.find_target_by_id(target_id)
                self.assertFalse(target.is_neutered())
                target.mark_as_neutered()
                self.assertTrue(target.is_neutered())
        response = self._post_reprocess(target_id, status=400)
        self.assertEqual(response['errors'], ['Neutered targets can not be reprocessed.'])

    def test_admin_highlighting(self):
        self.create_user('theadminuser@example.com', 'password')
        self.make_user_admin(self.get_logged_in_user())
        # Need an new target as the initial system created photos are now filtered.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Grab the new target.
        target_id = self.get_most_recent_target_from_gamestate()['target_id']
        target = self.get_logged_in_user().rovers.find_target_by_id(target_id)
        self.assertEqual(target.highlighted, 0)
        # And the element id with that target should be in the HTML (the Javascript uses this)
        # to issue the request.
        recent_users_html, recent_targets_html, _ = self._get_recent_users_and_targets_html()
        highlight_id = 'highlight_' + target_id
        self.assertFalse(_checkbox_checked(recent_targets_html, highlight_id))
        # Check the highlighted flag is not set in the gamestate.
        self.assertEqual(self.get_target_from_gamestate(target_id)['highlighted'], 0)

        # Mark this target as highlighted.
        response = self.admin_api_highlight_add(target_id)
        self.assertEqual(response, {})
        target = self.get_logged_in_user().rovers.find_target_by_id(target_id)
        self.assertEqual(target.highlighted, 1)
        # The checkbox for this target should now be checked.
        recent_users_html, recent_targets_html, _ = self._get_recent_users_and_targets_html()
        self.assertTrue(_checkbox_checked(recent_targets_html, highlight_id))
        # Check the highlighted flag is now set in the gamestate.
        self.assertEqual(self.get_target_from_gamestate(target_id)['highlighted'], 1)
        # Verify that a MOD chip was sent as well.
        found_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', target_id])
        self.assertEqual(len(found_chips), 1)
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['highlighted'], 1)

        # Attempt to highlight the target again to be sure nothing explodes.
        response = self.admin_api_highlight_add(target_id)
        self.assertEqual(response, {})
        target = self.get_logged_in_user().rovers.find_target_by_id(target_id)
        self.assertEqual(target.highlighted, 1)

        # Advance time to clear chips.
        self.advance_now(minutes=10)

        # Now mark the target as not highlighted.
        response = self.admin_api_highlight_remove(target_id)
        self.assertEqual(response, {})
        target = self.get_logged_in_user().rovers.find_target_by_id(target_id)
        self.assertEqual(target.highlighted, 0)
        # The checkbox for this target should now be checked.
        recent_users_html, recent_targets_html, _ = self._get_recent_users_and_targets_html()
        self.assertFalse(_checkbox_checked(recent_targets_html, highlight_id))
        # Check the highlighted flag is now unset in the gamestate.
        self.assertEqual(self.get_target_from_gamestate(target_id)['highlighted'], 0)
        # Verify that a MOD chip was sent as well.
        found_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', target_id])
        self.assertEqual(len(found_chips), 1)
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['highlighted'], 0)

        # Attempt to unhighlight the target again to be sure nothing explodes.
        response = self.admin_api_highlight_remove(target_id)
        self.assertEqual(response, {})
        target = self.get_logged_in_user().rovers.find_target_by_id(target_id)
        self.assertEqual(target.highlighted, 0)

        # Attempt to highlight a non-existent target.
        response = self.admin_api_highlight_add('00000000-0000-0000-0000-000000000000', status=400)
        self.assertEqual(response['errors'], ['This target does not exist.'])

        # Attempt to highlight a non-picture target.
        target = self.get_targets_from_gamestate()[0]
        self.assertEqual(target['picture'], 0)
        response = self.admin_api_highlight_add(target['target_id'], status=400)
        self.assertEqual(response['errors'], ['Only picture targets can be highlighted.'])

        # Create a new target and neuter it then attempt to highlight a neutered target.
        result = self.create_target(arrival_delta=SIX_HOURS, **points.SECOND_MOVE)
        chip_value = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        target_id = chip_value['target_id']
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                u = self.get_logged_in_user(ctx=ctx)
                target = u.rovers.find_target_by_id(target_id)
                target.mark_as_neutered()
        response = self.admin_api_highlight_add(target_id, status=400)
        self.assertEqual(response['errors'], ['Neutered targets can not be highlighted.'])
        # Advance to that targets render_at time of that target so the next target shows up for rendering.
        self.advance_now(seconds=SIX_HOURS)

        # Create a new classified target and then attempt to highlight a classified target.
        result = self.create_target(arrival_delta=SIX_HOURS, **points.THIRD_MOVE)
        chip_value = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        target_id = chip_value['target_id']
        self.render_next_target(assert_only_one=True, classified=1)
        self.advance_game(seconds=SIX_HOURS*2)
        target = self.get_target_from_gamestate(target_id)
        self.assertEqual(target['classified'], 1)
        response = self.admin_api_highlight_add(target_id, status=400)
        self.assertEqual(response['errors'], ['Classified targets can not be highlighted.'])

    ## Test helpers
    def _post_reprocess(self, target_id, status=200):
        payload = {'target_id': target_id}
        response = xjson.loads(self.app.post(urls.admin_api_reprocess_target(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload), status=status).body)
        return response

    def _get_recent_users_and_targets_html(self):
        response = xjson.loads(self.app.get(urls.admin_recent_users_and_targets_html(),
                                            headers=[xjson.accept]).body)
        return response['recent_users_html'], response['recent_targets_html'], response['recent_transactions_html']

    def _admin_inviter_invitations(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                invites = admin_module.get_admin_inviter_user(ctx).invitations.values()
                # Lazy load all the gift objects before the ctx is committed and the connection is closed.
                [i.gift for i in invites]
                return invites

    def _admin_inviter_invitations_count(self):
        return len(self._admin_inviter_invitations())

def _checkbox_checked(html, dom_id):
    assert(dom_id in html)
    is_checked = re.search(dom_id+r'.*checkbox.*checked..true.*>', html) != None
    return is_checked
