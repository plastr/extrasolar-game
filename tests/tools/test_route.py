# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.debug import route as route_module
from front.debug.route import Route

from front.tests import base

TEST_ROUTE = [
    {"lat":6.239306025698268,"lng":-109.4133809260432,"yaw":0.1,"name":"FIRST_MOVE"},
    {"lat":6.239441334975075,"lng":-109.41393518133788,"yaw":0.1,"name":"NEXT_MOVE"},
    {"lat":6.239332015817533,"lng":-109.41436165257124,"yaw":0.1},
    {"lat":6.239076048920382,"lng":-109.414678153235,"yaw":0.1,"name":"AT_KEY_POINT","arrival_delta":28800}, # 6 hours
    {"lat":6.239494661385128,"lng":-109.41463792009978,"yaw":0.1},
    {"lat":6.239923938788315,"lng":-109.41462987347273,"yaw":0.1,"name":"DELAY_START"},
    {"lat":6.240339884259681,"lng":-109.41471033974318,"yaw":0.1,"name":"END_POINT","start_delay":7200}] # 2 hours

class TestRoute(base.TestCase):
    def test_route_create_and_move(self):
        route = Route.from_struct(TEST_ROUTE)
        # There is one overriden arrival_delta in the test route and one overriden start_delay.
        # The rest are the default values.
        self.assertEqual(route.duration(), 6*route_module.DEFAULT_ARRIVAL_DELTA + 28800 + 7200)
        self.assertEqual(route.duration_to_point("AT_KEY_POINT"), 3*route_module.DEFAULT_ARRIVAL_DELTA + 28800)

        # Verify the step_of_point system works.
        self.assertEqual(route.step_of_point("FIRST_MOVE"), 1)
        self.assertEqual(route.step_of_point("AT_KEY_POINT"), 4)
        self.assertEqual(route.step_of_point("END_POINT"), route.num_points())
        self.assertIsNone(route.step_of_point("NO_SUCH_POINT"), None)

        # Initial state.
        move_iter = route.move_iter()
        self.assertIsNone(move_iter.current_point())
        self.assertEqual(move_iter.next_point().name, "FIRST_MOVE")

        point = move_iter.move_forward()
        self.assertEqual(move_iter.current_point().name, "FIRST_MOVE")
        self.assertEqual(point.name, "FIRST_MOVE")
        self.assertEqual(move_iter.next_point().name, "NEXT_MOVE")

        points = move_iter.move_to_point("NEXT_MOVE")
        self.assertEqual(move_iter.current_point().name, "NEXT_MOVE")
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0].name, "NEXT_MOVE")
        self.assertIsNone(move_iter.next_point().name)

        points = move_iter.create_to_point("AT_KEY_POINT")
        self.assertEqual(len(points), 2)
        self.assertEqual(points[1].name, "AT_KEY_POINT")
        # Should not have moved.
        self.assertEqual(move_iter.current_point().name, "NEXT_MOVE")
        self.assertIsNone(move_iter.next_point().name)

        points = move_iter.move_to_point("AT_KEY_POINT")
        self.assertEqual(move_iter.current_point().name, "AT_KEY_POINT")
        self.assertEqual(len(points), 2)
        self.assertEqual(points[1].name, "AT_KEY_POINT")
        self.assertIsNone(move_iter.next_point().name)

        point = move_iter.create_next()
        # Should not have moved.
        self.assertEqual(move_iter.current_point().name, "AT_KEY_POINT")
        self.assertIsNone(point.name)
        self.assertIsNone(move_iter.next_point().name)

        # End state.
        move_iter.move_to_point("END_POINT")
        self.assertEqual(move_iter.current_point().name, "END_POINT")
        self.assertIsNone(move_iter.next_point())

        self.assertEqual(move_iter.move_forward(), None)
        # At the end of the line, any more movement ends iteration.
        self.assertRaises(StopIteration, move_iter.next)
        # At the end of the line, any more creation is an error.
        self.assertRaises(route_module.EndOfRoute, move_iter.create_next)

    def test_move_iteration(self):
        route = Route.from_struct(TEST_ROUTE)
        count = 0
        for point in route.move_iter():
            count += 1
        self.assertEqual(count, len(TEST_ROUTE))

        move_iter = route.move_iter()
        # Create the first two points without movement.
        move_iter.create_next()
        move_iter.create_next()
        count = 0
        for point in move_iter:
            count += 1
        self.assertEqual(count, len(TEST_ROUTE))

        # At the end of the line, any more creation is an error.
        self.assertRaises(route_module.EndOfRoute, move_iter.create_next)

    def test_delay_start_in_created_unmoved_error(self):
        # It is an error to have a delay_start > 0 for a point which is created but
        # not yet moved to.
        modified_route = [dict(p) for p in TEST_ROUTE]
        modified_route[1]['start_delay'] = 7200
        route = Route.from_struct(modified_route)
        move_iter = route.move_iter()
        move_iter.move_forward()
        move_iter.create_next()
        self.assertRaises(route_module.InvalidStartDelay, move_iter.create_next)

    # Test all of the movement methods from initial state as they have different code paths.
    def test_initial_states(self):
        move_iter = Route.from_struct(TEST_ROUTE).move_iter()
        point = move_iter.move_forward()
        self.assertEqual(point.name, "FIRST_MOVE")
        self.assertEqual(move_iter.next_point().name, "NEXT_MOVE")

        move_iter = Route.from_struct(TEST_ROUTE).move_iter()
        points = move_iter.move_to_point("FIRST_MOVE")
        self.assertEqual(points[0].name, "FIRST_MOVE")
        self.assertEqual(move_iter.next_point().name, "NEXT_MOVE")

        move_iter = Route.from_struct(TEST_ROUTE).move_iter()
        point = move_iter.create_next()
        self.assertEqual(point.name, "FIRST_MOVE")
        self.assertEqual(move_iter.next_point().name, "FIRST_MOVE")

        move_iter = Route.from_struct(TEST_ROUTE).move_iter()
        points = move_iter.create_to_point("FIRST_MOVE")
        self.assertEqual(points[0].name, "FIRST_MOVE")
        self.assertEqual(move_iter.next_point().name, "FIRST_MOVE")

    def test_relative_arrival_delta(self):
        class TrackDeltas(object):
            arrival_deltas = []
            def create_target_for_point(self, route, point, relative_arrival_delta):
                self.arrival_deltas.append(relative_arrival_delta)
            def clear(self):
                self.arrival_deltas = []
        route = Route.from_struct(TEST_ROUTE)
        track = TrackDeltas()
        move_iter = route.move_iter(delegate=track)

        # Test the initial case.
        move_iter.create_to_point("AT_KEY_POINT")
        self.assertEqual(len(track.arrival_deltas), 4)
        # Verify that each arrival_delta is greater than the previous one.
        for index in range(1, len(track.arrival_deltas)):
            self.assertTrue(track.arrival_deltas[index] > track.arrival_deltas[index - 1])

        # Test the normal case.
        move_iter.move_to_point("AT_KEY_POINT")
        track.clear()
        move_iter.create_to_point("END_POINT")
        self.assertEqual(len(track.arrival_deltas), 3)
        # Verify that each arrival_delta is greater than the previous one.
        for index in range(1, len(track.arrival_deltas)):
            self.assertTrue(track.arrival_deltas[index] > track.arrival_deltas[index - 1])

        # At the end of the line, any more creation allowed.
        self.assertRaises(route_module.EndOfRoute, move_iter.create_next)
