# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re

from front import Constants
from front.lib import gametime, db
from front.backend import notifications

from front.tests import base
from front.tests.base import points, rects, SIX_HOURS

class TestLureAlerts(base.TestCase):
    def setUp(self):
        super(TestLureAlerts, self).setUp()
        self.create_user('testuser@example.com', 'pw')
        self.user = self.get_logged_in_user()

    def test_lure_alerts(self):
        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()

        # There should be no lure sent if run immediatly for a new user.
        user_activities = self._send_lure_alert(notified=0, processed=0)
        # And no lure up to a second before the lure threshold time.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW - 1)
        user_activities = self._send_lure_alert(notified=0, processed=0)
        # But once passing the lure threshold, there should be a lure sent for all of the initial gamestate data
        # the user never viewed or completed.
        self.advance_now(seconds=2)
        user_activities = self._send_lure_alert(notified=1, processed=1)
        # There should be one LureUserActivity object captured.
        lure_activity = user_activities[0]
        # There should be at least one incomplete task, and a few unviewed messages and recent targets.
        self.assertTrue(lure_activity.has_lure_activity())
        self.assertTrue(len(lure_activity.not_done_missions) > 0)
        self.assertTrue(len(lure_activity.unread_messages) > 0)
        self.assertTrue(lure_activity.unviewed_targets_count > 0)
        self.assertTrue(len(lure_activity.recent_targets) > 0)

        # The last_accessed time was not changed, so going to the next lure threshold window should result in nothing
        # to process or notify on.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)
        user_activities = self._send_lure_alert(notified=0, processed=0)

        # However if the last_accessed time is changed, then another lure should be sent again.
        self.get_gamestate()
        # And it should have the same counts for the activity in the first lure sent.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)
        user_activities = self._send_lure_alert(notified=1, processed=1)
        # There should be at least one incomplete task, and a few unviewed messages and recent targets.
        self.assertTrue(user_activities[0].has_lure_activity())
        self.assertEqual(len(lure_activity.not_done_missions), len(user_activities[0].not_done_missions))
        self.assertEqual(len(lure_activity.unread_messages), len(user_activities[0].unread_messages))
        self.assertEqual(lure_activity.unviewed_targets_count, user_activities[0].unviewed_targets_count)
        self.assertEqual(len(lure_activity.recent_targets), len(user_activities[0].recent_targets))

        # Emulate logging back into the game (updating last_accessed flag).
        self.get_gamestate()
        # And also go back and mark all of the alerted on not done missions as done and the unread messages and recent
        # targets as viewed.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                # The db context used for the models in the UserActivity object has been closed so
                # need to lookup the models fresh in order to modify them.
                u = self.get_logged_in_user(ctx=ctx)
                for m in lure_activity.not_done_missions:
                    assert m.is_root_mission()
                    if len(m.parts) == 0:
                        u.missions[m.mission_id].mark_done()
                    else:
                        for p in m.parts:
                            u.missions[p.mission_id].mark_done()
                for m in lure_activity.unread_messages:
                    u.messages[m.message_id].mark_as_read(ctx)
                for t in lure_activity.recent_targets:
                    u.rovers[t.rover_id].targets[t.target_id].mark_viewed()

        # Running the lure check immediately should not process anything as last_accessed was just updated.
        user_activities = self._send_lure_alert(notified=0, processed=0)
        # Pass the lure threshold again, which should result in this user being processed, but no notification sent
        # as all lure activity was made done or viewed.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)
        user_activities = self._send_lure_alert(notified=0, processed=1)

    def test_lure_alerts_with_templating_all_activity_types(self):
        # Add a target and render it but do not advance so we have a known thumbnail URL.
        chips_result = self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        target_id = target['target_id']
        check_species_url = str(target['urls']['check_species'])
        self.render_next_target()

        # Advance to the arrival time of the target before identifying the species.
        self.advance_now(seconds=SIX_HOURS)

        # Identify a new species in this target so that there is unviewed species data to report in the lure email.
        self.check_species(check_species_url, [rects.SPC_PLANT001])

        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()

        # Now move past the lure window and there should be reportable activity.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)

        # Run the notifications tool with the real email sending callback, which in unit tests will
        # capture all sent emails, but the real templating will still occur.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_lure_alert_at(ctx, gametime.now(),
                                                             notifications.send_lure_alert_email_callback)
        self.assertEqual(processed, 1)
        self.assertEqual(len(self.get_sent_emails()), 1)
        email_body = self.get_sent_emails()[0].body_html
        self.assertTrue("[Extrasolar] Pending Tasks" in self.get_sent_emails()[0].subject)
        self.assertTrue("Hello, Testfirst" in email_body)
        # Verify that all of the data types we summarize in the lure email are in the body (ignore the counts as)
        # those might change as the story/initial user data changes during development.
        self.assertTrue("Active tasks:" in email_body)
        self.assertTrue("Unviewed messages:" in email_body)
        self.assertTrue("Unviewed species:" in email_body)
        self.assertTrue("Unviewed badges:" in email_body)
        # Verify the target_id (as part of ops URL) for the target being notified on is in the email.
        self.assertTrue(target_id in email_body)

        # Verify that running the process again at the next window sends no emails.
        self.clear_sent_emails()
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_lure_alert_at(ctx, gametime.now(),
                                                            notifications.send_lure_alert_email_callback)
        self.assertEqual(processed, 0)
        self.assertEqual(len(self.get_sent_emails()), 0)

    def test_unsubcribe_lure_alerts(self):
        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()

        # Now move past the lure window and there should be reportable activity.
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)
    
        # Run the notifications tool with the real email sending callback, which in unit tests will
        # capture all sent emails, but the real templating will still occur.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_lure_alert_at(ctx, gametime.now(),
                                                             notifications.send_lure_alert_email_callback)
        self.assertEqual(processed, 1)
        self.assertEqual(len(self.get_sent_emails()), 1)
        email_body = self.get_sent_emails()[0].body_html
        # Extract unsubscribe link from email_body and the link (we are not logged in right? be sure)
        unsubscribe_url = str(re.search(r'(%s)' % self.user.url_unsubscribe(), email_body).group(1))
    
        # Following this link should work without a valid authentication cookie.
        self.logout_user()
        response = self.app.get(unsubscribe_url)
        self.assertTrue("You have been unsubscribed" in response)

        # Log the user back in.
        self.login_user('testuser@example.com', 'pw')

        # Load the gamestate to update the last_accessed time to now.
        self.get_gamestate()
    
        # Verify that running the process again at the next window sends no emails.
        self.clear_sent_emails()
        self.advance_now(seconds=Constants.LURE_ALERT_WINDOW + 1)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = notifications.send_lure_alert_at(ctx, gametime.now(),
                                                             notifications.send_lure_alert_email_callback)
        self.assertEqual(processed, 0)
        self.assertEqual(len(self.get_sent_emails()), 0)

    def _send_lure_alert(self, at_time=None, notified=0, processed=0):
        if at_time is None:
            at_time = gametime.now()
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                capture = _CaptureUserActivity()
                count = notifications.send_lure_alert_at(ctx, at_time, capture)
        self.assertEqual(count, processed, "Unexpected number of users processed for activity.")
        self.assertEqual(len(capture.user_activities), notified, "Unexpected number of users notified for activity.")
        return capture.user_activities

class _CaptureUserActivity(object):
    def __init__(self):
        self.user_activities = []
    def __call__(self, ctx, user, user_activity, at_time):
        self.user_activities.append(user_activity)
