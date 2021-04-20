# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
from front.debug import route as route_module

class StoryBeatInterface(object):
    """
    An interface to document the various callbacks that a Beat in the story can receive.
    A Beat is a subclass (or class that conforms to this interface) where the name of the subclass
    matches a Point name in a Route known to the Story managing this Beat.
    e.g POINT_IN_STORY(StoryBeatInterface):
        @classmethod
        def moving_to_target(..)

    Standard arguments:
        delegate - The StoryDelegate provided to the Story managing this Beat. Intended to expose useful utilites.
        target - The Target instance. This is whatever is returned by a call to StoryDelegateInterface.target_for_point
                 and in some cases might be a an actual models.Target instance or might be deserialized JSON etc.
                 NOTE: The target might be None, if it was neutered or deleted for instance.
        point - The Point instance associated with this callback event.
    """
    @classmethod
    def create_next_targets(cls, delegate, target, point):
        """
        Return the number of targets that should be created ahead of this Beat upon arrival.
        This simulates the user creating multiple targets at a time on the map.
        """
        return 0

    @classmethod
    def waited_to_create_target(cls, delegate, target, point):
        """ Called if the Point for this Beat has a start_delay > 0, after the delay time is advanced. """

    @classmethod
    def created_target(cls, delegate, target, point):
        """ Called immediately after the target for this Beat was created. """
        pass

    @classmethod
    def moving_to_target(cls, delegate, target, point):
        """ Called immediately before starting to move to this Beat.
            Called AFTER any start_delay has elapsed."""
        pass

    @classmethod
    def moving_to_target_halfway(cls, delegate, target, point):
        """ Called at the halfway point (in terms of time) between this Beat and the previous one. """
        pass

    @classmethod
    def moved_to_target(cls, delegate, target, point):
        """ Called when the Story has arrived at this Beat. """
        pass

    @classmethod
    def leaving_target(cls, delegate, target, point):
        """ Called immediately before starting to move away from this Beat. """
        pass

    @classmethod
    def left_target(cls, delegate, target, point):
        """ Called after starting to move away from this Beat. """
        pass

    @classmethod
    def extra_duration(cls, delegate):
        """
        Optionally allow a Beat to add additional duration time to this Story.
        This is intended to be used by 'adhoc' beats implemented by specific implementations
        of Story specific Beat code (replay_game, story_case etc.)
        """
        return 0

class StoryDelegateInterface(object):
    """
    An interface to document the various callbacks that the delegate provided to a Story instance
    is expected to implement.
    Standard arguments:
        delegate - The StoryDelegate provided to the Story managing this Beat.
                   Intended to expose useful utilites to the Beat.
        target - The Target instance. This is whatever is returned by a call to
                 StoryDelegateInterface.target_for_point and in some cases might be a an
                 actual models.Target instance or might be deserialized JSON etc.
    """
    @classmethod
    def create_target_for_point(cls, point, relative_arrival_delta):
        """
        Create a Target object for this Point.
        It is expected that any target creation code that runs in this method
        will factor in any point.start_delay when creating the Target.
        relative_arrival_delta defaults to the Point.arrival_delta value but will have
        the sum of any created but not moved to Points duration values added if any exist.
        """
        pass

    @classmethod
    def target_for_point(cls, point):
        """
        Return the Target data for this Point. The returned value is passed to Beat callbacks.
        Return None to indicate that no callbacks should be dispatched, usually because the
        Target has been neutered or deleted for other reasons.
        """
        pass

    @classmethod
    def render_target(cls, target, point):
        """ Render this Target. Called halfway between this Beat and the previous one. """
        pass

    @classmethod
    def advanced_story_by(cls, seconds, point):
        """ Called when the Story moves between points, informing the delegate of the elapsed seconds.
            May be called multiple times when traveling between Points. This is where the delegate
            would run any deferred actions or adjust gametime. """
        pass

class StoryError(Exception):
    pass
class UnknownPointError(StoryError):
    pass
class DuplicatePointError(StoryError):
    pass

class Story(route_module.RouteDelegate):
    def __init__(self, route_structs, delegate, beats=[], fallback_beat=None):
        self._routes = [route_module.Route.from_struct(struct) for struct in route_structs]
        self._delegate = delegate
        self._beats = beats
        self._fallback_beat = fallback_beat

        # Validate that every point.name across all routes are unique. This is so that
        # calling play() with a to_point value doesn't have an unexpected result.
        point_names = set()
        for point in self._points_iter():
            if point.name is not None:
                if point.name in point_names:
                    raise DuplicatePointError("Point name duplicated in story route data [%s]" % point.name)
                point_names.add(point.name)

    def play(self, to_point=None):
        """ Playback this story, visiting either every point in every route and running any defined beats
            or only to a specific point name if to_point is provided. """
        if to_point is not None: self._assert_point_name_in_story(to_point)

        all_moved_to = []
        story_iter = Story.Iterator(self, self)
        # Move to each Point in the Story. Exit from the iteration after route_steps number of Points are moved to.
        for moved_to in story_iter:
            all_moved_to.append(moved_to)

            # If this beat requests that the next N number of targets in the Route should be created now
            # (as part of the user creating two targets at once for instance), do so now.
            create_next = self._beat_dispatch(moved_to, "create_next_targets", default=0)
            # Create all the future points requested.
            if create_next > 0:
                story_iter.create_ahead(create_next)

            # If we have arrived at the requested point, stop iterating.
            if to_point is not None and moved_to.name == to_point:
                break

        # Return all of the visited points as a list.
        return all_moved_to

    def duration(self):
        """ Return the total duration, in seconds, of every Route in this Story.
            NOTE: This includes any values returned by any Beats extra_duration method. """
        duration = sum(r.duration() for r in self._routes)
        # Factor in any extra duration time defined by any beat. Used for instance by adhoc beats with time delays.
        duration += sum(b.extra_duration(self._delegate) for b in self.beats_for_all_points())
        return duration

    def duration_to_point(self, point_name):
        """ Return the total duration, in seconds, from the start of the story to the given Point name.
            NOTE: This includes any values returned by any Beats extra_duration method that corrispond
            to any Point up till the given Point name."""
        self._assert_point_name_in_story(point_name)

        duration = 0
        for r in self._routes:
            step = r.step_of_point(point_name)
            if step is None:
                duration += r.duration()
            else:
                # The point is in this route, so get its duration and then stop counting.
                duration += r.duration_to_point(point_name)
                break
        # Factor in any extra duration time defined by any beat. Used for instance by adhoc beats with time delays.
        duration += sum(b.extra_duration(self._delegate) for b in self.beats_to_point(point_name))
        return duration

    def num_points(self):
        """ Return the total number of Points of every Route in this Story. """
        return sum(r.num_points() for r in self._routes)

    def named_points(self):
        return [point_name for r in self._routes for point_name in r.named_points()]

    def step_of_point(self, point_name):
        """ Returns the 'sequence step' of the given Point name, as an integer, in this Story. """
        total_steps = 0
        for r in self._routes:
            step = r.step_of_point(point_name)
            # If this point name is not in this route, assume it is in the next route
            # and add that routes total steps.
            if step is None:
                total_steps += r.num_points()
            # If the point name is in this route, then add its sequence step to the total
            # and return.
            else:
                total_steps += step
                return total_steps
        # Otherwise, the point is not in this route, return None.
        return None

    def beats_to_point(self, point_name):
        """ Return any Beats defined for all Points in this Story up to the supplied Point name.
            Optionally point_name can be None to get all defined Beats, see beats_for_all_points. """
        if point_name is not None: self._assert_point_name_in_story(point_name)

        beats = []
        # Iterate through every Point in the Story up till point_name (or all if point_name is None) and
        # track any Beat associated with all visited Points.
        for point in self._points_iter():
            if point.name is not None:
                beat_class = self._beat_for_point(point)
                # If a Beat was defined, track it.
                if beat_class is not None:
                    beats.append(beat_class)
            # If a specific Point name was listed as a stopping point and we have arrived there, then return
            # the found beats.
            if point_name is not None and point.name == point_name:
                return beats

        # Having reached the end of the Story, if we had no listed stopping Point, return all the Beats we found.
        if point_name is None:
            return beats

    def beats_for_all_points(self):
        """ Return all Beats defined for any Point in this Story. """
        return self.beats_to_point(point_name=None)

    ## Route delegate methods
    def create_target_for_point(self, route, point, relative_arrival_delta):
        # If the point has a start_delay then advance the story to that point.
        if point.start_delay > 0:
            self._delegate.advanced_story_by(seconds=point.start_delay, point=point)

        # Ask the story delegate to create the target.
        self._delegate.create_target_for_point(point, relative_arrival_delta)

        # If we advanced the game, inform the delegate after the target was created.
        if point.start_delay > 0:
            self._beat_dispatch(point, "waited_to_create_target")

    def created_point(self, route, point):
        self._beat_dispatch(point, "created_target")

    def moving_to_point(self, route, to_point, from_point):
        # moving_to_target is called AFTER any start_delay has elapsed.
        self._beat_dispatch(to_point, "moving_to_target")

        # Render the target for this point.
        target = self._delegate.target_for_point(to_point)
        # Target might be None if it has been neutered or deleted and therefore it
        # makes no sense to try and render it.
        if target is not None:
            self._delegate.render_target(target, point=to_point)

        # Determine the halfway mark in seconds between this point and the previous point.
        first_half = to_point.arrival_delta / 2
        remainder = to_point.arrival_delta % 2
        second_half = first_half + remainder
        assert (first_half + second_half) == to_point.arrival_delta

        # Inform any beats we are halfway and inform the delegate of the advancement of time.
        # This would be a good place to run any deferred actions simulating the deferred system running
        # halfway between two targets.
        # It would also be expected that gametime would be advanced by this callback.
        self._beat_dispatch(to_point, "moving_to_target_halfway")
        self._delegate.advanced_story_by(seconds=first_half, point=to_point)

        # This would be a good place to run any deferred actions simulating the deferred system running
        # again to catch any actions meant to be run in the second half of the time between the two points.
        # It would also be expected that gametime would be advanced by this callback.
        self._delegate.advanced_story_by(seconds=second_half, point=to_point)

    def moved_to_point(self, route, point):
        # Time was advanced in moving_to_target, targets were rendered and deferreds run.
        self._beat_dispatch(point, "moved_to_target")

    def leaving_point(self, route, point):
        self._beat_dispatch(point, "leaving_target")

    def left_point(self, route, point):
        self._beat_dispatch(point, "left_target")

    def _beat_dispatch(self, point, action, default=None, **kwargs):
        # If the point has a beat, dispatch the action to that beat.
        beat_class = self._beat_for_point(point)
        if beat_class is not None:
            return self._dispatch_action_to_class(point, action, beat_class, default, **kwargs)

        # If no beats matched the point (or it had no name) and a fallback_beat was defined, run
        # the action on that class now.
        if self._fallback_beat is not None:
            return self._dispatch_action_to_class(point, action, self._fallback_beat, default, **kwargs)

        # No beats matched, return the default.
        return default

    # Returns None if there is no beat class for this point.name. Does not return fallback_beats.
    def _beat_for_point(self, point):
        # If the point has no name then we have no way to lookup the beat so return None.
        if point.name is None:
            return None

        # If the point has a name, attempt to lookup the beat for that point name in each beat module in turn.
        # The first beat that implements a class matching the point name will be returned.
        for callback_module in self._beats:
            try:
                return getattr(callback_module, point.name)
            except AttributeError:
                continue
        # If no beat was found, return None indicating no beat found.
        return None

    def _dispatch_action_to_class(self, point, action, cls, default, **kwargs):
        try:
            callback_func = getattr(cls, action)
        except AttributeError:
            return default

        target = self._delegate.target_for_point(point)
        # NOTE: The target might be None, if it was neutered or deleted for instance.
        return callback_func(self._delegate, target, point, **kwargs)

    # Returns a new iterator object which will return each point in this story in turn
    # and will not perform any beat actions associated with those points (basically a read-only iterator)
    def _points_iter(self):
        # Create a no-op RouteDelegate which performs no actions as we move through the story.
        route_delegate = route_module.RouteDelegate()
        return Story.Iterator(self, route_delegate)

    def _assert_point_name_in_story(self, point_name):
        assert point_name is not None
        if self.step_of_point(point_name) is None:
            raise UnknownPointError("Point name is not in any route of story [%s]" % point_name)

    class Iterator(object):
        """ An iteration compatible object that yields the next move Point along the given Story, one
            at a time. Also provides a method to create targets beyond the current move. """
        def __init__(self, story, route_delegate):
            # Create movement iterators for all of the routes.
            self._route_iters = [r.move_iter(delegate=route_delegate) for r in story._routes]
            # Track which route movement iterator is being used for movement and which for creation.
            self._move_iter = 0
            self._create_iter = 0
            # Tracks how many targets past the current have been created but not moved to.
            self._created_ahead = 0

        # During this iteration, the consumer of an instance of this iterator
        # may call create_ahead with a count of the number of steps ahead to create.
        # NOTE: These steps are RELATIVE to the currently moved to point. In other words,
        # if at two consecutive points, A and B, create_next(2) is called, that means that two points
        # will be created ahead of A, and then the iterator will move to B, at which point only 1
        # additional point ahead will be created, since there is already 1 point ahead of B.
        # A -> B, B+1
        # B -> B+1 (already exists, not created), B+2
        def create_ahead(self, count):
            for i in range(0, (count - self._created_ahead)):
                self._route_create_iter.create_next()
                # Track how many points ahead have been created.
                self._created_ahead += 1

        ## Iteration protocol
        def __iter__(self):
            return self

        def next(self):
            moved_to = self._route_move_iter.move_forward()
            # If any targets have been created ahead of movement, then decrement the value
            # tracking that as this point has just been moved to.
            if self._created_ahead > 0:
                self._created_ahead -= 1
            return moved_to

        ## Route iterator accessors. Not intended for public use.
        @property
        def _route_move_iter(self):
            """ Points to the Route.MoveIter currently being used to the Story forward. """
            if self._route_iters[self._move_iter].next_point() is None:
                # Flush out the end of the route.
                self._route_iters[self._move_iter].move_forward()

                # Raises StopIteration if end of routes, stoping iteration for anything using
                # this MoveIter for an iteration.
                if self._move_iter + 1 == len(self._route_iters):
                    raise StopIteration
                # Move onto the next route for movement.
                self._move_iter += 1
                # Also move the create iterator forward (if it is behind) to keep up with movement.
                if self._create_iter < self._move_iter:
                    self._create_iter += 1
            return self._route_iters[self._move_iter]

        @property
        def _route_create_iter(self):
            """ Points to the Route.MoveIter currently being used to create targets for the Story. """
            if self._route_iters[self._create_iter].next_create_point() is None:
                # Running out of Routes for creation indicates an error in the source Route data, most
                # likely a Beat at the end of the Route that is requesting to create targets beyond
                # the end of the Story.
                if self._create_iter + 1 == len(self._route_iters):
                    raise Exception("End of all Story Routes reached, cannot create next point.")
                # Move onto the next route for creation.
                self._create_iter += 1
            assert self._create_iter >= self._move_iter
            return self._route_iters[self._create_iter]
