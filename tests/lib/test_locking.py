# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base

from front.lib import db, locking
from front.lib.locking import acquire_db_lock, acquire_db_lock_if_unlocked

class TestLocking(base.TestCase):
    def test_acquire_db_lock(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with acquire_db_lock(ctx, 'TEST_LOCK', 10):
                self.assertFalse(locking.is_lock_free(ctx, 'TEST_LOCK'))
            # Should unlock outside of context.
            self.assertTrue(locking.is_lock_free(ctx, 'TEST_LOCK'))

    def test_acquire_db_lock_with_exception(self):
        raised = False
        try:
            with db.commit_or_rollback(self.get_ctx()) as ctx:
                with acquire_db_lock(ctx, 'TEST_LOCK', 10):
                    self.assertFalse(locking.is_lock_free(ctx, 'TEST_LOCK'))
                    raise Exception("Testing locking with exception")
        except:
            raised = True
        self.assert_(raised)
        # Should unlock outside of context.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            self.assertTrue(locking.is_lock_free(ctx, 'TEST_LOCK'))

    def test_acquire_db_lock_timed_out(self):
        raised = False
        try:
            with db.commit_or_rollback(self.get_ctx()) as ctx:
                with acquire_db_lock(ctx, 'TEST_LOCK', 10):
                    # Run commit_or_rollback again with a new context/connection to simulate another
                    # process attempting to acquire this lock.
                    with db.commit_or_rollback(self.get_ctx()) as ctx:
                        with acquire_db_lock(ctx, 'TEST_LOCK', 1):
                            self.fail("This line should not execute.")
        except locking.LockTimeoutError:
            raised = True
        self.assert_(raised)
        # Should unlock outside of context.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            self.assertTrue(locking.is_lock_free(ctx, 'TEST_LOCK'))

    def test_acquire_db_lock_if_unlocked(self):
        raised = False
        # Track all of the blocks of code expected to execute.
        expected_blocks = 0
        try:
            with db.commit_or_rollback(self.get_ctx()) as outer_ctx:
                with acquire_db_lock(outer_ctx, 'TEST_LOCK', 10):
                    # Run commit_or_rollback again with a new context/connection to simulate another
                    # process attempting to acquire this lock.
                    with db.commit_or_rollback(self.get_ctx()) as inner_ctx:
                        try:
                            with acquire_db_lock_if_unlocked(inner_ctx, 'TEST_LOCK', 1):
                                self.fail("This line should not execute.")
                        except locking.LockAlreadyLocked:
                            expected_blocks += 1
                    # The lock should still be held by the outer context.
                    self.assertFalse(locking.is_lock_free(outer_ctx, 'TEST_LOCK'))
                    expected_blocks += 1
                expected_blocks += 1
                # Should still unlock outside of outer context.
                self.assertTrue(locking.is_lock_free(outer_ctx, 'TEST_LOCK'))
        except locking.LockTimeoutError:
            # The inner lock should not timeout, instead silently return.
            raised = True
        self.assertFalse(raised)
        self.assertEqual(expected_blocks, 3)
