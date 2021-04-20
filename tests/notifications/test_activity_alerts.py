# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re

from front import Constants, target_image_types, activity_alert_types
from front.lib import gametime, urls, db, utils
from front.models import species
from front.backend import notifications

from front.tests import base
from front.tests.base import points, rects, SIX_HOURS, DELAYED_SPECIES_KEY

class TestActivityAlerts(base.TestCase):
    def setUp(self):
        super(TestActivityAlerts, self).setUp()
        # The player will be notified about activity resulting from completing the simulator so do not force
        # completion to more accurately model the real player experience.
        self.create_validated_user('testuser@example.com', 'pw')
        self.user = self.get_logged_in_user()

    def test_activity_alerts_medium_frequency(self):
        self._run_example_activity_alerts_for_frequency(activity_alert_types.MEDIUM)

    def test_activity_alerts_long_frequency(self):
        self._run_example_activity_alerts_for_frequency(activity_alert_types.LONG)

    def test_no_activity_alerts_past_inactive_threshold(self):
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        self.advance_now(seconds=self.user.activity_alert_frequency_window)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Create on target to be sure there is reportable activity.
        self.create_target_and_move(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)

        # Now advance to the next notification window and verify there is a processed row and notification sent.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)
        self.assertEqual(len(user_activities[0].unviewed_targets), 1)

        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()

        # Now advance to the next notification window and verify there is a processed row and no notifications.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()

        # Move just before the the activity alerts inactive threshold and make sure there is still a processed row.
        self.advance_now(seconds=Constants.ACTIVITY_ALERT_INACTIVE_THRESHOLD - 10)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Finally, move past the activity alerts inactive threshold and verify there are no rows processed.
        self.advance_now(seconds=10 + self.user.activity_alert_frequency_window)
        user_activities = self._send_activity_alert(notified=0, processed=0)

        # Do one final big jump foward in time way past the inactive threshold to be extra sure no rows are processed.
        self.advance_now(seconds=Constants.ACTIVITY_ALERT_INACTIVE_THRESHOLD + 10)
        user_activities = self._send_activity_alert(notified=0, processed=0)

        # Load the gamestate to update the last_accessed time to now, emulating the user coming back to the game.
        self.get_gamestate()
        # Create on target to be sure there is reportable activity.
        self.create_target_and_move(arrival_delta=SIX_HOURS, **points.SECOND_MOVE)

        # Now advance to the next notification window and verify there is a processed row and notification sent.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)
        self.assertEqual(len(user_activities[0].unviewed_targets), 1)

    def test_activity_alerts_multiple_targets(self):
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        self.advance_now(seconds=self.user.activity_alert_frequency_window)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Create two targets and move the game to them, for a total of 12 hours of advancement.
        chip_result = self.create_target_and_move(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)
        arrival_time_date = self.user.after_epoch_as_datetime(chip['value']['arrival_time'])
        chip_result = self.create_target_and_move(arrival_delta=SIX_HOURS, **points.SECOND_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)

        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)
        # The earliest element should be the oldest target.
        self.assert_equal_seconds(user_activities[0].earliest, arrival_time_date)
        self.assertEqual(len(user_activities[0].unread_messages), 0)
        self.assertEqual(len(user_activities[0].unviewed_targets), 2)

    def test_activity_alerts_delayed_species(self):
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        self.advance_now(seconds=self.user.activity_alert_frequency_window)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Create a target and arrive at it. This target's arrival time becomes the 'anchor' for the
        # notification window (the oldest alerted activity).
        chip_result = self.create_target_and_move(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)
        arrival_time_date = self.user.after_epoch_as_datetime(chip['value']['arrival_time'])
        check_species_url = str(chip['value']['urls']['check_species'])

        # Verify the species being detected has delayed availability.
        species_id = species.get_id_from_key(DELAYED_SPECIES_KEY)
        species_delay = utils.in_seconds(minutes=species.delayed_minutes_for_id(species_id))
        self.assertTrue(species_delay > 0)
        # Advance time to half of the species delayed availability time subtracted from the full notification window.
        # This means that the species data will still be delayed within the notification window.
        self.advance_now(seconds=self.user.activity_alert_frequency_window - (species_delay / 2))

        # Detect a species on a new target known to have delayed species data.
        result = self.check_species(check_species_url, [rects.for_species_key(DELAYED_SPECIES_KEY)])
        # Verify the species appears to have delayed data.
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        self.assertTrue("PENDING" in chip['icon'])
        self.assertTrue(chip['available_at'] > chip['detected_at'])
        self.assertEqual(chip['available_at'] - chip['detected_at'], species_delay)

        # The delayed species should not show up in the activity immediatly as it has delayed data.
        # Advance the rest of the delayed data window to trigger the activity window which is still anchored by
        # the original target creation.
        self.advance_now(seconds=(species_delay / 2) + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)
        # The earliest element should be the target.
        self.assert_equal_seconds(user_activities[0].earliest, arrival_time_date)
        self.assertEqual(len(user_activities[0].unviewed_targets), 1)
        self.assertEqual(len(user_activities[0].unviewed_species), 0)

        # Now advance to the next notification window and the delayed species should now be notifiable activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + (species_delay / 2))
        user_activities = self._send_activity_alert(notified=1, processed=1)
        self.assertEqual(len(user_activities[0].unviewed_targets), 0)
        self.assertEqual(len(user_activities[0].unviewed_species), 1)
        # The species data should now be fully available.
        detected_species = user_activities[0].unviewed_species[0]
        # The earliest element should be the species (when it was detected, not available).
        self.assert_equal_seconds(user_activities[0].earliest, detected_species.detected_at_date)
        # And that species should be the same species that was detected.
        self.assertFalse(detected_species.is_currently_delayed())
        self.assertEqual(detected_species.species_id, species_id)
        self.assertTrue("PENDING" not in detected_species.icon)

    def test_activity_alerts_delayed_species_outside_window(self):
        ## Detected a delayed species on its own, with no other activity to anchor it within the notification window
        ## which means it should be sent out normally.
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        self.advance_now(seconds=self.user.activity_alert_frequency_window)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Create a target and arrive at it.
        chip_result = self.create_target_and_move(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)
        check_species_url = str(chip['value']['urls']['check_species'])
        # Flush out the target notification.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)

        # Detect a species on a new target known to have delayed species data.
        self.check_species(check_species_url, [rects.for_species_key(DELAYED_SPECIES_KEY)])
        species_id = species.get_id_from_key(DELAYED_SPECIES_KEY)
        # Now advance to the next notification window and the delayed species should now be notifiable activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)
        self.assertEqual(len(user_activities[0].unviewed_targets), 0)
        self.assertEqual(len(user_activities[0].unviewed_species), 1)
        # The species data should be fully available.
        detected_species = user_activities[0].unviewed_species[0]
        # The earliest element should be the species (when it was detected, not available).
        self.assert_equal_seconds(user_activities[0].earliest, detected_species.detected_at_date)
        # And that species should be the same species that was detected.
        self.assertFalse(detected_species.is_currently_delayed())
        self.assertEqual(detected_species.species_id, species_id)
        self.assertTrue("PENDING" not in detected_species.icon)        

    def test_activity_alerts_with_templating(self):
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        self.advance_now(seconds=self.user.activity_alert_frequency_window)

        # Add a target and render it but do not advance the game.
        self.create_target(arrival_delta=SIX_HOURS)
        self.render_next_target()

        # Advance 1 hour and create a message.
        self.advance_now(hours=1)
        message = self.send_mock_message_now(self.user, 'MSG_TEST_1')

        # Now move past the activity_alert_frequency_window and target arrival time and there
        # should be reportable activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + SIX_HOURS + 10)

        # The target should be arrived at now so thumbnail URL should be in gamestate.
        notify_target = self.get_most_recent_target_from_gamestate()
        thumbnail_url = notify_target['images'][target_image_types.THUMB]

        # Run the notifications tool with the real email sending callback, which in unit tests will
        # capture all sent emails, but the real templating will still occur.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_activity_alert_at(ctx, gametime.now(),
                                                                      notifications.send_activity_alert_email_callback)
        self.assertEqual(processed, 1)
        self.assertEqual(len(self.get_sent_emails()), 1)
        email_body = self.get_sent_emails()[0].body_html
        self.assertTrue("Recent Extrasolar Activity" in self.get_sent_emails()[0].subject)
        self.assertTrue("Hello, Testfirst" in email_body)
        # Verify the message being notified on is in the email.
        self.assertTrue(message.subject in email_body)
        # Verify the thumbnail URL for the target being notified on is in the email.
        self.assertTrue(thumbnail_url in email_body)

        # Verify that running the process again at the next window sends no emails.
        self.clear_sent_emails()
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_activity_alert_at(ctx, gametime.now(),
                                                                      notifications.send_activity_alert_email_callback)
        self.assertEqual(processed, 1)
        self.assertEqual(len(self.get_sent_emails()), 0)

    def test_activity_alerts_all_activity_types(self):
        # Advance to a point relatively deep into the story where we know achievements, species, and missions
        # have been added. Most importantly we need to advance to a point where we have a mission
        # that has parts to make sure those don't appear in the notification email.
        self.logout_user()
        self.replay_game('testuser@example.com', 'pw', to_point='OUTSIDE_AUDIO_MYSTERY01_ZONE')
        self.login_user('testuser@example.com', 'pw')

        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()

        # Send one message too since all messages are automatically marked viewed by the
        # replay_game system.
        message = self.send_mock_message_now(self.get_logged_in_user(), 'MSG_TEST_1')

        # Run the notifications tool with the real email sending callback, which in unit tests will
        # capture all sent emails, but the real templating will still occur.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_activity_alert_at(ctx, gametime.now(),
                                                                      notifications.send_activity_alert_email_callback)

        # Since this is a brand new user which just had a large number of moves played back
        # and has never had a notification email sent, we expect to see quite a bit of data to be
        # in the notification email. The purpose of this test is to make sure the template
        # is parsing/displaying all of the data types correctly.

        # Verify only one email was sent.
        self.assertEqual(processed, 1)
        self.assertEqual(len(self.get_sent_emails()), 1)
        email_body = self.get_sent_emails()[0].body_html

        # Verify that expected parts of the gamestate that were added while replaying the game
        # are all included in the notification email.
        user = self.get_logged_in_user()
        self.assertTrue("Recent Extrasolar Activity" in self.get_sent_emails()[0].subject)
        self.assertTrue("Hello, " + user.first_name in email_body)

        # Verify the message being notified on is in the email.
        self.assertTrue(message.subject in email_body)

        # The number of user created targets in the gamestate should equal the number
        # of thumbnail URLs listed in the notification email.
        target_count = 0
        for r in user.rovers.itervalues():
            for t in r.targets.pictures():
                if t.was_user_created():
                    target_count += 1
        self.assertTrue(target_count > 0, "Must have targets in the gamestate to test.")
        # Currently all fake rendered targets have the same thumbnail URL so just pull it
        # from the last target.
        found = re.findall(t.url_image_thumbnail, email_body)
        self.assertEqual(len(found), target_count)

        # Make sure that we have at least one child mission in the gamestate to be tested
        # that it is not in the email.
        at_least_one_child = False
        self.assertTrue(len(user.missions) > 0, "Must have missions in the gamestate to test.")
        for m in user.missions.itervalues():
            # The simulator mission is started/created when the user is created so it will never
            # be sent in a notification email.
            if m.mission_definition.startswith('MIS_SIMULATOR'):
                self.assertTrue(m.title not in email_body)
            # If a mission is a child mission, it should not be in the email.
            elif not m.is_root_mission():
                at_least_one_child = True
                self.assertTrue(m.title not in email_body)
            else:
                self.assertTrue(m.title in email_body)
        self.assertTrue(at_least_one_child, "Must test to see if child missions are excluded from the email.")

        # All species are detected after the user has been created so they should
        # all be in the email.
        self.assertTrue(len(user.species) > 0, "Must have species in the gamestate to test.")
        for s in user.species.itervalues():
            self.assertTrue(s.name in email_body)

        # All achieved achievements other than the created user achievement are achieved after the user has
        # been created so they should all be in the email.
        self.assertTrue(len(user.achievements.achieved()) > 0, "Must have achievements in the gamestate to test.")
        for a in user.achievements.achieved():
            if a.achievement_key == 'ACH_GAME_CREATE_USER':
                self.assertTrue(a.title not in email_body)
            else:
                self.assertTrue(a.title in email_body)

    def test_unsubcribe_activity_alerts(self):
        # Advance gametime.now() to a point beyond where all the the initial gamestate creation is done.
        self.advance_now(seconds=self.user.activity_alert_frequency_window)

        # Create a message.
        self.send_mock_message_now(self.user, 'MSG_TEST_1')

        # Now move past the activity_alert_frequency_window and there should be reportable activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)

        # Run the notifications tool with the real email sending callback, which in unit tests will
        # capture all sent emails, but the real templating will still occur.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_activity_alert_at(ctx, gametime.now(),
                                                                      notifications.send_activity_alert_email_callback)
        self.assertEqual(processed, 1)
        self.assertEqual(len(self.get_sent_emails()), 1)
        email_body = self.get_sent_emails()[0].body_html
        # Extract unsubscribe link from email_body and the link (we are not logged in right? be sure)
        unsubscribe_url = str(re.search(r'(%s)' % self.user.url_unsubscribe(), email_body).group(1))

        # Following this link should work without a valid authentication cookie.
        self.logout_user()
        response = self.app.get(unsubscribe_url)
        self.assertTrue("You have been unsubscribed" in response)

        # Send another message.
        self.send_mock_message_now(self.user, 'MSG_TEST_2')

        # Verify that running the process again at the next window sends no emails.
        self.clear_sent_emails()
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_activity_alert_at(ctx, gametime.now(),
                                                                      notifications.send_activity_alert_email_callback)
        self.assertEqual(processed, 0)
        self.assertEqual(len(self.get_sent_emails()), 0)

    def _run_example_activity_alerts_for_frequency(self, frequency):
        # Configure this test user to have the given notifications frequency.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                user.set_activity_alert_frequency(frequency)

        # Advance time to a point beyond the window size. There should be a row to process
        # but no activity as the user has done no reportable activity and digest_window_start
        # should have been initialized to a few minutes into the future to hide all user
        # creation activity from notification.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Advance just shy of the window and verify there is no row to process and no activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window - 10)
        user_activities = self._send_activity_alert(notified=0, processed=0)

        # Create a message to generate activity.
        message = self.send_mock_message_now(self.user, 'MSG_TEST_1')

        # There is still no reportable activity and no row should have been processed
        # as time has not advanced past the activity_alert_frequency_window.
        user_activities = self._send_activity_alert(notified=0, processed=0)

        # Now move past the activity_alert_frequency_window and there should be reportable activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + 10)
        user_activities = self._send_activity_alert(notified=1, processed=1)
        self.assert_equal_seconds(user_activities[0].earliest, message.sent_at_date)
        self.assertEqual(len(user_activities[0].unread_messages), 1)
        self.assertEqual(len(user_activities[0].unviewed_targets), 0)

        # Jump forward to just before the next window. There should be no row to process and no activity.
        self.advance_now(seconds=self.user.activity_alert_frequency_window - 10)
        user_activities = self._send_activity_alert(notified=0, processed=0)

        # And then move past the max window size. There should be a user to process
        # but no activity to notify on.
        self.advance_now(seconds=11)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Jump time forward far past the max window size. This simulates the digest system being
        # broken for a number of hours.
        self.advance_now(seconds=self.user.activity_alert_frequency_window + utils.in_seconds(hours=4))

        # Create a message.
        message = self.send_mock_message_now(self.user, 'MSG_TEST_2')

        # There should be activity to process, but nothing to notify on. This simulates
        # the digest system working again, and the digest_window_start time being updated
        # for this user to the earliest activity, namely the just sent message, but no
        # digest being sent.
        self.advance_now(seconds=self.user.activity_alert_frequency_window - 10)
        user_activities = self._send_activity_alert(notified=0, processed=1)

        # Now move past the activity_alert_frequency_window and there should be reportable activity.
        self.advance_now(seconds=11)
        user_activities = self._send_activity_alert(notified=1, processed=1)

        # Create a message.
        message = self.send_mock_message_now(self.user, 'MSG_TEST_3')

        # There should be no activity to report just before the window.
        self.advance_now(seconds=self.user.activity_alert_frequency_window - 10)
        user_activities = self._send_activity_alert(notified=0, processed=0)

        # Mark the message as read.
        self.json_get(urls.message_content(message.message_id))

        # Now move past the activity_alert_frequency_window and there should be no reportable
        # activity as the message was marked read.
        self.advance_now(seconds=11)
        user_activities = self._send_activity_alert(notified=0, processed=1)

    def _send_activity_alert(self, at_time=None, notified=0, processed=0):
        if at_time is None:
            at_time = gametime.now()
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                capture = _CaptureUserActivity()
                count = notifications.send_activity_alert_at(ctx, at_time, capture)
        self.assertEqual(count, processed, "Unexpected number of users processed for activity.")
        self.assertEqual(len(capture.user_activities), notified, "Unexpected number of users notified for activity.")
        return capture.user_activities

class _CaptureUserActivity(object):
    def __init__(self):
        self.user_activities = []
    def __call__(self, ctx, user, user_activity, at_time):
        self.user_activities.append(user_activity)
