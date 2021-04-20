# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import urls, db
from front.models import chips
from front.models import progress as progress_module
from front.tests import base

class TestMessaging(base.TestCase):
    def setUp(self):
        super(TestMessaging, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_create_client_progress(self):
        gamestate = self.get_gamestate()
        # Construct a valid client side progress key
        test_key = progress_module.CLIENT_NAMESPACES[0] + "_TESTING"
        self.assertTrue(test_key not in gamestate['user']['progress'])
        # Pull the create progress URL from the gamestate.
        create_progress_url = str(gamestate['urls']['create_progress'])

        # Now create the key from the client.
        payload = {'key': test_key, 'value': 'test_value'}
        response = self.json_post(create_progress_url, payload)
        # Verify there were chips and gamestate changes
        found = self.chips_for_path(['user', 'progress', '*'], response)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['action'], chips.ADD)
        self.assertEqual(found[0]['value']['key'], test_key)
        self.assertEqual(found[0]['value']['value'], 'test_value')
        gamestate = self.get_gamestate()
        self.assertTrue(test_key in gamestate['user']['progress'])

        # Attempt to create the key again, which is an error.
        response = self.json_post(create_progress_url, payload, status=400)
        self.assertTrue('already present' in response['errors'][0])

        # Advance time to clear chips.
        self.advance_now(minutes=10)

        # And then reset the key, which removes it from the gamestate.
        reset_progress_url = str(gamestate['user']['progress'][test_key]['urls']['reset'])
        response = self.json_post(reset_progress_url)
        # Verify there were chips and gamestate changes
        found = self.chips_for_path(['user', 'progress', '*'], response)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['action'], chips.DELETE)
        self.assertEqual(found[0]['path'][-1], test_key)
        gamestate = self.get_gamestate()
        self.assertTrue(test_key not in gamestate['user']['progress'])

        # Attempt to reset the just reset key, which is an error.
        response = self.json_post(reset_progress_url, status=400)
        self.assertTrue('cannot be reset' in response['errors'][0])

        # Should not be able to create or reset a non-client allowed progress key
        payload = {'key': "PRO_BOGUS_KEY", 'value': ''}
        response = self.json_post(create_progress_url, payload, status=400)
        self.assertTrue('Invalid client progress' in response['errors'][0])
        response = self.json_post(urls.client_progress_reset("PRO_BOGUS_KEY"), status=400)
        self.assertTrue('Invalid client progress' in response['errors'][0])

    def test_create_duplicate_server_progress(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                prog = progress_module.create_new_progress(ctx, user, 'PRO_TESTING_KEY')
                self.assertIsNotNone(prog)

                # Attempting to send an existing progress key to the user's gamestate should log a warning
                # and return None.
                self.expect_log('front.models.progress', 'Refusing to add exising progress key')
                prog = progress_module.create_new_progress(ctx, user, 'PRO_TESTING_KEY')
                self.assertIsNone(prog)
