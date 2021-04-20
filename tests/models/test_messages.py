# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re

from front.lib import db, utils
from front.models import chips
from front.models import message as message_module
from front.callbacks import message_callbacks
from front.tests import base

class TestMessaging(base.TestCase):
    def setUp(self):
        super(TestMessaging, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_simple_message_send_and_read(self):
        user = self.get_logged_in_user()
        # Send a message a few seconds into the future to guarantee that it's first in the sorted list.
        self.advance_now(seconds=10)
        new_message = self.send_message_now(user, 'MSG_TEST_SIMPLE')
        self.assertIsNotNone(new_message)

        gamestate = self.get_gamestate()
        # The first message is now the test message, welcome message is second.
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertTrue("Test Sender" in message['sender'])
        self.assertTrue("simple test" in message['subject'])
        self.assertEqual(message['read_at'], None)
        self.assertEqual(message['needs_password'], 0)
        self.assertEqual(message['locked'], 0)
        found = self.chips_for_path(['user', 'messages', '*'])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['action'], chips.ADD)
        self.assertTrue("simple test" in found[0]['value']['subject'])
        self.assertEqual(found[0]['value']['read_at'], None)

        # Act like the user comes back 10 minutes later and reads the message (to move past ADD chip)
        self.advance_now(minutes=10)
        body_url = str(message['urls']['message_content'])
        response = self.json_get(body_url)
        self.assertTrue("Hello World" in response['content_html'])
        found = self.chips_for_path(['user', 'messages', '*'], response)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['action'], chips.MOD)
        self.assertNotEqual(found[0]['value']['read_at'], None)

        # The message should now be read.
        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertNotEqual(message['read_at'], None)
        self.assertEqual(message['locked'], 0)

        # Attempting to send an existing message to the user's gamestate should log a warning and return None.
        self.expect_log('front.models.message', 'Refusing to send exising msg_type')
        new_message = self.send_message_now(user, 'MSG_TEST_SIMPLE')
        self.assertIsNone(new_message)

    def test_send_all_now(self):
        gamestate = self.get_gamestate()
        count = len(gamestate['user']['messages'])

        user = self.get_logged_in_user()
        # Send two messages a few seconds into the future to guarantee that they come after any other messages.
        self.advance_now(seconds=10)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                return message_module.send_all_now(ctx, user, ['MSG_TEST_SIMPLE', 'MSG_TEST_LOCKED'])

        # Verify the messages appear to be in the correct order.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['messages']), count + 2)
        self.assertTrue("simple test" in gamestate['user']['messages'][-2]['subject'])
        self.assertTrue("test locked message" in gamestate['user']['messages'][-1]['subject'])
        self.assertTrue(gamestate['user']['messages'][-2]['sent_at'] < gamestate['user']['messages'][-1]['sent_at'])

    def test_send_later(self):
        gamestate = self.get_gamestate()
        count_before = len(gamestate['user']['messages'])

        user = self.get_logged_in_user()
        self.assertFalse(user.messages.has_been_queued_or_delivered('MSG_TEST_SIMPLE'))

        deliver_seconds = utils.in_seconds(minutes=5)
        # Send a message a few minutes in the future.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                message_module.send_later(ctx, user, 'MSG_TEST_SIMPLE', deliver_seconds)

                # Verify the message was queued.
                self.assertTrue(user.messages.has_been_queued_or_delivered('MSG_TEST_SIMPLE'))

        self.advance_game(seconds=deliver_seconds)
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['messages']), count_before + 1)
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertEqual(message['msg_type'], 'MSG_TEST_SIMPLE')
        user = self.get_logged_in_user()
        self.assertTrue(user.messages.has_been_queued_or_delivered('MSG_TEST_SIMPLE'))

    def test_should_deliver(self):
        SHOULD_DELIVER = None
        class MSG_TEST_SIMPLE_Callbacks(message_callbacks.BaseCallbacks):
            @classmethod
            def should_deliver(cls, ctx, user):
                return SHOULD_DELIVER
        self.inject_callback(message_callbacks, MSG_TEST_SIMPLE_Callbacks)

        # Send a message a few seconds into the future to guarantee that it's first in the sorted list.
        user = self.get_logged_in_user()
        self.advance_now(seconds=10)
        SHOULD_DELIVER = False
        m = self.send_message_now(user, 'MSG_TEST_SIMPLE')
        self.assertIsNone(m)
        message = _most_recent_message_from_gamestate(self.get_gamestate())
        self.assertNotEqual(message['msg_type'], 'MSG_TEST_SIMPLE')
        SHOULD_DELIVER = True
        m = self.send_message_now(user, 'MSG_TEST_SIMPLE')
        self.assertEqual(m.msg_type, 'MSG_TEST_SIMPLE')
        message = _most_recent_message_from_gamestate(self.get_gamestate())
        self.assertEqual(message['msg_type'], 'MSG_TEST_SIMPLE')

    def test_forwarding(self):
        user = self.get_logged_in_user()
        # Send a message a few seconds into the future to guarantee that it's first in the sorted list.
        self.advance_now(seconds=10)
        self.send_message_now(user, 'MSG_TEST_SIMPLE')

        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertTrue("Test Sender" in message['sender'])
        found = self.chips_for_path(['user', 'messages', '*'])
        self.assertEqual(len(found), 1)
        forward_url = str(message['urls']['message_forward'])

        # Advance time to clear chips and assure message sort order.
        self.advance_now(minutes=10)

        # Attempt to forward the message. This should result in a default hint message
        # being sent to the user a few minutes later.
        payload = {'recipient': 'KRYPTEX'}
        response = self.json_post(forward_url, payload)
        found = self.chips_for_path(['user', 'messages', '*'], response)
        self.assertEqual(len(found), 0)  # Nothing yet (It's delayed).
        
        # Advance far enough to get our message.
        self.advance_game(minutes=10)
        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertEqual(message['msg_type'], 'MSG_NO_FORWARD_TO_KRYPTEX')

        # Repeat. This time, send to someone else to prompt a different hint.
        payload = {'recipient': 'TURING'}
        response = self.json_post(forward_url, payload)
        self.advance_game(minutes=10)
        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertEqual(message['msg_type'], 'MSG_NO_FORWARDa')

        # Attempt to forward the message again. This should result in a second default hint message
        # being sent to the user.
        payload = {'recipient': 'TURING'}
        response = self.json_post(forward_url, payload)
        self.advance_game(minutes=10)
        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertEqual(message['msg_type'], 'MSG_NO_FORWARDb')
        num_messages_before = len(gamestate['user']['messages'])

        # Advance time to clear chips and assure message sort order.
        self.advance_now(minutes=10)

        # Attempt to forward the message again. This should result in no new messages being sent.
        payload = {'recipient': 'KRYPTEX'}
        response = self.json_post(forward_url, payload)
        gamestate = self.get_gamestate()
        num_messages_after = len(gamestate['user']['messages'])
        self.assertEqual(num_messages_before, num_messages_after)

        # Attempt to forward the message with no recipient, which is an error.
        payload = {}
        response = self.json_post(forward_url, payload, status=400)
        self.assertTrue(len(response['errors']) > 0)

    def test_message_locked(self):
        user = self.get_logged_in_user()
        # Send a message a few seconds into the future to guarantee that it's first in the sorted list.
        self.advance_now(seconds=10)
        m = self.send_message_now(user, 'MSG_TEST_LOCKED')
        # Because the keycode includes the user.user_id which is different on every test run
        # we need to pull this value from the server side model.
        keycode = m.keycode

        gamestate = self.get_gamestate()
        # The first message is now the test message, welcome message is second.
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertTrue("Test Sender" in message['sender'])
        self.assertTrue("test locked message" in message['subject'])
        self.assertEqual(message['read_at'], None)
        self.assertEqual(message['needs_password'], 1)
        self.assertEqual(message['locked'], 1)

        # The message is locked so the content should now be the locked body.
        body_url = str(message['urls']['message_content'])
        response = self.json_get(body_url)
        content_html = response['content_html']
        self.assertTrue("message is secured" in content_html)
        # The unlock URL is the action property of the unlock form.
        unlock_url = str(re.search(r'data-url="(.*)">', content_html).group(1))

        # The message should be marked read even if it is still locked.
        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertIsNotNone(message['read_at'])
        chip = self.last_chip_value_for_path(['user', 'messages', '*'], response)
        self.assertIsNotNone(chip['read_at'])

        # Attempt to unlock the message with an invalid password.
        payload = {'password':'invalid'}
        response = self.json_post(unlock_url, payload)
        self.assertFalse(response['was_unlocked'])
        self.assertTrue("message is secured" in response['content_html'])

        # Now unlock the message.
        payload = {'password':keycode}
        response = self.json_post(unlock_url, payload)
        self.assertTrue(response['was_unlocked'])
        self.assertTrue("this is a test message" in response['content_html'])
        chip = self.last_chip_value_for_path(['user', 'messages', '*'], response)
        self.assertEqual(chip['locked'], 0)

        # And the message content should now be the unlocked body.
        body_url = str(message['urls']['message_content'])
        response = self.json_get(body_url)
        self.assertTrue("this is a test message" in response['content_html'])

        # The message should now be read and unlocked.
        gamestate = self.get_gamestate()
        message = _most_recent_message_from_gamestate(gamestate)
        self.assertIsNotNone(message['read_at'])
        self.assertEqual(message['locked'], 0)

        # Advance time to clear chips.
        self.advance_now(minutes=10)

        # Attempt to unlock the message again, which should act the same on the client but do nothing
        # on the server and log a warning.
        self.expect_log('front.models.message', 'Refusing to unlock unlocked message')
        response = self.json_post(unlock_url, payload)
        self.assertTrue(response['was_unlocked'])
        self.assertTrue("this is a test message" in response['content_html'])
        # No chip should be issued since no change in data.
        chip = self.last_chip_value_for_path(['user', 'messages', '*'], response)
        self.assertIsNone(chip)

        # Attempt to unlock the message with no password, which is an error.
        payload = {}
        response = self.json_post(unlock_url, payload, status=400)
        self.assertTrue(len(response['errors']) > 0)

    def test_message_locked_lower_case(self):
        # Send a message a few seconds into the future to guarantee that it's first in the sorted list.
        self.advance_now(seconds=10)
        m = self.send_message_now(self.get_logged_in_user(), 'MSG_TEST_LOCKED')
        keycode = m.keycode
        # Lower case the keycode to make sure if the user doesn't capitalize it will still work.
        keycode_lower = keycode.lower()
        self.assertNotEqual(keycode, keycode_lower)

        self.assertEqual(_most_recent_message_from_gamestate(self.get_gamestate())['locked'], 1)
        unlock_url = m.url_unlock()
        # Now unlock the message with the lowercase password.
        payload = {'password':keycode_lower}
        response = self.json_post(unlock_url, payload)
        self.assertTrue(response['was_unlocked'])
        # The message should now be unlocked.
        self.assertEqual(_most_recent_message_from_gamestate(self.get_gamestate())['locked'], 0)

def _most_recent_message_from_gamestate(gamestate):
    messages = gamestate['user']['messages'].values()
    by_sent_at = sorted(messages, key=lambda m: m['sent_at'], reverse=True)
    return by_sent_at[0]
