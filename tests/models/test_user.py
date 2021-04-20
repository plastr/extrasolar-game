# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import debug
from front.lib import db
from front.tools import replay_game

from front.tests import base
from front.tests.base import PRODUCT_KEY_S1_GIFT

class TestUser(base.TestCase):
    # NOTE: Currently there is not a formal mechanism to delete a user, so this test exercises the
    # debug mechanism, eventually there will be a user.delete() or similar method which this test will exercise.
    def test_delete_user(self):
        # Verify that the lists of deletion tables are up-to-date with the actual schema.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                all_current_tables = set(debug.list_all_db_tables(ctx))
                if all_current_tables != debug.DELETE_KNOWN_TABLES:
                    stale = debug.DELETE_KNOWN_TABLES.difference(all_current_tables)
                    unhandled = all_current_tables.difference(debug.DELETE_KNOWN_TABLES)
                    stale_and_unhandled = stale.union(unhandled)
                    raise Exception("Unhandled or stale table during user data deletion %s" % stale_and_unhandled)

        # Use replay game to insert a bunch of user data to delete.
        from front.debug.stories import fastest_game_story
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                tool = replay_game.ReplayGame(ctx, 'testuser@example.com',
                                              route_structs=fastest_game_story.routes(),
                                              beats=fastest_game_story.beats(), verbose=False)
                tool.run()
                user_id = self.get_user_by_email('testuser@example.com', ctx=ctx).user_id

        self.login_user('testuser@example.com', replay_game.TEST_PASSWORD)
        # Load the entire gamestate with validation enabled after replaying the full game to make sure it looks right.
        self.get_gamestate(skip_validation=False)
        # Purchase a gift and send an invitation to be sure these tables are cleared as well.
        self.set_user_invites_left(1)
        self.purchase_gift(PRODUCT_KEY_S1_GIFT)
        self.logout_user()

        # Now delete the user.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                debug.delete_user_and_data(ctx, user_id, include_user_table=True)

        # And perform a select * from every table in the actual schema except those listed in DELETE_IGNORE_TABLES
        # and make sure those tables are empty.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                for t in all_current_tables:
                    if t in debug.DELETE_IGNORE_TABLES:
                        continue
                    # Table name can't be escaped as the named query would normally do.
                    rows = db._run_query_string(ctx, "SELECT * FROM %s" % t)
                    self.assertEqual(len(rows), 0, "Deleting user left stale data in %s table." % t)
