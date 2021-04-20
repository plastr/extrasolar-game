# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.backend import email_queue
from front.lib import db, email_module

from front.tests import base

class TestEmailQueue(base.TestCase):
    def test_enqueue_email_message(self):
        test_email = email_module.EmailMessage('fromuser@example.com', 'touser@example.com', 'Test Subject', 'Test Body pa\xd9\xad')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                # Add an email to the queue.
                email_queue.enqueue_email_message(ctx, test_email)
                self.assertEqual(len(self.get_sent_emails()), 0)
                # And then process the queue.
                processed = email_queue.process_email_queue(ctx)
                self.assertEqual(processed, 1)
                self.assertEqual(len(self.get_sent_emails()), 1)
                self.assertEqual(self.get_sent_emails()[0].email_from, test_email.email_from)
                self.assertEqual(self.get_sent_emails()[0].email_to, test_email.email_to)
                self.assertEqual(self.get_sent_emails()[0].subject, test_email.subject)
                self.assertEqual(self.get_sent_emails()[0].body_html, test_email.body_html)
                self.clear_sent_emails()

                # Should be no more work to do on the queue.
                processed = email_queue.process_email_queue(ctx)
                self.assertEqual(processed, 0)
                self.assertEqual(len(self.get_sent_emails()), 0)

    def test_email_module_queue_mode(self):
        self.create_user('testuser@example.com', 'pw', first_name="EmailUserFirst", last_name="EmailUserLast")

        # Put the email_module into queue dispatch mode.
        email_module.set_queue_dispatcher()

        # Send an email 'now' which will put it on the queue.
        self.assertEqual(len(self.get_sent_emails()), 0)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                email_module.send_now(ctx, user, 'EMAIL_TEST')
        self.assertEqual(len(self.get_sent_emails()), 0)

        # Now process the queue which should send the email.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = email_queue.process_email_queue(ctx)
                self.assertEqual(processed, 1)
                self.assertEqual(len(self.get_sent_emails()), 1)
                self.assertEqual(self.get_sent_emails()[0].email_from, '"Test Sender" <test@example.com>')
                self.assertEqual(self.get_sent_emails()[0].email_to, 'testuser@example.com')
                self.assertTrue("Test message" in self.get_sent_emails()[0].subject)
                self.assertTrue("Hello EmailUserFirst" in self.get_sent_emails()[0].body_html)
                self.clear_sent_emails()

                # Should be no more work to do on the queue.
                processed = email_queue.process_email_queue(ctx)
                self.assertEqual(processed, 0)
                self.assertEqual(len(self.get_sent_emails()), 0)

        # Sending an alarm however should bypass the queue.
        self.clear_sent_emails()
        self.assertEqual(len(self.get_sent_emails()), 0)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                email_module.send_alarm("toalarm@example.com", 'EMAIL_TEST_ALARM')
        self.assertEqual(len(self.get_sent_emails()), 1)
        self.assertEqual(self.get_sent_emails()[0].email_to, 'toalarm@example.com')
        self.assertTrue("Test message for an alarm" in self.get_sent_emails()[0].subject)

        # An alarm email should not end up in the queue,
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = email_queue.process_email_queue(ctx)
                self.assertEqual(processed, 0)

    def test_delivery_fail(self):
        self.create_user('testuser@example.com', 'pw')
        # Put the email_module into queue dispatch mode.
        email_module.set_queue_dispatcher()

        # Signal to the unit test base class to raise an exception when sending an email via email_ses.
        self._fail_email_delivery = True

        # Send an email 'now' which will put it on the queue.
        self.assertEqual(len(self.get_sent_emails()), 0)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                email_module.send_now(ctx, user, 'EMAIL_TEST')

        # Attempt to process the queue, which would log an exception and rollback.
        self.expect_log('front.backend.email_queue', '.*Sending queued email failed.*')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = email_queue.process_email_queue(ctx)
                # No email should have been processed because an exception should have occurred and rolled back the
                # transaction.
                self.assertEqual(processed, 0)
                self.assertEqual(len(self.get_sent_emails()), 0)

        # And now remove the exception raising.
        self._fail_email_delivery = False
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                processed = email_queue.process_email_queue(ctx)
                # Should now be able ot process the email on the queue.
                self.assertEqual(processed, 1)
                self.assertEqual(len(self.get_sent_emails()), 1)
