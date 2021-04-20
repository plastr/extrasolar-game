# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import datetime

from front.lib import db, utils
from front.tools import replay_game

from front.tests import base

NUM_STARTING_TARGETS_PER_ROVER = 1
NUM_INITIAL_PHOTOS = 4

class TestReplayGame(base.TestCase):
    def test_run_replay_game(self):
        # Snapshot the wallclock at the start of the test. The last targets arrival time should
        # be within a second or two of this time when the replay finishes.
        start_time = datetime.utcnow()

        from front.debug.stories import fastest_game_story
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                tool = replay_game.ReplayGame(ctx, 'testuser@example.com',
                                              route_structs=fastest_game_story.routes(),
                                              beats=fastest_game_story.beats(), verbose=False)
                tool.run()

        user = self.get_user_by_email('testuser@example.com')
        total_points = sum(len(r) for r in fastest_game_story.routes())
        total_targets = len([t for r in user.rovers.values() for t in r.targets])
        # Make sure we have the expected number of targets, taking neutered targets and
        # initial targets into account.
        NUM_ROVERS = 4
        NUM_NEUTERED_TARGETS = 2
        NUM_CUSTOM_TARGETS = 1  # Rover 2's final target out in the ocean.
        self.assertEqual(total_targets, total_points + NUM_INITIAL_PHOTOS + NUM_ROVERS*NUM_STARTING_TARGETS_PER_ROVER
            - NUM_NEUTERED_TARGETS + NUM_CUSTOM_TARGETS)

        # The last target should just have been arrived at relative to the actual wall clock. This is here to verify the
        # adhoc duration time counting is working (see extra_duration definition and usage)
        last_target_arrival_versus_now = utils.seconds_between_datetimes(user.all_picture_targets()[-1].arrival_time_date,
                                                                         start_time)
        self.assertTrue(abs(last_target_arrival_versus_now) <= 3)

        # Run the tool again to verify deletion of user data is working.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                tool = replay_game.ReplayGame(ctx, 'testuser@example.com',
                                              route_structs=fastest_game_story.routes(),
                                              beats=fastest_game_story.beats(), verbose=False)
                tool.run(no_prompt=True)

        user = self.get_user_by_email('testuser@example.com')
        self.assertEqual(total_targets, len([t for r in user.rovers.values() for t in r.targets]))

    def test_run_replay_game_to_point(self):
        # Snapshot the wallclock at the start of the test. The last targets arrival time should
        # be within a second or two of this time when the replay finishes.
        start_time = datetime.utcnow()

        from front.debug.stories import fastest_game_story
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                tool = replay_game.ReplayGame(ctx, 'testuser@example.com',
                                              route_structs=fastest_game_story.routes(),
                                              beats=fastest_game_story.beats(), verbose=False)
                # This should always go to a point which crosses a route boundary or two as well
                # as has some adhoc beats with time delta changes to exercise all that code.
                tool.run(to_point="SCI_FIND_COMMON_FIRST_TAGS")

        user = self.get_user_by_email('testuser@example.com')
        total_targets = len([t for r in user.rovers.values() for t in r.targets])
        total_points = tool._story.step_of_point('SCI_FIND_COMMON_FIRST_TAGS')
        # Make sure we have the expected number of targets, taking neutered targets and
        # initial targets into account.
        NUM_ROVERS = 4
        NUM_NEUTERED_TARGETS = 1
        self.assertEqual(total_targets, total_points + NUM_INITIAL_PHOTOS + NUM_ROVERS*NUM_STARTING_TARGETS_PER_ROVER - NUM_NEUTERED_TARGETS)

        # The last target should just have been arrived at relative to the actual wall clock. This is here to verify the
        # adhoc duration time counting is working (see extra_duration definition and usage)
        last_target_arrival_versus_now = utils.seconds_between_datetimes(user.all_picture_targets()[-1].arrival_time_date,
                                                                         start_time)
        self.assertTrue(abs(last_target_arrival_versus_now) <= 3)
