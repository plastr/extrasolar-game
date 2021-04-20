# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.backend import deferred
from front.lib import db, utils
from front.callbacks import timer_callbacks

from front.tests import base

class TestDeferred(base.TestCase):
    def test_deferred_timer(self):
        class TMR_TEST01_Callbacks(timer_callbacks.BaseCallbacks):
            TIMER_FIRED = False
            @classmethod
            def timer_arrived_at(cls, ctx, user):
                cls.TIMER_FIRED = True
        self.inject_callback(timer_callbacks, TMR_TEST01_Callbacks)

        self.create_user('testuser@example.com', 'pw')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_user_by_email('testuser@example.com', ctx=ctx)
                deferred.run_on_timer(ctx, 'TMR_TEST01', user, delay=utils.in_seconds(minutes=30))
                # Make sure the timer does not fire before its time.
                processed = self.advance_game_for_user(user, minutes=29)
                self.assertEqual(len(processed), 0)
                self.assertFalse(TMR_TEST01_Callbacks.TIMER_FIRED)
                # Now jump to the timer firing time.
                processed = self.advance_game_for_user(user, minutes=1)
                self.assertEqual(len(processed), 1)
                self.assertTrue(TMR_TEST01_Callbacks.TIMER_FIRED)

    def test_deferred_timer_with_args(self):
        class TMR_TEST02_Callbacks(timer_callbacks.BaseCallbacks):
            TIMER_FIRED = False
            ARG = None
            @classmethod
            def timer_arrived_at(cls, ctx, user, arg):
                cls.TIMER_FIRED = True
                cls.ARG = arg
        self.inject_callback(timer_callbacks, TMR_TEST02_Callbacks)

        self.create_user('testuser@example.com', 'pw')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_user_by_email('testuser@example.com', ctx=ctx)
                deferred.run_on_timer(ctx, 'TMR_TEST02', user, delay=utils.in_seconds(minutes=30), arg="Hello")
                # Make sure the timer does not fire before its time.
                processed = self.advance_game_for_user(user, minutes=29)
                self.assertEqual(len(processed), 0)
                self.assertFalse(TMR_TEST02_Callbacks.TIMER_FIRED)
                self.assertEqual(TMR_TEST02_Callbacks.ARG, None)
                # Now jump to the timer firing time.
                processed = self.advance_game_for_user(user, minutes=1)
                self.assertEqual(len(processed), 1)
                self.assertTrue(TMR_TEST02_Callbacks.TIMER_FIRED)
                self.assertEqual(TMR_TEST02_Callbacks.ARG, "Hello")

    def test_deferred_run_later_negative_delay(self):
        class TMR_TEST01_Callbacks(timer_callbacks.BaseCallbacks):
            TIMER_FIRED = False
            @classmethod
            def timer_arrived_at(cls, ctx, user):
                cls.TIMER_FIRED = True
        self.inject_callback(timer_callbacks, TMR_TEST01_Callbacks)

        # Attempting to use deferred run_later with a negative delay value should result in a log warning
        # and the delay time being set to 0 (now).
        self.expect_log('front.backend.deferred', 'Refusing to run later a deferred with a negative delay time')

        self.create_user('testuser@example.com', 'pw')
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_user_by_email('testuser@example.com', ctx=ctx)
                # NOTE: run_on_timer calls through to run_later
                deferred.run_on_timer(ctx, 'TMR_TEST01', user, delay=-3600)
                # The deferred action should run immediatly.
                processed = self.advance_game_for_user(user, seconds=0)
                self.assertEqual(len(processed), 1)
                self.assertTrue(TMR_TEST01_Callbacks.TIMER_FIRED)
