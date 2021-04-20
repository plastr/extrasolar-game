# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re
from front.tests import base
from front.tests.base import PRODUCT_KEY_S1_GIFT, VOUCHER_KEY_S1_GIFT, PRODUCT_KEY_ALL_GIFT, VOUCHER_KEY_ALL_GIFT
from front.tests.base import PRODUCT_KEY_S1, PRODUCT_KEY_ALL, VOUCHER_KEY_ALL, VOUCHER_KEY_S1
from front.tests.base import INVITE_EMAIL, INVITE_FIRST_NAME, INVITE_LAST_NAME, INVITE_LAST_NAME_TRUNCATED
from front.tests.mock_stripe import ChargeAlwaysSuccess, FAKE_CHARGE_ID_1

from front import gift_types
from front.lib import db, urls
from front.models import chips
from front.backend import admin

class TestGifts(base.TestCase):
    def setUp(self):
        super(TestGifts, self).setUp()
        self.create_user('testuser@example.com', 'pw')
        # Should always be able to send gifts even if there are no invites left.
        self.set_user_invites_left(0)
        # Advance time a few seconds to flush any chips.
        self.advance_now(seconds=5)

    def test_admin_gift_redeem_new(self):
        # Create an admin gift as the 'testuser@example.com' admin user.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                admin_user = self.get_logged_in_user(ctx=ctx)
                self.make_user_admin(admin_user)
                gift = admin.create_admin_gift_of_type(ctx, admin_user, gift_types.GFT_S1_PASS, "Testing Gift")
        self.logout_user()

        # Redeem that admin gift for a new user.
        response = self.app.get(gift.url_gift_redeem())
        response = response.click(href=gift.url_gift_redeem_new_user())
        form = response.forms['form_signup']
        form['signup_email'].value = INVITE_EMAIL
        form['first_name'].value = INVITE_FIRST_NAME
        form['last_name'].value = INVITE_LAST_NAME
        form['signup_password'] = "pw"
        response = form.submit()
        # Should attempt to send to /
        response = response.follow()
        self.assertEqual(urls.root(), response.request.path)
        # And then redirect to root.
        response = response.follow()
        self.assertEqual(urls.auth_signup_complete(), response.request.path)
        self.assertTrue("No Available Rovers" in response)
        # Now validate the new user (who should still be logged in).
        validate_url = self.get_user_by_email(INVITE_EMAIL).url_validate()
        response = self.app.get(urls.root())
        response = self.app.get(validate_url)
        self.assertTrue("Account Authenticated" in response)
        response = self.app.get(urls.ops())
        self.assertEqual(urls.ops(), response.request.path)
        self.assert_logged_in(response)

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        vouchers = gamestate['user']['vouchers']
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)
        found_chips = self.chips_for_path(['user', 'vouchers', '*'])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['voucher_key'], VOUCHER_KEY_S1_GIFT)
        # Verify that the product that delivers this voucher is no longer available for the recipient.
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL in gamestate['user']['shop']['available_products'])
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'])
        self.assertEqual(len(found_chips), 0)
        found_chips = self.chips_for_path(['user', 'shop', 'available_products', PRODUCT_KEY_S1])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.DELETE)
        self.assertEqual(found_chips[0]['path'][-1], PRODUCT_KEY_S1)

        # Attempting to redeem the gift again should be an error.
        response = self.app.get(gift.url_gift_redeem())
        self.assertTrue('gift has already been redeemed' in response)
        self.assertTrue(gift.url_gift_redeem_new_user() not in response)
        response = self.app.get(gift.url_gift_redeem_new_user())
        self.assertTrue('gift has already been redeemed' in response)

    def test_admin_gift_redeem_existing(self):
        # Create an admin gift as the 'testuser@example.com' admin user.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                admin_user = self.get_logged_in_user(ctx=ctx)
                self.make_user_admin(admin_user)
                gift = admin.create_admin_gift_of_type(ctx, admin_user, gift_types.GFT_S1_PASS, "Testing Gift")

        # Check the lazy loaded fields for the GiftRedeemed subclass.
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.gifts_created), 1)
        gift = sender.gifts_created.values()[0]
        self.assertEqual(gift.creator.user_id, sender.user_id)
        self.assertIsNone(gift.redeemer)
        # Check the lazy loaded name and description.
        product = sender.shop.available_products[PRODUCT_KEY_S1]
        self.assertEqual(gift.name, product.name)
        self.assertEqual(gift.description, product.description)

        # Logout the admin user
        self.logout_user()
        # Create an existing user and login as them.
        self.create_user('existing@example.com', 'pw')
        response = self.app.get(gift.url_gift_redeem())
        response = response.click(href=gift.url_gift_redeem_existing_user())
        form = response.forms['form_login']
        form['login_email'].value = "existing@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        response = response.follow()

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        vouchers = gamestate['user']['vouchers']
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)
        found_chips = self.chips_for_path(['user', 'vouchers', '*'])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['voucher_key'], VOUCHER_KEY_S1_GIFT)
        # Verify that the product that delivers this voucher is no longer available for the recipient.
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL in gamestate['user']['shop']['available_products'])
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'])
        self.assertEqual(len(found_chips), 0)
        found_chips = self.chips_for_path(['user', 'shop', 'available_products', PRODUCT_KEY_S1])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.DELETE)
        self.assertEqual(found_chips[0]['path'][-1], PRODUCT_KEY_S1)

        # Attempting to redeem the gift again should be an error.
        response = self.app.get(gift.url_gift_redeem())
        self.assertTrue('gift has already been redeemed' in response)
        self.assertTrue(gift.url_gift_redeem_existing_user() not in response)
        response = self.app.get(gift.url_gift_redeem_existing_user())
        self.assertTrue('gift has already been redeemed' in response)

        # Check the lazy loaded fields for the GiftRedeemed subclass.
        redeemer = self.get_logged_in_user()
        self.assertEqual(len(redeemer.gifts_created), 0)
        self.assertEqual(len(redeemer.gifts_redeemed), 1)
        gift = redeemer.gifts_redeemed.values()[0]
        self.assertEqual(gift.creator.user_id, sender.user_id)
        self.assertEqual(gift.redeemer.user_id, redeemer.user_id)
        self.assertEqual(redeemer.campaign_name, "")

        # And check the lazy loaded fields for the GiftCreated now that they are all populated.
        self.logout_user()
        self.login_user("testuser@example.com", "pw")
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.gifts_redeemed), 0)
        self.assertEqual(len(sender.gifts_created), 1)
        gift = sender.gifts_created.values()[0]
        self.assertEqual(gift.creator.user_id, sender.user_id)
        self.assertEqual(gift.redeemer.user_id, redeemer.user_id)

    # Test buying a gift which sends an invitation and is redeemed by a new user.
    def test_buy_gift_with_invitation_new_user(self):
        response = self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_last_name=INVITE_LAST_NAME)

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()

        # A new purchased product of the expected type should exist.
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 1)
        product = gamestate['user']['shop']['purchased_products'].values()[0]
        self.assertEqual(product['product_key'], PRODUCT_KEY_S1_GIFT)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_S1_GIFT)

        # An invitation should have been sent with a gift attached.
        invitations = gamestate['user']['invitations']
        self.assertEqual(len(invitations), 1)
        # Verify that the truncation code in the validation step worked.
        self.assertEqual(invitations.values()[0]['recipient_last_name'], INVITE_LAST_NAME_TRUNCATED)
        invite = invitations.values()[0]

        # The gift is not put into the gamestate so check the model object itself.
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.gifts_created), 1)
        self.assertEqual(len(sender.gifts_redeemed), 0)
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertIsNone(invite_model.accepted_at)
        gift = invite_model.gift
        self.assertEqual(gift.creator_id, sender.user_id)
        self.assertFalse(gift.was_redeemed())

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        email = self._get_invite_accept_email()
        invite_accept_url = re.search(invite['urls']['invite_accept'], email.body_html).group(0)

        # Verify some of the expected data was inserted into the email body.
        self.assertEqual(INVITE_EMAIL, email.email_to)
        self.assertTrue(INVITE_FIRST_NAME in email.body_html)

        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender as we are creating a new user.
        self.logout_user()

        # Follow the accept invite URL as a not logged in user which should show a choice of whether
        # to redeem the gift for a new or existing user.
        response = self.app.get(invite_accept_url)
        # The inviters first name should be shown in the template to explain to the user who invited them.
        self.assertTrue(sender.first_name in response)

        # Select the redeem for new user option.
        response = response.click(href=gift.url_gift_redeem_new_user())

        # Assert the invite code is in the page.
        self.assertTrue('Invitation Code' in response)
        # And signup the user using the invite provided data and a user supplied password.
        form = response.forms['form_signup']
        # These fields should have been filled out.
        self.assertEqual(form['signup_email'].value, INVITE_EMAIL)
        self.assertEqual(form['first_name'].value, INVITE_FIRST_NAME)
        self.assertEqual(form['last_name'].value, INVITE_LAST_NAME_TRUNCATED)
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()
        # The new user should redirect back to / and since they are not authorized (haven't followed the backdoor link),
        # they should see the rover program is full message.
        response = response.follow()
        self.assertEqual(urls.auth_signup_complete(), response.request.path)
        self.assertTrue('No Available Rovers' in response)

        # Verify the recipient was created but still has not validated.
        self.logout_user()
        response = self.login_user(INVITE_EMAIL, 'pw')
        response = response.follow()  # Redirect from / to /capacity
        self.assertEqual(urls.auth_signup_complete(), response.request.path)
        self.assertTrue("No Available Rovers" in response)
        # Now login as the recipient and go through the validation process.
        recipient = self.get_logged_in_user()
        response = self.app.get(recipient.url_validate())
        self.assertTrue("Account Authenticated" in response)
        response = self.app.get(urls.ops())
        self.assertEqual(urls.ops(), response.request.path)
        self.assert_logged_in(response)

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        vouchers = gamestate['user']['vouchers']
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)

        # Verify that the product that delivers this voucher is no longer available for the recipient.
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL in gamestate['user']['shop']['available_products'])

        # Verify the senders invite was accepted.
        sender = self.get_user_by_email(sender.email)
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertIsNotNone(invite_model.accepted_at)

    # Test buying a gift which sends an invitation and is redeemed by an existing user.
    def test_buy_gift_with_invitation_existing_user(self):
        # NOTE: More extensive testing of the purchasing system is provided in test_buy_gift_with_invitation_new_user.
        response = self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_last_name=INVITE_LAST_NAME)

        # An invitation should have been sent with a gift attached.
        gamestate = self.get_gamestate()
        invitations = gamestate['user']['invitations']
        self.assertEqual(len(invitations), 1)
        # Verify that the truncation code in the validation step worked.
        self.assertEqual(invitations.values()[0]['recipient_last_name'], INVITE_LAST_NAME_TRUNCATED)
        invite = invitations.values()[0]

        # The gift is not put into the gamestate so check the model object itself.
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertIsNone(invite_model.accepted_at)
        gift = invite_model.gift

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        email = self._get_invite_accept_email()
        invite_accept_url = re.search(invite['urls']['invite_accept'], email.body_html).group(0)

        # Verify some of the expected data was inserted into the email body.
        self.assertEqual(INVITE_EMAIL, email.email_to)
        self.assertTrue(INVITE_FIRST_NAME in email.body_html)

        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender as we are going to signup a new user to be the redeemer.
        self.logout_user()
        EXISTING_EMAIL = 'testexisting@example.com'
        # Create and login as a new user which will be the 'existing' user.
        self.create_user(EXISTING_EMAIL, 'pw')
        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Follow the accept invite URL as the logged in user which should STILL show a choice of whether
        # to redeem the gift for a new or existing user.
        response = self.app.get(invite_accept_url)
        # The inviters first name should be shown in the template to explain to the user who invited them.
        self.assertTrue(sender.first_name in response)

        # Select the redeem for existing user option.
        response = response.click(href=gift.url_gift_redeem_existing_user())

        # And login as the existing user.
        form = response.forms['form_login']
        form['login_email'] = EXISTING_EMAIL
        form['login_password'] = "pw"
        response = form.submit()
        # The new user should redirect back to / and since they are authorized should redirect to ops.
        response = response.follow()  # Follow redirect to /
        response = response.follow()  # Follow redirect to /ops
        self.assertEqual(urls.ops(), response.request.path)
        self.assert_logged_in(response)

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        self.assertTrue(gamestate['user']['email'], EXISTING_EMAIL)
        vouchers = gamestate['user']['vouchers']
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)

        # Verify that the product that delivers this voucher is no longer available for the recipient.
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL in gamestate['user']['shop']['available_products'])

        # Verify the senders invite was accepted.
        sender = self.get_user_by_email(sender.email)
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertIsNotNone(invite_model.accepted_at)

    # Test redeeming multiple gifts, especially to check the user.current_voucher_level changes.
    def test_redeem_multiple_gifts(self):
        # Check the initial gamestate.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['vouchers']), 0)
        self.assertIsNone(gamestate['user']['current_voucher_level'])

        self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_email="testuser@example.com")
        gift_s1 = self.get_logged_in_user().gifts_created.values()[0]
        self.purchase_gift(PRODUCT_KEY_ALL_GIFT, recipient_email="testuser@example.com")
        gift_all = [g for g in self.get_logged_in_user().gifts_created.values() if g.gift_id != gift_s1.gift_id][0]

        # Redeem the S1 gift.
        response = self.app.get(gift_s1.url_gift_redeem())
        response = response.click(href=gift_s1.url_gift_redeem_existing_user())
        form = response.forms['form_login']
        form['login_email'].value = "testuser@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        response = response.follow()

        # A voucher should have been delivered.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['vouchers']), 1)
        self.assertTrue(VOUCHER_KEY_S1 in gamestate['user']['vouchers'])
        # And the current_voucher_level should have changed.
        self.assertEqual(gamestate['user']['current_voucher_level'], VOUCHER_KEY_S1)
        found_chips = self.chips_for_path(['user'])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['current_voucher_level'], VOUCHER_KEY_S1)

        # Clear chips
        self.advance_now(minutes=10)

        # Redeem the ALL gift.
        response = self.app.get(gift_all.url_gift_redeem())
        response = response.click(href=gift_all.url_gift_redeem_existing_user())
        form = response.forms['form_login']
        form['login_email'].value = "testuser@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        response = response.follow()

        # Another voucher should have been delivered.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['vouchers']), 2)
        self.assertTrue(VOUCHER_KEY_ALL in gamestate['user']['vouchers'])
        # And the current_voucher_level should have changed.
        self.assertEqual(gamestate['user']['current_voucher_level'], VOUCHER_KEY_ALL)
        found_chips = self.chips_for_path(['user'])
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['current_voucher_level'], VOUCHER_KEY_ALL)

    # Test purchasing multiple gifts, which are repurchased product objects.
    def test_buy_multiple_gifts(self):
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.shop.purchased_products), 0)
        self.assertEqual(len(sender.gifts_created), 0)

        self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_email="testrecipient1@example.com")
        self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_email="testrecipient2@example.com")
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.shop.purchased_products), 2)
        self.assertEqual(len(sender.gifts_created), 2)

    # Test buying a gift and redeeming it as the creator.
    def test_buy_gift_with_invitation_to_self(self):
        response = self.purchase_gift(PRODUCT_KEY_S1_GIFT)
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertIsNone(invite_model.accepted_at)
        sender_id = sender.user_id
        self.assertEqual(len(sender.gifts_created), 1)
        gift = sender.gifts_created.values()[0]

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()
        invitations = gamestate['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        email = self._get_invite_accept_email()
        invite_accept_url = re.search(invite['urls']['invite_accept'], email.body_html).group(0)

        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender to be sure logging in as them works.
        self.logout_user()

        # Follow the accept invite URL as a not logged in user.
        response = self.app.get(invite_accept_url)
        # Select the redeem for a new user option, however we will sign in as the existing.
        response = response.click(href=gift.url_gift_redeem_new_user())

        form = response.forms['form_signup']
        # These fields should have been filled out.
        self.assertEqual(form['signup_email'].value, INVITE_EMAIL)
        self.assertEqual(form['first_name'].value, INVITE_FIRST_NAME)
        # Fill out the signup form with the senders valid, existing user credentials.
        form['signup_email'] = "testuser@example.com"
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()
        user_id = self.assert_logged_in(response)

        # Verify got logged in as the sender.
        self.assertEqual(user_id, sender_id)

        # Verify the sender who became the recipient got the voucher for the gift.
        vouchers = self.get_gamestate()['user']['vouchers']
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)

        # Verify the senders invite was accepted.
        sender = self.get_user_by_email(sender.email)
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertIsNotNone(invite_model.accepted_at)

    # Test that a user created via an invitation (so has a user.inviter_id) who then receives another
    # invitation with a gift who then redeems that gift+invite for their existing account doesn't have their
    # inviter_id replaced and that the second invite is still mark as accepted. (in earlier versions of the schema
    # before invites could have gift attachments there was a unique constraint on invitations.recipient_id that
    # prevented this behavior from working.)
    def test_redeem_invite_gift_from_invited_user(self):
        # Create two admin invites (with gifts) as the 'testuser@example.com' admin user.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                admin_user = self.get_logged_in_user(ctx=ctx)
                admin_user_id = admin_user.user_id
                self.make_user_admin(admin_user)
                invite_params = {
                    'recipient_email': INVITE_EMAIL, 'recipient_first_name': INVITE_FIRST_NAME,
                    'recipient_last_name': INVITE_LAST_NAME_TRUNCATED, 'recipient_message': "Hello and welcome"
                }
                invite1 = admin.send_admin_invite_with_gift_type(ctx, admin_user, invite_params,
                                                                 gift_types.GFT_S1_PASS, "Testing Admin Invite+Gift")
                gift1 = invite1.gift
                invite2 = admin.send_admin_invite_with_gift_type(ctx, admin_user, invite_params,
                                                                 gift_types.GFT_ALL_PASS, "Testing Admin Invite+Gift")
                gift2 = invite2.gift
        self.logout_user()

        # Sign up a new user with the first invite.
        response = self.app.get(invite1.url_invite_accept())
        # Select the redeem for a new user option.
        response = response.click(href=gift1.url_gift_redeem_new_user())
        # Accept the invite as the new user.
        form = response.forms['form_signup']
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()
        # Now login as the recipient and go through the validation process.
        self.logout_user()
        self.login_user(INVITE_EMAIL, 'pw')
        self.app.get(self.get_logged_in_user().url_validate())

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        self.assertTrue(VOUCHER_KEY_S1_GIFT in gamestate['user']['vouchers'])

        # Now accept the second invite and gift, but login to the existing account when redeeming.
        response = self.app.get(invite2.url_invite_accept())
        # Select the redeem for a existing user option.
        response = response.click(href=gift2.url_gift_redeem_existing_user())
        # Accept the invite as the existing user.
        form = response.forms['form_login']
        form['login_email'] = INVITE_EMAIL
        form['login_password'] = "pw"
        response = form.submit()
        response = response.follow()

        # Verify the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        self.assertTrue(VOUCHER_KEY_ALL_GIFT in gamestate['user']['vouchers'])

        recipient = self.get_logged_in_user()
        # Verify both the admin inviter invites were accepted.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                admin_inviter = admin.get_admin_inviter_user(ctx)
                # The inviter_id for the new user should point back at the admin inviter user (Turing) who
                # was the inviter.
                self.assertEqual(recipient.inviter_id, admin_inviter.user_id)
                self.assertEqual(len(admin_inviter.invitations), 2)
                invite_model = admin_inviter.invitations.values()[0]
                self.assertIsNotNone(invite_model.accepted_at)
                self.assertEqual(invite_model.recipient_id, recipient.user_id)
                # But the gift creator_id should be the real human admin user who created the gifts/invites.
                self.assertEqual(invite_model.gift.creator_id, admin_user_id)
                self.assertEqual(invite_model.gift.redeemer_id, recipient.user_id)
                invite_model = admin_inviter.invitations.values()[1]
                self.assertIsNotNone(invite_model.accepted_at)
                self.assertEqual(invite_model.recipient_id, recipient.user_id)
                self.assertEqual(invite_model.gift.creator_id, admin_user_id)
                self.assertEqual(invite_model.gift.redeemer_id, recipient.user_id)

    # Test that redeeming a gift when the user already has that voucher is an error.
    def test_cannot_redeem_gift_if_have_voucher(self):
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=False, charge=charge)
        self.purchase_gift(PRODUCT_KEY_S1_GIFT)
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.gifts_created), 1)
        gift = sender.gifts_created.values()[0]

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()
        invitations = gamestate['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]
        vouchers = gamestate['user']['vouchers']
        self.assertEqual(len(vouchers), 1)
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        email = self._get_invite_accept_email()
        invite_accept_url = re.search(invite['urls']['invite_accept'], email.body_html).group(0)

        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender as we are going to accept the invite with their credentials.
        self.logout_user()

        # Follow the accept invite URL as a not logged in user.
        response = self.app.get(invite_accept_url)
        # Select the redeem for a existing user option.
        response = response.click(href=gift.url_gift_redeem_existing_user())

        form = response.forms['form_login']
        form['login_email'] = "testuser@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        # Attempting to redeem this gift should be an error shown on the page to the user since they already
        # have the voucher this gift was going to deliver.
        self.assertTrue('You cannot redeem this gift.' in response)

        self.login_user("testuser@example.com", "pw")
        # Verify nothing changed.
        gamestate = self.get_gamestate()
        invitations = gamestate['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]
        vouchers = gamestate['user']['vouchers']
        self.assertEqual(len(vouchers), 1)
        self.assertTrue(VOUCHER_KEY_S1_GIFT in vouchers)

    # Test that redeeming the s1 gift when the user already has the all voucher is denied.
    def test_cannot_redeem_s1_gift_if_have_all_voucher(self):
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_ALL], save_card=False, charge=charge)
        self.purchase_gift(PRODUCT_KEY_S1_GIFT)
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.gifts_created), 1)
        gift = sender.gifts_created.values()[0]

        # Grab the post purchase gamestate.
        invitations = self.get_gamestate()['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        email = self._get_invite_accept_email()
        invite_accept_url = re.search(invite['urls']['invite_accept'], email.body_html).group(0)

        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender as we are going to accept the invite with their credentials.
        self.logout_user()
        response = self.app.get(invite_accept_url)
        # Select the redeem for a existing user option.
        response = response.click(href=gift.url_gift_redeem_existing_user())
        form = response.forms['form_login']
        # Fill out the signup form with the senders valid, existing user credentials.
        form['login_email'] = "testuser@example.com"
        form['login_password'] = "pw"
        response = form.submit()
        # Attempting to redeem this gift should be an error shown on the page to the user since they already
        # have the ALL voucher which supersedes the voucher this gift was going to deliver.
        self.assertTrue('You cannot redeem this gift.' in response)

        self.login_user("testuser@example.com", "pw")
        # Verify nothing changed.
        gamestate = self.get_gamestate()
        invitations = gamestate['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]
        vouchers = gamestate['user']['vouchers']
        self.assertEqual(len(vouchers), 1)
        self.assertTrue(VOUCHER_KEY_ALL in vouchers)
        self.assertTrue(VOUCHER_KEY_S1_GIFT not in vouchers)

    # Test that receiving the ALL gift makes the S1 pass product unavailable.
    def test_buy_gift_all_removes_s1_pass(self):
        response = self.purchase_gift(PRODUCT_KEY_ALL_GIFT)
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.gifts_created), 1)
        gift = sender.gifts_created.values()[0]

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        invitations = self.get_gamestate()['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]
        email = self._get_invite_accept_email()
        invite_accept_url = re.search(invite['urls']['invite_accept'], email.body_html).group(0)
        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender as we are creating a new user.
        self.logout_user()
        # Follow the accept invite URL as a not logged in user.
        response = self.app.get(invite_accept_url)
        # Select the redeem for a new user option.
        response = response.click(href=gift.url_gift_redeem_new_user())
        # Accept the invite as the new user.
        form = response.forms['form_signup']
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()
        # Now login as the recipient and go through the validation process.
        self.logout_user()
        self.login_user(INVITE_EMAIL, 'pw')
        self.app.get(self.get_logged_in_user().url_validate())

        # Verify the sender who became the recipient got the voucher for the gift.
        gamestate = self.get_gamestate()
        self.assertTrue(VOUCHER_KEY_ALL_GIFT in gamestate['user']['vouchers'])
        # And verify the S1 product is not available (and also the ALL product is gone too).
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL not in gamestate['user']['shop']['available_products'])

    # Test that purchasing a gift invitation does not decrement invites_left.
    def test_buy_gift_no_change_in_invites_left(self):
        self.set_user_invites_left(1)
        self.assertEqual(self.get_logged_in_user().invites_left, 1)
        self.purchase_gift(PRODUCT_KEY_S1_GIFT)
        self.assertEqual(self.get_logged_in_user().invites_left, 1)

    # Test trying to purchase a gift invitation with a bad email address.
    def test_buy_gift_bad_email(self):
        response = self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_email="invalid&domain", status=400)
        self.assertTrue("Invalid email address" in response['errors'][0])

    # Test trying to purchase a gift invitation with missing values.
    def test_buy_gift_missing_data(self):
        # recipient_email is missing.
        response = self.purchase_gift(PRODUCT_KEY_S1_GIFT, recipient_email=None, status=400)
        self.assertTrue("Missing required field: recipient_email" in response['errors'][0])

    def _get_invite_accept_email(self):
        invite_emails = [e for e in self.get_sent_emails() if "Invitation" in e.subject]
        self.assertTrue(len(invite_emails) == 1)
        return invite_emails[0]
