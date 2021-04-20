# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
from front.debug import route as route_module
from front.debug import story

from front.tests import base

EXTRA_DURATION = 3611
ARRIVAL_DELTA = 28800
START_DELAY = 7200

TEST_ROUTE1 = [
    {"lat":1.0,"lng":-1.0,"yaw":0.1,"name":"FIRST_MOVE"},
    {"lat":2.0,"lng":-2.0,"yaw":0.1,"name":"SECOND_MOVE"}] # Create next two
TEST_ROUTE2 = [
    {"lat":3.0,"lng":-3.0,"yaw":0.1,"name":"THIRD_MOVE"},  # Create next two
    {"lat":4.0,"lng":-4.0,"yaw":0.1,"name":"FOURTH_POINT","arrival_delta":ARRIVAL_DELTA},
    {"lat":5.0,"lng":-5.0,"yaw":0.1,"name":"FIFTH_POINT"},
    {"lat":6.0,"lng":-6.0,"yaw":0.1,"name":"SIXTH_POINT","start_delay":START_DELAY}, # 2 hours
    {"lat":7.0,"lng":-7.0,"yaw":0.1}]
# Contains a duplicate point name from TEST_ROUTE1
TEST_ROUTE_DUPLICATE = [
    {"lat":8.0,"lng":-8.0,"yaw":0.1,"name":"FIRST_MOVE"}
]


class TestStory(base.TestCase):
    def test_story_full_play(self):
        delegate = TestStoryDelegate(self)
        test_story = story.Story(route_structs=[TEST_ROUTE1, TEST_ROUTE2],
                                 delegate=delegate,
                                 beats=[StoryBeats],
                                 fallback_beat=StoryBeatsFallbackTest)
        test_story.play()

        # The story should have created all the points in all the routes.
        total_points = len(TEST_ROUTE1) + len(TEST_ROUTE2)
        self.assertEqual(len(delegate.CREATED_TARGETS), total_points)
        self.assertEqual(len(delegate.MOVED_TO_TARGETS), total_points)
        self.assertEqual(len(delegate.LEAVING_TARGETS), total_points)
        self.assertEqual(len(delegate.LEFT_TARGETS), total_points)
        # And one point should have waited for the start_delay
        self.assertTrue(delegate.WAITED)

        # There is one overriden arrival_delta and one start_delay in the test route.
        # The rest are the default values.
        # NOTE: The fifth point adds EXTRA_DURATION to the duration, emulating an adhoc beat.
        self.assertEqual(test_story.duration(), 6*route_module.DEFAULT_ARRIVAL_DELTA + ARRIVAL_DELTA + START_DELAY + EXTRA_DURATION )
        # Did not reach the EXTRA_DURATION beat so don't factor that in.
        self.assertEqual(test_story.duration_to_point("FOURTH_POINT"), 3*route_module.DEFAULT_ARRIVAL_DELTA + ARRIVAL_DELTA)
        # Should have reached the EXTRA_DURATION beat so factor that in.
        self.assertEqual(test_story.duration_to_point("FIFTH_POINT"), 4*route_module.DEFAULT_ARRIVAL_DELTA + ARRIVAL_DELTA + EXTRA_DURATION)

    def test_story_to_point(self):
        delegate = TestStoryDelegate(self)
        test_story = story.Story(route_structs=[TEST_ROUTE1, TEST_ROUTE2],
                                 delegate=delegate,
                                 beats=[StoryBeats],
                                 fallback_beat=StoryBeatsFallbackTest)
        test_story.play(to_point="SECOND_MOVE")

        total_points = 2
        # Two targets created at SECOND_MOVE but not moved to.
        self.assertEqual(len(delegate.CREATED_TARGETS), total_points + 2)
        self.assertEqual(len(delegate.MOVED_TO_TARGETS), total_points)
        # If to_point is used, the leaving/left events are not fired for the last point.
        self.assertEqual(len(delegate.LEAVING_TARGETS), total_points - 1)
        self.assertEqual(len(delegate.LEFT_TARGETS), total_points - 1)

    def test_story_unknown_point_name(self):
        delegate = TestStoryDelegate(self)
        test_story = story.Story(route_structs=[TEST_ROUTE1, TEST_ROUTE2],
                                 delegate=delegate)
        self.assertRaises(story.UnknownPointError, test_story.play, to_point="UNKNOWN_POINT")

    def test_story_duplicate_point_name(self):
        delegate = TestStoryDelegate(self)
        self.assertRaises(story.DuplicatePointError, story.Story,
                          route_structs=[TEST_ROUTE1, TEST_ROUTE_DUPLICATE], delegate=delegate)

class TestStoryDelegate(story.StoryDelegateInterface):
    def __init__(self, test):
        self.TEST = test
        self.CREATED_TARGETS = []
        self.MOVED_TO_TARGETS = []
        self.LEAVING_TARGETS = []
        self.LEFT_TARGETS = []
        self.WAITED = False

    def create_target_for_point(self, point, relative_arrival_delta):
        self.CREATED_TARGETS.append(point)

    def target_for_point(self, point):
        return {'target_id': 'BOGUS'}

# A simple beat base class which counts certain events.
class TestStoryBeat(story.StoryBeatInterface):
    @classmethod
    def leaving_target(cls, delegate, target, point):
        delegate.LEAVING_TARGETS.append(point)

    @classmethod
    def left_target(cls, delegate, target, point):
        delegate.LEFT_TARGETS.append(point)

class StoryBeats(object):
    class FIRST_MOVE(TestStoryBeat):
        @classmethod
        def moved_to_target(cls, delegate, target, point):
            delegate.MOVED_TO_TARGETS.append(point)
            delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 1)

    # Signal that the next two targets should be created past this one.
    class SECOND_MOVE(TestStoryBeat):
        @classmethod
        def create_next_targets(cls, delegate, target, point):
            return 2

        @classmethod
        def moved_to_target(cls, delegate, target, point):
            delegate.MOVED_TO_TARGETS.append(point)
            delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 2)

    # Signal that the next two targets should be created past this one. That really means that only
    # one additional target should be created past what has already been created since the previous
    # point already indicated that the two past it should be created.
    class THIRD_MOVE(TestStoryBeat):
        @classmethod
        def create_next_targets(cls, delegate, target, point):
            return 2

        @classmethod
        def moved_to_target(cls, delegate, target, point):
            delegate.MOVED_TO_TARGETS.append(point)
            delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 4)

    class FOURTH_POINT(TestStoryBeat):
        @classmethod
        def moved_to_target(cls, delegate, target, point):
            delegate.MOVED_TO_TARGETS.append(point)
            delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 5)

    class FIFTH_POINT(TestStoryBeat):
        @classmethod
        def moved_to_target(cls, delegate, target, point):
            delegate.MOVED_TO_TARGETS.append(point)
            delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 5)

        # Emulate an 'adhoc beat' by adding some start or arrival time delay to the duration
        # to test that handling.
        @classmethod
        def extra_duration(cls, delegate):
            return EXTRA_DURATION

    class SIXTH_POINT(TestStoryBeat):
        @classmethod
        def waited_to_create_target(cls, delegate, target, point):
            delegate.WAITED = True

        @classmethod
        def moved_to_target(cls, delegate, target, point):
            delegate.MOVED_TO_TARGETS.append(point)
            delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 6)

class StoryBeatsFallbackTest(TestStoryBeat):
    @classmethod
    def moved_to_target(cls, delegate, target, point):
        delegate.MOVED_TO_TARGETS.append(point)
        delegate.TEST.assertEqual(len(delegate.CREATED_TARGETS), 7)
