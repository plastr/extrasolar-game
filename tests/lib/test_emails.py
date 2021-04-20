# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

from front.lib import db, utils, email_module
from front.tests import base

class TestEmails(base.TestCase):
    def setUp(self):
        super(TestEmails, self).setUp()
        self.create_user('testuser@example.com', 'pw', first_name="EmailUserFirst", last_name="EmailUserLast")

    def test_send_now(self):
        user = self.get_logged_in_user()
        # Send an email now.
        self.assertEqual(len(self.get_sent_emails()), 0)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                email_module.send_now(ctx, user, 'EMAIL_TEST')
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertTrue("Test message" in self.get_sent_emails()[0].subject)
        self.assertTrue("Hello EmailUserFirst" in self.get_sent_emails()[0].body_html)

    def test_send_later(self):
        user = self.get_logged_in_user()
        # Send an email a few seconds in the future.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                email_module.send_later(ctx, user, 'EMAIL_TEST', utils.in_seconds(seconds=30))

        self.assertEqual(len(self.get_sent_emails()), 0)
        self.advance_game_for_user(user, seconds=60)
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertTrue("Test message" in self.get_sent_emails()[0].subject)
        self.assertTrue("Hello EmailUserFirst" in self.get_sent_emails()[0].body_html)

    def test_send_alarm(self):
        # Send an alarm email now.
        self.assertEqual(len(self.get_sent_emails()), 0)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                email_module.send_alarm("toalarm@example.com", 'EMAIL_TEST_ALARM')
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertEqual(self.get_sent_emails()[0].email_to, 'toalarm@example.com')
        self.assertTrue("Test message for an alarm" in self.get_sent_emails()[0].subject)
