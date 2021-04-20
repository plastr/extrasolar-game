# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import difflib

from front.tests import base
from front.tests.base import points

from front.lib import db
from front.callbacks import target_callbacks
from front.tools import apply_migrations, extract_schema

class TestDB(base.TestCase):
    def setUp(self):
        super(TestDB, self).setUp()

    def test_row_and_run(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, 'test/create_test_table')
                # Perform the select query with no rows.
                self.assertRaises(db.UnexpectedResultError, db.run, ctx, 'test/select_test_rows')
                self.assertRaises(db.TooFewRowsError, db.row, ctx, 'test/select_test_rows')
                rows = db.rows(ctx, 'test/select_test_rows')
                self.assertEqual(len(rows), 0)

                # Add a single row.
                db.run(ctx, 'test/insert_test_row', test_field=0)
                # Perform the query with one row.
                self.assertRaises(db.UnexpectedResultError, db.run, ctx, 'test/select_test_rows')
                row = db.row(ctx, 'test/select_test_rows')
                self.assertEqual(len(row), 1)
                rows = db.rows(ctx, 'test/select_test_rows')
                self.assertEqual(len(rows), 1)

                # Add a second row.
                db.run(ctx, 'test/insert_test_row', test_field=1)
                self.assertRaises(db.UnexpectedResultError, db.run, ctx, 'test/select_test_rows')
                self.assertRaises(db.TooManyRowsError, db.row, ctx, 'test/select_test_rows')
                rows = db.rows(ctx, 'test/select_test_rows')
                self.assertEqual(len(rows), 2)

                # Running row or rows on an INSERT or similar should raise an error, but the data
                # is still inserted.
                self.assertRaises(db.UnexpectedResultError, db.row, ctx, 'test/insert_test_row',  test_field=2)
                self.assertRaises(db.UnexpectedResultError, db.rows, ctx, 'test/insert_test_row',  test_field=3)
                rows = db.rows(ctx, 'test/select_test_rows')
                self.assertEqual(len(rows), 4)

                # Cleanup the test database.
                db.run(ctx, 'test/drop_test_table')

    def test_row_cache(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, 'test/create_test_table')
                # Verify the cache is empty by default.
                rows = db.rows(ctx, 'test/select_test_rows_by_test_field', test_field=42)
                self.assertEqual(len(rows), 0)
                rows = ctx.row_cache.get_rows_from_query('test/select_test_rows_by_test_field', 42)
                self.assertIsNone(rows)

                # Insert some data.
                db.run(ctx, 'test/insert_test_row', test_field=42)
                rows = db.rows(ctx, 'test/select_test_rows_by_test_field', test_field=42)
                self.assertEqual(len(rows), 1)
                # Still not in the cache.
                rows = ctx.row_cache.get_rows_from_query('test/select_test_rows_by_test_field', 42)
                self.assertIsNone(rows)
                # Now insert the rows into the cache.
                rows = db.rows(ctx, 'test/select_test_rows_by_test_field', test_field=42)
                ctx.row_cache.set_rows_from_query(ctx, lambda r: [r['test_field']],
                                                  "test/select_test_rows_by_test_field", test_field=42)
                # Data should now be in the cache.
                rows = ctx.row_cache.get_rows_from_query('test/select_test_rows_by_test_field', 42)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['test_field'], 42)

                # Attempting to insert the same data back into the cache should log a warning.
                self.expect_log('front.lib.db', 'Row caching query data that was already cached.*')
                ctx.row_cache.set_rows_from_query(ctx, lambda r: [r['test_field']],
                                                  "test/select_test_rows_by_test_field", test_field=42)

                # And test that using the row cache with queries with no arguments also works.
                rows = db.rows(ctx, 'test/select_test_rows')
                self.assertEqual(len(rows), 1)
                rows = ctx.row_cache.get_rows_from_query('test/select_test_rows')
                self.assertIsNone(rows)
                ctx.row_cache.set_rows_from_query(ctx, lambda r: [], 'test/select_test_rows')
                rows = ctx.row_cache.get_rows_from_query('test/select_test_rows')
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]['test_field'], 42)

                # Cleanup the test database.
                db.run(ctx, 'test/drop_test_table')

    def test_database_middleware(self):
        # Insert code into the default target_created callback behavior which can optionally
        # raise a known exception. This will be used to test the middleware.
        class MiddlewareTestError(Exception): pass
        RAISE_EXCEPTION = False
        class MiddlwareTest_Callbacks(target_callbacks.BaseCallbacks):
            @classmethod
            def target_created(cls, ctx, user, target):
                if RAISE_EXCEPTION:
                    raise MiddlewareTestError
        self.inject_callback(target_callbacks, MiddlwareTest_Callbacks)

        self.create_user('testuser@example.com', 'pw')
        count = self._target_count_in_db()
        self.create_target(**points.FIRST_MOVE)
        # Creating a target should increase the number of targets by one.
        self.assertEqual(self._target_count_in_db(), count + 1)

        self.advance_now(hours=6)
        count = self._target_count_in_db()
        # Attempt to create a target with the base target_created callbacks always raising an exception.
        # The DatabaseMiddleware wrapper should rollback all DB connections.
        RAISE_EXCEPTION = True
        self.assertRaises(MiddlewareTestError, self.create_target, **points.SECOND_MOVE)
        RAISE_EXCEPTION = False
        # The number of targets before the exception should be the same afterwards.
        self.assertEqual(self._target_count_in_db(), count)

    def test_commit_or_rollback(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, 'test/create_test_table')

        # If there are no exceptions, the connection should commit.
        count = self._test_rows_count_in_db()
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, 'test/insert_test_row', test_field=0)
        self._assert_test_row_count_in_db(count + 1)

        # If there is an exception, the connection should rollback and no changes should be applied.
        count = self._test_rows_count_in_db()
        raised = False
        try:
            with db.commit_or_rollback(self.get_ctx()) as ctx:
                with db.conn(ctx) as ctx:
                    db.run(ctx, 'test/insert_test_row', test_field=1)
                    raise Exception("Test failure.")
        except:
            raised = True
        self.assert_(raised)
        self._assert_test_row_count_in_db(count)

        # Calling db.commit within a commit_or_rollback block should commit everything
        # up till that point. Subsequent exceptions should still rollback new changes.
        count = self._test_rows_count_in_db()
        raised = False
        try:
            with db.commit_or_rollback(self.get_ctx()) as ctx:
                with db.conn(ctx) as ctx:
                    for row_name in ["first", "second"]:
                        # The first row should insert and commit
                        db.run(ctx, 'test/insert_test_row', test_field=2)
                        # The second row should failed before the commit.
                        if row_name is "second":
                            raise Exception("Test failure.")
                        db.commit(ctx)
        except:
            raised = True
        self.assert_(raised)
        # Two message inserts were attempted, but the second failed before the commit, so only
        # one message should have been inserted.
        self._assert_test_row_count_in_db(count + 1)

        # Cleanup the test database.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                db.run(ctx, 'test/drop_test_table')

    def test_migrations(self):
        TEST_DB = 'test_migrations_db'

        # Get a fresh configuration dictionary and change the testing database
        # to be a name specific for this test.
        conf = self.get_ctx()
        conf['database.name'] = TEST_DB
        try:
            # Create a blank database and then apply all of the migrations and roll them all back.
            db.create_database(conf, apply_schema=False)
            apply_migrations.run_migrations(conf, action='apply', no_prompt=True, verbose=False)
            # Should have more than just the _yoyo_migrations table.
            self.assertTrue(len(db.list_tables(conf)) > 2)

            # Grab the live db schema using the extract_schema tool.
            live_schema = extract_schema.extract(TEST_DB)
            # And load the schema file that is saved to disk/in source control
            file_schema = db._schema()

            # And now 'diff' those two schema strings.
            diff = "".join((l for l in difflib.context_diff(live_schema.splitlines(True), file_schema.splitlines(True))))
            if len(diff) > 0:
                print diff
                self.fail("The migrated schema and the schema.sql file are different, migrations out of sync?")

            # The yoyo migration connection is not under our control so it is not in SQL TRADITIONAL mode
            # e.g. strict mode so we will perform an adhoc migration on the fully migrated database
            # in strict mode which will raise an exception if the schema is not strict compliant.
            with db.commit_or_rollback(conf) as ctx:
                with db.conn(ctx) as ctx:
                    db._run_query_string(ctx, 'ALTER TABLE users ADD COLUMN _test_sentinal int NOT NULL')
                    db._run_query_string(ctx, 'ALTER TABLE users DROP COLUMN _test_sentinal')

                # Now roll all the migrations back to make sure they perform correctly and
                # verify we hit the baseline migration which raises an exception if rolled back.
                hit_baseline_migration = False
                try:
                    apply_migrations.run_migrations(conf, action='rollback', no_prompt=True, verbose=False)
                except Exception, e:
                    hit_baseline_migration = True
                    self.assertEqual(str(e), "Cannot rollback the baseline migration.")
                self.assertTrue(hit_baseline_migration)

                # Verify only a baseline migration is left.
                with db.conn(ctx) as ctx:
                    rows = db._run_query_string(ctx, 'SELECT * from _yoyo_migration')
                    self.assertEqual(len(rows), 1)
                    self.assertTrue('baseline' in rows[0]['id'])
        # No matter what happens be sure we delete the test specific database.
        finally:
            db.destroy_database(conf)

    def _target_count_in_db(self):
        return len(self.get_targets_from_gamestate(self.get_gamestate()))

    def _test_rows_count_in_db(self):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                return len(db.rows(ctx, 'test/select_test_rows'))

    def _assert_test_row_count_in_db(self, count):
        current_count = self._test_rows_count_in_db()
        self.assertEqual(current_count, count)
