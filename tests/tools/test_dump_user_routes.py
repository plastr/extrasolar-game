# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import db, utils
from front.tools import dump_user_routes, replay_game

from front.tests import base
from front.tests.base import points

class TestDumpUserRoutes(base.TestCase):
    def setUp(self):
        super(TestDumpUserRoutes, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_dump_user_routes(self):
        user = self.get_logged_in_user()
        chip_result = self.create_target_and_move(**points.FIRST_MOVE)
        target_one = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)
        start_delay = utils.in_seconds(hours=4)
        arrival_delta = utils.in_seconds(hours=10)
        self.advance_now(seconds=start_delay)
        chip_result = self.create_target(arrival_delta=arrival_delta, **points.SECOND_MOVE)
        target_two = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)

        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                routes_by_rover, all_targets = dump_user_routes.targets_as_route_for_user_id(ctx, user.user_id)

        # Only one rover so far.
        self.assertEqual(len(routes_by_rover), 1)
        route = routes_by_rover[0][1]
        # Only two user created targets.
        self.assertEqual(route.num_points(), 2)
        points_iter = route.iterpoints()
        # The first points arrival_delta is going to be strange, since we create the initial
        # lander points and then some amount of time goes by before the user can create their
        # first target.
        point = points_iter.next()
        # However, the second point's arrival_delta should equal the amount we delayed before
        # creating it plus how long its travel time was.
        point = points_iter.next()
        self.assertEqual(point.arrival_delta, arrival_delta)
        self.assertEqual(point.start_delay, start_delay)

        # Pass the dumped route through replay_game and see if the data looks correct.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                tool = replay_game.ReplayGame(ctx, 'testuser_replay@example.com',
                                              route_structs=[route.to_struct()], verbose=False)
                tool.run()

        user = self.get_user_by_email('testuser_replay@example.com')
        rover = user.rovers.active()[0]

        # Verify that the start_time and arrival_time fields made the round trip intact.
        last_two_targets = rover.targets.by_arrival_time()[-2:]
        replay_target_one, replay_target_two = last_two_targets[0], last_two_targets[1]
        self._assert_targets_same_times(target_one, replay_target_one)
        self._assert_targets_same_times(target_two, replay_target_two)

    def _assert_targets_same_times(self, original, replay):
        # NOTE: Ideally we could verify lat==lat,lng==lng but loss of precision prevents this currently.
        self.assertEqual(original['start_time'], replay.start_time)
        self.assertEqual(original['arrival_time'], replay.arrival_time)
