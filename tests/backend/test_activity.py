# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import timedelta

from front.models import species
from front.lib import gametime, urls, db
from front.backend import activity
from front.tests import base
from front.tests.base import SIX_HOURS, DELAYED_SPECIES_KEY, rects

class TestActivity(base.TestCase):
    def test_recent_activity_for_user(self):
        self.create_user('testuser@example.com', 'pw')
        user = self.get_logged_in_user()
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        # In the window from then until 6 hours before, there should be no activity.
        self.advance_now(hours=10)
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        self.assertEqual(user_activity.earliest, None)
        self.assertEqual(len(user_activity.unread_messages), 0)
        self.assertEqual(len(user_activity.unviewed_targets), 0)

        # Advance 1 hour and create a message.  Make sure that message appears in a time window
        # that includes now.
        self.advance_now(hours=1)

        self.send_mock_message_now(self.get_logged_in_user(), 'MSG_TEST_1')
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        self.assert_equal_seconds(user_activity.earliest, gametime.now())
        self.assertEqual(len(user_activity.unread_messages), 1)
        self.assertEqual(len(user_activity.unviewed_targets), 0)

        # Create a target hours after the message was sent but don't process it.  We should have no unseen activity.
        self.advance_now(hours=10)
        # The target arrival_time is 6 hours from now.
        chip_result = self.create_target(arrival_delta=SIX_HOURS)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)
        arrival_time_date = user.after_epoch_as_datetime(chip['value']['arrival_time'])
        mark_target_viewed_url = str(chip['value']['urls']['mark_viewed'])
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        self.assertEqual(user_activity.earliest, None)
        self.assertEqual(len(user_activity.unread_messages), 0)
        self.assertEqual(len(user_activity.unviewed_targets), 0)

        # Now process the target and check again.  There should now be 1 unseen target.
        self.advance_now(hours=6)
        self.render_next_target()
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        self.assert_equal_seconds(user_activity.earliest, gametime.now())
        self.assertEqual(len(user_activity.unread_messages), 0)
        self.assertEqual(len(user_activity.unviewed_targets), 1)
        self.assertEqual(len(user_activity.unviewed_species), 0)

        # Identify a delayed species and make sure it does not show up in activity until it is fully available.
        self.advance_now(minutes=10)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.for_species_key(DELAYED_SPECIES_KEY)])
        # Verify the species chips.
        species_id = species.get_id_from_key(DELAYED_SPECIES_KEY)
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        self.assertTrue("Pending" in chip['name'])
        self.assertTrue("PENDING" in chip['icon'])
        self.assertTrue(chip['available_at'] > chip['detected_at'])
        mark_species_viewed_url = str(chip['urls']['mark_viewed'])

        # There should still be 1 unseen target and no unviewed species as this species has delayed data.
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        # The target should be the oldest activity.
        self.assert_equal_seconds(user_activity.earliest, arrival_time_date)
        self.assertEqual(len(user_activity.unread_messages), 0)
        self.assertEqual(len(user_activity.unviewed_targets), 1)
        self.assertEqual(len(user_activity.unviewed_species), 0)

        # Mark the target as viewed. Only the species should be in the activity.
        self.json_post(mark_target_viewed_url)

        # Advance to the point where the species data should now be available.
        available_after = chip['available_at'] - chip['detected_at']
        self.assertTrue(available_after > 0)
        self.advance_now(seconds=available_after)
        detected_at_date = user.after_epoch_as_datetime(chip['detected_at'])
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        # The detected time of the species should be the oldest activity.
        self.assert_equal_seconds(user_activity.earliest, detected_at_date)
        self.assertEqual(len(user_activity.unread_messages), 0)
        self.assertEqual(len(user_activity.unviewed_targets), 0)
        self.assertEqual(len(user_activity.unviewed_species), 1)

        # Send another message an hour later. There should now be a message and a species.
        self.advance_now(hours=1)
        message = self.send_mock_message_now(self.get_logged_in_user(), 'MSG_TEST_2')
        # There should now be a message and target in the activity.
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        # Earliest should be the species as it is still oldest.
        self.assert_equal_seconds(user_activity.earliest, detected_at_date)
        self.assertEqual(len(user_activity.unread_messages), 1)
        self.assertEqual(len(user_activity.unviewed_targets), 0)
        self.assertEqual(len(user_activity.unviewed_species), 1)

        # Mark the species as viewed. Only the message should be in the activity.
        self.json_post(mark_species_viewed_url)
        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        self.assert_equal_seconds(user_activity.earliest, message.sent_at_date)
        self.assertEqual(len(user_activity.unread_messages), 1)
        self.assertEqual(len(user_activity.unviewed_targets), 0)
        self.assertEqual(len(user_activity.unviewed_species), 0)

        # Mark the message as read. There should now be no activity.
        response = self.json_get(urls.message_content(message.message_id))
        self.assertTrue("Hello" in response['content_html'])

        user_activity = self._recent_activity(gametime.now() - timedelta(hours=6), gametime.now())
        self.assertEqual(user_activity.earliest, None)
        self.assertEqual(len(user_activity.unread_messages), 0)
        self.assertEqual(len(user_activity.unviewed_targets), 0)

    def test_recent_activity_all_types(self):
        # Advance to a point relatively deep into the story where we know achievements, species, and missions
        # have been added.
        self.replay_game('testuser@example.com', 'pw', to_point='AT_STUCK_ROVER')
        self.login_user('testuser@example.com', 'pw')

        # Send one message too since all messages are automatically marked viewed by the
        # replay_game system.
        self.send_mock_message_now(self.get_logged_in_user(), 'MSG_TEST_1')

        # Reach back to when the user was created for the activity so we are sure to get activity from all datatypes.
        user = self.get_logged_in_user()
        user_activity = self._recent_activity(user.epoch, gametime.now())

        self.assertIsNotNone(user_activity.earliest)
        self.assertTrue(len(user_activity.unread_messages) > 0)
        self.assertTrue(len(user_activity.unviewed_targets) > 0)
        self.assertTrue(len(user_activity.unviewed_missions) > 0)
        self.assertTrue(len(user_activity.unviewed_species) > 0)
        self.assertTrue(len(user_activity.unviewed_achievements) > 0)

    def _recent_activity(self, since, until):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                return activity.recent_activity_for_user(ctx, user, since, until)
