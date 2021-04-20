# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

class RouteDelegate(object):
    """ The interface for the Route delegate object. This classmethod style can be used or any object
        instance which implements any subset of these methods will also work. """
    @classmethod
    def create_target_for_point(cls, route, point, relative_arrival_delta):
        """
        This method is where the subclass or delegate should actually create the Target.
        It is expected that any target creation code that runs in this method
        will factor in any point.start_delay when creating the Target.
        relative_arrival_delta defaults to the Point.arrival_delta value but will have
        the sum of any created but not moved to Points duration values added if any exist.
        """
        pass

    @classmethod
    def created_point(cls, route, point):
        """ The Route has just created a Target for this Point. """
        pass

    @classmethod
    def moving_to_point(cls, route, to_point, from_point):
        """
        The Route is just about to move to the Point to_point from from_point.
        Called after this Target has been created.
        """
        pass

    @classmethod
    def moved_to_point(cls, route, point):
        """ The Route has arrived at this Point. """
        pass

    @classmethod
    def leaving_point(cls, route, point):
        """
        The Route is just about to move away from this Point.
        Called after the next Target has been created.
        """
        pass

    @classmethod
    def left_point(cls, route, point):
        """
        The Route has left this point and arrived at the next point. Called before moved_to_point.
        """
        pass

class RouteError(Exception):
    pass

class UnknownPointError(RouteError):
    pass

class EndOfRoute(RouteError):
    pass

class InvalidStartDelay(RouteError):
    pass

# If no arrival_delta is set for a Point, it will have this value, in seconds.
DEFAULT_ARRIVAL_DELTA = 21600 # 6 hours in seconds.

# If no start_delay is set for a Point, it will have this value, in seconds.
DEFAULT_START_DELAY = 0 # 0 seconds.

class Point(object):
    """
    This class holds information which describes a point in time and space on a Route.

    :param lat, lng: float The latitude and longitude of this point.
    :param yaw: float The yaw (direction faced) of this point. Optional field.
    :param name: str A unique name (key) to identify this point in the Route. Optional field. Defaults to None.
    :param arrival_delta: int The number of seconds, relative to the previous point, that this point
        should be arrived at by the Route. Optional field. Defaults to DEFAULT_ARRIVAL_DELTA.
    :param start_delay: int The number of seconds to delay before starting towards this point.
        Optional field. Defaults to DEFAULT_START_DELAY.
    :param identified: list A list of species_key names for the species which should be/were identified
        at this Point in the Route. Optional field. Defaults to [].
    """
    def __init__(self, lat, lng, yaw=0.0, name=None,
                       arrival_delta=DEFAULT_ARRIVAL_DELTA, start_delay=DEFAULT_START_DELAY,
                       identified=[]):
        self.lat = lat
        self.lng = lng
        self.yaw = yaw
        self.name = name
        self.arrival_delta = arrival_delta
        self.start_delay = start_delay
        self.identified = identified

    # The 'struct' is expected to be an Python dict, as converted potentially from JSON.
    # The fields are {lat, lng, yaw, name, arrival_delta, identified}
    # name, arrival_delta and identified might be absent.
    @classmethod
    def from_struct(cls, struct):
        assert struct.get('lat') != None
        assert struct.get('lng') != None
        assert struct.get('yaw') != None
        return cls(**struct)

    def duration(self):
        """
        Returns the total number of seconds elapsed in the route for this point.
        e.g. How long the route waits at each point plus how long it takes to arrive at
        the next point.
        """
        return self.start_delay + self.arrival_delta

    def to_struct(self):
        """ Return the dict struct representing this Point, ready to be JSONified. Optional properties
            which are None or empty will be excluded from the struct."""
        struct = {
            'lat':self.lat, 'lng':self.lng, 'yaw':self.yaw
        }
        # Add optional fields.
        if self.name is not None:
            struct['name'] = self.name
        if self.arrival_delta != DEFAULT_ARRIVAL_DELTA:
            struct['arrival_delta'] = self.arrival_delta
        if self.start_delay != DEFAULT_START_DELAY:
            struct['start_delay'] = self.start_delay
        if len(self.identified) > 0:
            struct['identified'] = self.identified
        return struct

    def __repr__(self):
        return "%s(name=[%s], lat=[%f], lng=[%f], yaw=[%f], delta=[%d], delay=[%d], identified=%s)" %\
            (self.__class__.__name__, self.name, self.lat, self.lng,
             self.yaw, self.arrival_delta, self.start_delay, self.identified)

class Route(object):
    def __init__(self, points):
        self._points = []
        self._name_map = {}

        # Bookend the points list with None's to indicate that there is no
        # initially moved to or created Point and that the last next point is None.
        # e.g., [None, p0, p1, p2, None].
        self._points.append(None)
        for index, point in enumerate(points):
            self._points.append(point)
            # Add a mapping from point name to index if name is set.
            if point.name is not None:
                # Don't allow duplicate names.
                assert point.name not in self._name_map, "Named point %s used more than once." % point.name
                self._name_map[point.name] = index + 1
        self._points.append(None)

    ## Serialization methods
    @classmethod
    def from_struct(cls, points_struct):
        points = [Point.from_struct(struct) for struct in points_struct]
        return cls(points)

    def to_struct(self):
        return [p.to_struct() for p in self.iterpoints()]

    ## Informational methods
    def num_points(self):
        return len(self._points) - 2 # Remove the bookends.

    def named_points(self):
        """ Returns a list of all Point names for any Point with a defined name property. """
        return [p.name for p in self.iterpoints() if p.name is not None]

    def step_of_point(self, point_name):
        """
        Returns the 'sequence step' of the given Point name, as an integer.
        The first point would be step 1, the last is equal to num_points().
        In other words this is NOT a 0 indexed list.
        Returns None if the Point name is not in this Route.
        """
        index = self._name_map.get(point_name)
        if index is None:
            return None
        return index

    def duration(self):
        """ Returns the total number of seconds this route will take. """
        total = 0
        for p in self.iterpoints():
            # The total route duration is how long we wait at each point plus
            # how long it takes to arrive at the next point.
            total += p.duration()
        return total

    def duration_to_point(self, point_name):
        """ Returns the total number of seconds this route will take up to the given point name. """
        step = self.step_of_point(point_name)
        if step is None:
            raise UnknownPointError("Point does not exist in Route [%s]." % point_name)
        total = 0
        for p in self._points[1:step + 1]:
            total += p.duration()
        return total

    ## Points data iteration.
    def iterpoints(self):
        return iter(self._points[1:len(self._points) - 1])

    ## Movement iteration.
    def move_iter(self, delegate=None):
        """ Returns a Route.MovementIterator ready to walk this Route. Optionally provide a delegate object which
            conforms to some subset of the RouteDelegate protocol to receive delegate events as iteration occurs. """
        return Route.MovementIterator(self, delegate=delegate)

    def __repr__(self):
        return "%s(num_points=%d)" % (self.__class__.__name__, self.num_points())

    class MovementIterator(object):
        """ An iteration compatible object that yields the next move Point along the Route, one
            at a time. Also provides a method to create targets beyond the current move. """
        def __init__(self, route, delegate=None):
            self._route = route
            self._points = route._points
            self._delgate = delegate
            # The indexes of the point which has been moved to and created to
            # (created_to can be advanced in front of moved_to)
            # Initially these point at the first bookend.
            self._moved_to = 0
            self._created_to = 0

        ## Iteration protocol
        def __iter__(self):
            return self

        def next(self):
            moved_to = self.move_forward()
            if moved_to is None:
                raise StopIteration
            return moved_to

        ## Informational methods
        def current_point(self):
            return self._points[self._moved_to]

        def next_point(self):
            return self._points[self._moved_to + 1]

        def next_create_point(self):
            return self._points[self._created_to + 1]

        ## Movement methods.
        def move_forward(self):
            # If this is the last Point in the Route, send the leaving/left events.
            # This == factors in the bookends.
            if self._moved_to == self._route.num_points():
                last_point = self.current_point()
                if hasattr(self._delgate, "leaving_point"):
                    self._delgate.leaving_point(self._route, last_point)
                if hasattr(self._delgate, "left_point"):
                    self._delgate.left_point(self._route, last_point)
                return None

            # Create the next point if it has not already been created.
            if self._moved_to == self._created_to:
                self.create_next()

            # Inform the callbacks of movement. If at the start or end of the
            # route, don't send the events for the bookends.
            leaving_point = self.current_point()
            if leaving_point is not None:
                if hasattr(self._delgate, "leaving_point"):
                    self._delgate.leaving_point(self._route, leaving_point)
            if self.next_point() is not None:
                if hasattr(self._delgate, "moving_to_point"):
                    self._delgate.moving_to_point(self._route, to_point=self.next_point(), from_point=leaving_point)

            # Record the movement.
            self._moved_to += 1
            # Inform the callbacks of movement.
            if leaving_point is not None:
                if hasattr(self._delgate, "left_point"):
                    self._delgate.left_point(self._route, leaving_point)
            if hasattr(self._delgate, "moved_to_point"):
                self._delgate.moved_to_point(self._route, self.current_point())
            return self.current_point()

        def create_next(self):
            # This factors in the bookends.
            if self._created_to == self._route.num_points():
                raise EndOfRoute("End of Route reached, cannot create point.")

            next = self.next_create_point()
            relative_arrival_delta = next.arrival_delta
            if len(self._created_not_moved()) > 0:
                # Add to the arrival_delta the duration of all created but unmoved targets since
                # the arrival_delta is the delta from 'now' which needs to factor in created but unmoved to targets.                    
                relative_arrival_delta += sum([p.duration() for p in self._created_not_moved()])

                # It violates the assumptions of the Route data to have created but unmoved to targets
                # with a start_delay > 0 as there is no clear way to support this situation.
                for p in self._created_not_moved():
                    if p.start_delay > 0:
                        raise InvalidStartDelay("Created but unmoved to points cannot have start_delay > 0")

            # Inform the callbacks of creation.
            if hasattr(self._delgate, "create_target_for_point"):
                self._delgate.create_target_for_point(self._route, next, relative_arrival_delta)
            if hasattr(self._delgate, "created_point"):
                self._delgate.created_point(self._route, next)

            # Record the creation.
            self._created_to += 1
            return next

        def move_to_point(self, point_name):
            """
            Return the list of points that are visited.
            """
            # Find the index of this point by name. Exception if unknown name.
            index = self._route.step_of_point(point_name)
            if index is None:
                raise UnknownPointError("Point name not found %s" % point_name)
            assert index > self._moved_to

            moved = []
            for i in range(self._moved_to, index):
                moved.append(self.move_forward())
            return moved

        def create_to_point(self, point_name):
            """
            Return the list of created points.
            """
            # Find the index of this point by name. Exception if unknown name.
            index = self._route.step_of_point(point_name)
            if index is None:
                raise UnknownPointError("Point name not found %s" % point_name)
            assert index > self._created_to

            created = []
            for i in range(self._created_to, index):
                created.append(self.create_next())
            return created

        ## Helper methods
        # Returns the list of created, but not moved to Points. Can be empty.
        def _created_not_moved(self):
            assert self._moved_to <= self._created_to
            # No points between moved_to and created_to.
            if self._moved_to == self._created_to:
                return []
            # Factor in skipping the first bookend slot.
            return self._points[self._moved_to + 1:self._created_to + 1]
