# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import timedelta

from front import Constants
from front.lib import gametime, db, utils, get_uuid, email_module, locking
from front.backend import email_queue
from front.cron import vacuum_old_chips, process_email_queue, run_deferred_actions, send_notifications, alert_delayed_renderer
from front.cron import cleanup_target_render_metadata

from front.tests import base
from front.tests.base import points, SIX_HOURS

class TestCronTools(base.TestCase):
    def setUp(self):
        super(TestCronTools, self).setUp()
        self.create_user('testuser@example.com', 'pw')
        self.user = self.get_logged_in_user()

    def test_vacumm_old_chips(self):
        # Send a dummy message and verify there was a chip issued.
        self.send_message_now(self.user, 'MSG_TEST_SIMPLE')
        chip = self.last_chip_for_path(['user', 'messages', '*'])
        self.assertNotEqual(chip, None)

        # Move time forward.
        self.advance_now(hours=vacuum_old_chips.DELETE_SINCE_HOURS)

        # Vacuum the chips older than DELETE_SINCE_HOURS ago.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            since = gametime.now() - timedelta(hours=vacuum_old_chips.DELETE_SINCE_HOURS)
            vacuum_old_chips.vacuum_chips(ctx, since)

        # Get any messages chips for the last DELETE_SINCE_HOURS hours + 30 seconds ago.
        chip = self.last_chip_for_path(['user', 'messages', '*'],
                                       seconds_ago=utils.in_seconds(hours=vacuum_old_chips.DELETE_SINCE_HOURS)+30)
        # There should be no messages chips as they were vacuumed.
        self.assertEqual(chip, None)

    def test_cleanup_target_render_metadata(self):
        # This process runs on real time, not gametime, so it's no easy to simulate the conditions
        # needed to verify proper cleanup. Let's just make sure the routine runs without throwing
        # any errors.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            cleanup_target_render_metadata.delete_target_render_metadata(ctx)

    def test_process_email_queue(self):
        # Enqueue an email to process.
        test_email = email_module.EmailMessage('fromuser@example.com', 'touser@example.com', 'Test Subject', 'Test Body')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                email_queue.enqueue_email_message(ctx, test_email)

        # Force the process lock to be held before running the processing, meaning no rows should be processed.
        # This simulates another email queue process running on another server which has already acquired this lock.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with locking.acquire_db_lock(ctx, process_email_queue.LOCK_NAME):
                processed = process_email_queue.process_email_queue(ctx)
        # There should have been no email processed, as the lock was already held.
        self.assertEqual(processed, 0)

        # Now run the process email queue tool again, making sure the one piece of email was processed.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            processed = process_email_queue.process_email_queue(ctx)
        self.assertEqual(processed, 1)

    def test_run_deferred_actions(self):
        # Create a target which will have a deferred event (arrived_at_target.)
        self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)

        # Move time forward to the arrival_time of the target plus a second.
        self.advance_now(seconds=SIX_HOURS + 1)

        # Force the process lock to be held before running the processing, meaning no rows should be processed.
        # This simulates another run deferred process running on another server which has already acquired this lock.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with locking.acquire_db_lock(ctx, run_deferred_actions.LOCK_NAME):
                since = gametime.now()
                processed = run_deferred_actions.run_deferred_actions(ctx, since)
        # There should have been no deferreds processed, as the lock was already held.
        self.assertEqual(processed, 0)

        # Now run the deferred tool again, making sure at least one deferred was processed.
        # Now run the deferred tool.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            since = gametime.now()
            processed = run_deferred_actions.run_deferred_actions(ctx, since)
        self.assertTrue(processed > 0)

    def test_send_notifications(self):
        # Load the gamestate to update the last_accessed time to now which will trigger lure activity.
        self.get_gamestate()

        # Now move past the lure window and there should be reportable activity for both lure and activity alerts.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)

        # Now run the send_notifications tool, once for each activity type.
        for alert_type in send_notifications.ALERT_TYPES:
            with db.commit_or_rollback(self.get_ctx()) as ctx:
                at_time = gametime.now()
                processed = send_notifications.send_notifications(ctx, alert_type, at_time)
                # There should have been some activity processed.
                self.assertTrue(processed > 0)

    def test_alert_delayed_renderer(self):
        # Create two targets for testing, 1 that will trigger the alert, the other which is not yet ready
        # for rendering.
        chips_result = self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        first_target_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)['target_id']
        chips_result = self.create_target(arrival_delta=SIX_HOURS*2, **points.SECOND_MOVE)
        second_target_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)['target_id']

        # Verify no alert would be sent since this target isn't delayed yet.
        email_address = "bogus@example.com"
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            render_after = gametime.now() - timedelta(minutes=alert_delayed_renderer.ALERT_PROCESSED_MINUTES)
            rows = alert_delayed_renderer.alert_unprocessed_targets_before(ctx, render_after, email_address)
            self.assertEqual(len(rows), 0)
        # No email should have been sent.
        self.assertEqual(len(self.get_sent_emails()), 0)

        # Move time forward.
        self.advance_now(minutes=alert_delayed_renderer.ALERT_PROCESSED_MINUTES)

        # There should now be a delayed unprocessed target.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            render_after = gametime.now() - timedelta(minutes=alert_delayed_renderer.ALERT_PROCESSED_MINUTES)
            rows = alert_delayed_renderer.alert_unprocessed_targets_before(ctx, render_after, email_address)
            self.assertEqual(len(rows), 1)
            self.assertEqual(str(get_uuid(rows[0]['target_id'])), first_target_id)

        # And an alert email should have been sent.
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertEqual(email_address, self.get_sent_emails()[0].email_to)
        self.assertTrue("Unprocessed Targets" in self.get_sent_emails()[0].subject)
        self.assertTrue("1 picture target" in self.get_sent_emails()[0].body_html)
        self.assertTrue(str(alert_delayed_renderer.ALERT_PROCESSED_MINUTES) + " minutes ago" in self.get_sent_emails()[0].body_html)
        self.clear_sent_emails()

        # Now render the first target.
        self.render_next_target(assert_only_one=True)

        # Verify no alert would be sent since the target is now rendered.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            render_after = gametime.now() - timedelta(minutes=alert_delayed_renderer.ALERT_PROCESSED_MINUTES)
            rows = alert_delayed_renderer.alert_unprocessed_targets_before(ctx, render_after, email_address)
            self.assertEqual(len(rows), 0)
        # No email should have been sent.
        self.assertEqual(len(self.get_sent_emails()), 0)

        # Mark the first target for reendering. Since this targets render_at has already been arrived at, this will
        # update its render_at time to 'now'.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            reprocess_target = self.get_logged_in_user(ctx=ctx).rovers.find_target_by_id(first_target_id)
            render_at_before = reprocess_target.render_at
            reprocess_target.mark_for_rerender()
            reprocess_target = self.get_logged_in_user(ctx=ctx).rovers.find_target_by_id(first_target_id)
            self.assertNotEqual(reprocess_target.render_at, render_at_before)
            self.assertTrue(utils.seconds_between_datetimes(reprocess_target.render_at, gametime.now()) < 1)

        # Move time forward to the next alert processing window past the new render_at time for the first target.
        self.advance_now(minutes=alert_delayed_renderer.ALERT_PROCESSED_MINUTES)

        # One again there should now be a delayed, unprocessed target (the target marked for rerendering).
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            render_after = gametime.now() - timedelta(minutes=alert_delayed_renderer.ALERT_PROCESSED_MINUTES)
            rows = alert_delayed_renderer.alert_unprocessed_targets_before(ctx, render_after, email_address)
            self.assertEqual(len(rows), 1)
            self.assertEqual(str(get_uuid(rows[0]['target_id'])), first_target_id)
        # And an alert email should have been sent.
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.clear_sent_emails()

        # To test a code path that is handled in mark_for_rerender but is currently not easily triggered by an
        # admin, also mark the second target for rerender and verify that its render_at time does not change
        # as it is in in the future.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            reprocess_target = self.get_logged_in_user(ctx=ctx).rovers.find_target_by_id(second_target_id)
            render_at_before = reprocess_target.render_at
            reprocess_target.mark_for_rerender()
            reprocess_target = self.get_logged_in_user(ctx=ctx).rovers.find_target_by_id(second_target_id)
            self.assertEqual(reprocess_target.render_at, render_at_before)
