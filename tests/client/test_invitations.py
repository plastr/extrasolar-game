# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re
from front.tests import base
from front.tests.base import INVITE_EMAIL, INVITE_FIRST_NAME, INVITE_LAST_NAME, INVITE_LAST_NAME_TRUNCATED

from front import Constants
from front.lib import urls
from front.models import chips

class TestInvitations(base.TestCase):
    def test_send_and_accept_invitation(self):
        # Add some unicode to the senders name to test a bug that was resolved.
        self.create_user('testuser@example.com', 'pw', first_name='First\xd9\xadName')
        invitations = self.get_gamestate()['user']['invitations']
        self.assertEqual(len(invitations), Constants.INITIAL_INVITATIONS)

        # Set the user invitations to 0 which is the assumed starting point for this test.
        self.set_user_invites_left(0)

        # Advance past the initial user setup and invites_left modification so chips etc. are empty.
        self.advance_game(minutes=10)

        # Emulate the user_increment_invites_left tool which is currently the only way to
        # grant more invitations since initial invite count is currently 0.
        self.set_user_invites_left(1)        

        # There should be a single chip updating the invites_left field.
        found_chips = self.chips_for_path(['user'])
        self.assertEqual(len(found_chips), 1)
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['invites_left'], 1)

        # Advance past the initial user setup and invites_left modification so chips etc. are empty.
        self.advance_game(minutes=10)

        # Store some sender values for the end of the test.
        u = self.get_logged_in_user()
        sender_user_id = str(u.user_id)
        sender_public_profile_url = u.url_public_profile()

        # Attempt to create an invitation with a bad email address.
        create_invite_url = str(self.get_gamestate()['urls']['create_invite'])
        payload = {
            'recipient_email': 'invalid&domain',
            'recipient_first_name': INVITE_FIRST_NAME,
            'recipient_last_name': INVITE_LAST_NAME,
            'recipient_message': 'Hello my friend.'
        }
        response = self.json_post(create_invite_url, payload, status=400)
        self.assertTrue("Invalid email address" in response['errors'][0])

        # Now create a valid, new invitation.
        payload = {
            'recipient_email': INVITE_EMAIL,
            'recipient_first_name': INVITE_FIRST_NAME,
            'recipient_last_name': INVITE_LAST_NAME,
            'recipient_message': 'Hello my friend, you should play this game! <a href="http://malware.example/">Malware</a>'
        }
        response = self.json_post(create_invite_url, payload)

        # There should be a chip updating the invites_left field to be decremented.
        found_chips = self.chips_for_path(['user'])
        self.assertEqual(len(found_chips), 1)
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['invites_left'], 0)

        # And a chip adding the invite to the invitations collection.
        found_chips = self.chips_for_path(['user', 'invitations', '*'])
        self.assertEqual(len(found_chips), 1)
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['recipient_email'], INVITE_EMAIL)
        self.assertIsNotNone(chip['value']['sent_at'])
        self.assertIsNone(chip['value']['accepted_at'])
        self.assertIsNone(chip['value']['recipient_id'])
        self.assertIsNone(chip['value']['urls']['recipient_public_profile'])

        # Check the gamestate invitations collection as well.
        invitations = self.get_gamestate()['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]
        self.assertEqual(invite['recipient_email'], INVITE_EMAIL)
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertEqual(invite_model.sender.user_id, sender.user_id)
        self.assertIsNone(invite_model.recipient)

        # Attempting to send another invite now that invites_left is 0 should be an error.
        payload = {
            'recipient_email': 'testotherecipient@example.com',
            'recipient_first_name': INVITE_FIRST_NAME,
            'recipient_last_name': INVITE_LAST_NAME,
            'recipient_message': 'Hello my friend.'
        }
        response = self.json_post(create_invite_url, payload, status=400)
        self.assertTrue("No more invitations are available" in response['errors'][0])

        # Pull the accept invite URL out of the invitation email (verifying it is present in the email body)
        self.assertEqual(len(self.get_sent_emails()), 1)
        email_body = self.get_sent_emails()[0].body_html
        invite_accept_url = re.search(invite['urls']['invite_accept'], email_body).group(0)

        # Verify some of the expected data was inserted into the email body.
        self.assertEqual(INVITE_EMAIL, self.get_sent_emails()[0].email_to)
        self.assertTrue(INVITE_FIRST_NAME in email_body)

        # Verify any HTML tags were escaped in the recipient_message
        self.assertFalse('<a href="http://malware.example/">Malware</a>' in email_body)
        self.assertTrue('&lt;a href="http://malware.example/"&gt;Malware&lt;/a&gt;' in email_body)

        # Advance past the invite creation chips etc. are empty.
        self.advance_game(minutes=10)

        # Logout the sender as we are creating a new user.
        self.logout_user()

        # Follow the accept invite URL as a not logged in user.
        response = self.app.get(invite_accept_url)

        # Assert the invite code is in the page.
        self.assertTrue('Invitation Code' in response)
        # Attempt to use the email for a user that already exists with a different password.
        form = response.forms['form_signup']
        form['signup_email'] = "testuser@example.com"
        form['signup_password'] = "otherpassword"
        response = form.submit()
        self.assertTrue("already taken" in response)
        # Attempt to use the email for a user that already exists with the correct password.
        response = self.app.get(invite_accept_url)
        form = response.forms['form_signup']
        form['signup_email'] = "testuser@example.com"
        form['signup_password'] = "pw"
        response = form.submit()
        response = response.follow()  # Follow redirect to /
        response = response.follow()  # Follow redirect to /ops
        # Should have signed in as that user and redirect to ops.
        self.assertEqual(response.request.path, urls.ops())

        # And now signup the user using the invite provided data and a user supplied password.
        self.logout_user()
        response = self.app.get(invite_accept_url)
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

        # Logout and attempt to follow the invite accept link again, which should redirect to / and
        # show the 'normal' root page (no rover program full message)
        self.logout_user()
        response = self.app.get(invite_accept_url)
        response = response.follow()
        self.assertEqual(urls.root(), response.request.path)
        self.assertTrue("No Available Rovers" not in response)

        # Login as the sender and verify that the invitations collection and chips were correct.
        self.login_user('testuser@example.com', 'pw')

        # Should be chip MODing the invite to the invitations collection.
        found_chips = self.chips_for_path(['user', 'invitations', '*'])
        self.assertEqual(len(found_chips), 1)
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertIsNotNone(chip['value']['accepted_at'])
        self.assertIsNotNone(chip['value']['recipient_id'])
        self.assertIsNotNone(chip['value']['urls']['recipient_public_profile'])

        # Check the gamestate invitations collection as well.
        invitations = self.get_gamestate()['user']['invitations']
        self.assertEqual(len(invitations), 1)
        invite = invitations.values()[0]
        self.assertEqual(invite['recipient_email'], INVITE_EMAIL)
        self.assertIsNotNone(invite['accepted_at'])
        self.assertIsNotNone(invite['urls']['recipient_public_profile'])

        # Now login as the recipient and go through the validation process.
        self.logout_user()
        response = self.login_user(INVITE_EMAIL, 'pw')
        response = response.follow()  # Follow redirect to /signup_complete
        self.assertEqual(urls.auth_signup_complete(), response.request.path)
        self.assertTrue("No Available Rovers" in response)

        recipient = self.get_logged_in_user()
        # Verify the invite supplied fields look correct.
        self.assertEqual(recipient.email, INVITE_EMAIL)
        self.assertEqual(recipient.first_name, INVITE_FIRST_NAME)
        self.assertEqual(recipient.last_name, INVITE_LAST_NAME_TRUNCATED)
        self.assertEqual(recipient.campaign_name, "")
        response = self.app.get(recipient.url_validate())
        self.assertTrue("Account Authenticated" in response)
        response = self.app.get(urls.ops())
        self.assertEqual(urls.ops(), response.request.path)
        self.assert_logged_in(response)

        # The new user who accepted the invite should have an inviter_id property that points back to the inviter
        gamestate = self.get_gamestate()
        inviter_id = gamestate['user']['inviter_id']
        self.assertEqual(inviter_id, sender_user_id)
        inviter = gamestate['user']['inviter']
        self.assertEqual(sender_public_profile_url, inviter['url_public_profile'])

        self.logout_user()
        self.login_user('testuser@example.com', 'pw')
        sender = self.get_logged_in_user()
        self.assertEqual(len(sender.invitations), 1)
        invite_model = sender.invitations.values()[0]
        self.assertEqual(invite_model.sender.user_id, sender.user_id)
        self.assertEqual(invite_model.recipient.user_id, recipient.user_id)
