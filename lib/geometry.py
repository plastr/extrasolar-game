# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Contains abstract map geometry utilities.
import math
from collections import namedtuple

Point = namedtuple('Point', ['x', 'y'])

def lat_lng_to_meters(lat, lng):
    """
    Convert a given latitude and longitude value into an x,y coordinate in our local
    coordinate system, which is a meter sized grid overlaid onto the planet.
    NOTE: Our local coordinate system is offset by 25694,63254 at zoom level 17.
    :param lat, lng: The coordinates to convert.
    :returns: a tuple (x, y)

    >>> lat_lng_to_meters(6.239325101535731, -109.41348444058872)
    (1476.1012644656003, 1491.9509387165308)
    """
    siny = math.sin(lat * math.pi / 180.0)
    yd = 16777216.0 - 0.5 * math.log((1.0 + siny) /
         (1.0-siny)) * (33554432.0 / (2.0*math.pi))
    xd = 16777216.0 + lng * (33554432.0/360.0)

    # Translate to our local coordinate system. Use zoom level 25 where
    # 1 tile's width is 1 meter.
    # Map tile offset: 25694,63254 at level 17
    originX, originY = _tile_origin(25)
    yd -= originY  # 16193024.0f
    xd -= originX  # 6577664.0f

    return xd, yd

def lineseg_intersects_circle(p, q, c, radius):
    """
    Return True if the line segment defined by P and Q intersects with the circle
    defined by the center at C and with the given radius. Also returns True if the line segment
    is inside of the circle.
    NOTE: Adapted from: http://www.desert.cx/sites/default/files/lseg_circ_intersect.c
    SEE ALSO: http://mathworld.wolfram.com/Circle-LineIntersection.html
              http://paulbourke.net/geometry/sphereline/
    :param p, q: The coordinates of the line segment, as two element array [x, y].
    :param c, radius: The center and radius of the circle. c is two element array [x, y].

    >>> lineseg_intersects_circle([1, 1], [10, 10], [10, 5], 2)
    False
    >>> lineseg_intersects_circle([1, 1], [10, 10], [10, 5], 5)
    True
    >>> lineseg_intersects_circle([5, 0], [5, 6], [3, 3], 2) # Tangent
    True
    >>> lineseg_intersects_circle([0, 0], [2, 4], [2, 2], 5) # Segment inside circle.
    True
    >>> p = lat_lng_to_meters(6.239781042287593, -109.41364000871158)
    >>> q = lat_lng_to_meters(6.239781042267593, -109.41364000871158)
    >>> c = lat_lng_to_meters(6.239781042277593, -109.41364000871158)
    >>> lineseg_intersects_circle(p, q, c, 25.0)
    True
    >>> p = lat_lng_to_meters(6.239781042287593, -109.41364000871158)
    >>> q = lat_lng_to_meters(6.239781042267593, -109.41364000871158)
    >>> c = lat_lng_to_meters(6.559781042267593, -109.55368000898158)
    >>> lineseg_intersects_circle(p, q, c, 25.0)
    False
    """
    # We define parametric equations for the location of the center of
    #   the circle and the location of a point along the line segment
    #   (from t=0.0 to t=1.0)
    #      P1(t) = c.x,
    #              c.y
    #      P2(t) = p.x + t*(q.x - p.x),
    #              p.y + t*(q.y - p.y)
    #
    #  From that we can define a parametric equation for the square of
    #  the distance between a point on the line segment and the center
    #  of the circle
    #     R(t) = (P2(t).x - P1(t).x)^2 + (P2(t).y - P1(t).y)^2
    #          = ((p.x + t*(q.x - p.x)) - c.x)^2
    #            + ((p.y + t*(q.y - p.y)) - c.y)^2
    # 
    #  It turns out that R(t) is a quadratic equation. To find the value
    #  for t where R(t) is minimized, we take the derivative of R(t) and
    #  solve for t when R'(t) = 0

    # Pack the arrays into a namedtuple for clarity.
    p = Point(p[0], p[1])
    q = Point(q[0], q[1])
    c = Point(c[0], c[1])

    dx = float(q.x - p.x)
    dy = float(q.y - p.y)
    # If the line segment is a single point, determine if the point is inside the circle.
    if (dx*dx + dy*dy) == 0.0:
        return point_inside_circle([p.x, p.y], c, radius)
    # Solve for t.
    t = float(-((p.x - c.x)*dx + (p.y - c.y)*dy) / ((dx*dx) + (dy*dy)))

    # Restrict t to within the limits of the line segment (0.0 and 1.0)
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    # Check to see if the distance between the closest point and the center
    #  of the circle is less than the radius of the circle, using the
    #  equation for R(t) described above
    dxc = (p.x + t*(q.x - p.x)) - c.x
    dyc = (p.y + t*(q.y - p.y)) - c.y
    rt = float((dxc*dxc) + (dyc*dyc))
    # Use <= to capture tangent points as well.
    if rt <= (radius * radius):
        return True
    else:
        return False

def lineseg_intersects_polygon(p, q, verts):
    """
    Return True if the line segment defined by P and Q intersects with the polygon with
    the given vertices.  Also returns True if the line segment is entirely inside of the polygon.
    
    :param p, q: The coordinates of the line segment, as two element array [x, y].
    :param verts: An array of vertices [x, y] that form our polygon  The first and
    last vertices should be the same.

    >>> lineseg_intersects_polygon([0,1.1], [2, 1.1], [[0,0], [1,1], [1,0], [0,0]])
    False
    >>> lineseg_intersects_polygon([0,-0.1], [10, -0.1], [[0,0], [1,1], [1,0], [0,0]])
    False
    >>> lineseg_intersects_polygon([0,0.9], [1, 0.9], [[0,0], [1,1], [1,0], [0,0]])
    True
    >>> lineseg_intersects_polygon([0,0.1], [0.5,0.1], [[0,0], [1,1], [1,0], [0,0]])
    True
    >>> lineseg_intersects_polygon([0.5,0.1], [0,0.1], [[0,0], [1,1], [1,0], [0,0]])
    True
    """
    if point_inside_polygon(q, verts):
        return True

    # For each pair of coordinates in the polygon, see if there is an intersection.
    numVerts = len(verts)
    for i in range(numVerts-1):
        v0 = verts[i]
        v1 = verts[(i+1)%numVerts]

        # Compute which halfspace the start and endpoints lie in.
        halfspace_start = _point_line_halfspace(p, v0, v1)
        halfspace_end   = _point_line_halfspace(q, v0, v1)
        # If both points are on the same side of the line, ignore this segment.
        if halfspace_start > 0.0 and halfspace_end > 0.0:
            continue
        if halfspace_start < 0.0 and halfspace_end < 0.0:
            continue
        
        # If the determinate is 0, the lines are parallel or one segment is a point.
        det = (v1[1]-v0[1])*(q[0]-p[0]) - (v1[0]-v0[0])*(q[1]-p[1])
        if det == 0.0:
            continue

        # Calculate the time t of the intersection in the parametric equation for the poly.
        tPoly = ((q[0]-p[0])*(p[1]-v0[1]) -
                 (q[1]-p[1])*(p[0]-v0[0]))/det
        if tPoly < 0.0 or tPoly > 1.0:
            # Intersection was beyond the ends of the line segment.
            continue
        
        # Calculate the time t of the intersection in the parametric equation for the ray.
        tRay = ((v1[0]-v0[0])*(p[1]-v0[1]) -
                (v1[1]-v0[1])*(p[0]-v0[0]))/det
        if tRay >= 0.0 and tRay <= 1:
            # The point of intersection is p + (q-p)*tRay
            return True
    return False

def distance_to_polygon(p, verts):
    """
    Return the nearest distance from point p to the edges of a polygon.
    
    :param p: A point [x, y].
    :param verts: An array of vertices [x, y] that form our polygon  The first and
    last vertices should be the same.

    >>> distance_to_polygon([0,0], [[0,0], [1,1], [1,0], [0,0]])
    0.0
    >>> distance_to_polygon([0.5,-1], [[0,0], [1,1], [1,0], [0,0]])
    1.0
    >>> distance_to_polygon([0,1], [[0,0], [1,1], [1,0], [0,0]])
    0.7071067811865476
    >>> distance_to_polygon([0,2], [[0,0], [2,2], [2,0], [0,0]])
    1.4142135623730951
    """
    
    # For each pair of coordinates in the polygon, compute the distance to point p.
    numVerts = len(verts)
    min_dist = -1
    for i in range(numVerts-1):
        dist_to_seg = -1
        v0 = verts[i]
        v1 = verts[(i+1)%numVerts]

        len_squared = _length_squared(v0, v1)  # Use the square of the length to avoid a sqrt.
        if len_squared == 0.0:
            dist_to_seg = _distance(p, v0);
        else:
            # Consider the line extending the segment, parameterized as v0 + t (v1 - v0).
            # We find projection of point p onto the line. 
            # It falls where t = [(p-v0) . (v1-v0)] / |v1-v0|^2
            v0_p  = [p[0] -v0[0], p[1] -v0[1]]
            v0_v1 = [v1[0]-v0[0], v1[1]-v0[1]]
            t =  (v0_p[0] * v0_v1[0] + v0_p[1] * v0_v1[1]) / float(len_squared)  # Force floating-point division
            if t < 0.0:
                dist_to_seg = _distance(p, v0)  # Closest intersection is beyond the v0 end of the segment
            elif t > 1.0:
                dist_to_seg = _distance(p, v1)  # Closest intersection is beyond the v1 end of the segment
            else:
                projection = [v0[0] + t * v0_v1[0], v0[1] + t * v0_v1[1]]  # Projection falls on the segment
                dist_to_seg = _distance(p, projection)
        if i==0 or dist_to_seg < min_dist:
            min_dist = dist_to_seg

    return min_dist

def point_inside_polygon(point, verts):
    """
    Return True if the point is inside the given polygon verticies, False otherwise.
    :param point: The coordinates of the point, as two element array [x, y].
    :param verts: The list of [x, y] points of the polygon.

    >>> verts = [[6.23971, -109.41356], [6.23959, -109.41297], [6.23898, -109.41331]]
    >>> point_inside_polygon([6.239781042267593, -109.41364000871158], verts)
    False
    >>> point_inside_polygon([6.239325101535731, -109.41348444058872], verts)
    False
    >>> point_inside_polygon([6.238866494083636, -109.41331277921176], verts)
    False
    >>> point_inside_polygon([6.239290439358602, -109.41306869819141], verts)
    False
    >>> point_inside_polygon([6.239524, -109.413186], verts)
    True
    """
    # Pack the arrays into a namedtuple for clarity.
    point = Point(point[0], point[1])

    # Cast a ray in the +x direction and count line-segment crossings to determine if
    # the given point is inside the boundary.
    # For each pair of coordinates in the polygon, see if there is an intersection.
    intersections = 0
    numVerts = len(verts)
    for i in range(numVerts):
        v0 = verts[i]
        v1 = verts[(i+1)%numVerts]
        # If the y-coordinates are the same, then no intersection is possible.
        if v0[1] == v1[1]:
            continue
        # Make sure that v0 has a smaller y-coordinate than v1.
        if (v0[1] > v1[1]):
            swap = v0
            v0 = v1
            v1 = swap
        # Check if the line from 'point' moving in the +x direction crosses this segment.
        # The choice of inequality operators is important to make sure we count a line
        # exactly once if we cross the vertex.
        if point.y > v1[1] or point.y <= v0[1]:
            continue
        # Compute which halfspace the point is in.
        halfspace = _point_line_halfspace([point.x, point.y], v0, v1)
        if halfspace > 0:
            intersections += 1
    # An even number of intersections means we're outside the polygon.
    if intersections%2 == 0:
        return False
    return True

def point_inside_circle(point, center, radius):
    """
    Return True if the point is inside the given circle (center and radius), False otherwise.
    :param point: The coordinates of the point, as two element array [x, y].
    :param center, radius: The center and radius of the circle. center is two element array [x, y].

    >>> point_inside_circle([0, 0], [2, 2], 2)
    False
    >>> point_inside_circle([1, 1], [2, 2], 2)
    True
    >>> point_inside_circle([2, 2], [2, 2], 2) # Center
    True
    >>> point_inside_circle([0, 2], [2, 2], 2) # Tangent
    True
    """
    # Pack the arrays into a namedtuple for clarity.
    point = Point(point[0], point[1])
    center = Point(center[0], center[1])

    dx = point.x - center.x
    dy = point.y - center.y
    distance_squared = dx*dx + dy*dy
    return distance_squared <= (radius * radius)

def angle_closeness(a, b, error):
    """Determine the closeness of two angles, in radians, if they are witin the error closeness, in radians.

    # Simple angles.
    >>> angle_closeness(1, 1.1, .2)
    True
    >>> angle_closeness(1, 1.2, .1)
    False

    # Negative angles.
    >>> angle_closeness(-1, -1.1, .2)
    True
    >>>
    angle_closeness(-1, -1.2, .1)
    False

    # Zero angles.
    >>> angle_closeness(-.1, .1, .3)
    True
    >>> angle_closeness(.1, -.1, .3)
    True
    >>> angle_closeness(.1, -.1, .1)
    False
    >>> angle_closeness(-.1, .1, .1)
    False

    # Angles near PI.
    angle_closeness(3.1, 3.0, .2)
    True
    angle_closeness(-3.1, -3.0, .2)
    True
    angle_closeness(-3.1, 3.1, .2)
    True
    angle_closeness(3.1, -3.1, .2)
    True
    angle_closeness(3.1, 3.0, .05)
    False
    angle_closeness(-3.1, -3.0, .05)
    False
    angle_closeness(-3.1, 3.1, .05)
    False
    angle_closeness(3.1, -3.1, .05)
    False
    """
    if abs(a - b) < error:
        return True
    else:
        if a < 0:
            a += math.pi * 2
        elif b < 0:
            b += math.pi * 2
        return abs(a - b) < error

def to_radians(degrees):
    """Convert degress to radians.

    >>> to_radians(0)
    0.0
    >>> to_radians(360)
    6.283185307179586
    >>> to_radians(90)
    1.5707963267948966
    >>> to_radians(180)
    3.141592653589793
    >>> to_radians(-180)
    -3.141592653589793
    """
    return degrees * math.pi/180;

def dist_between_lat_lng(lat0, lng0, lat1, lng1):
    """
    Compute the distance, in meters, between two pairs of lat/lng cooridnates in our
    canonical (i.e., fake but useful meter-based) coordinate system.  Note that this will
    give a different answer from the haversine formula.

    >>> d = dist_between_lat_lng(6.239883912, -109.413989817, 6.239663470, -109.414478278)
    >>> d > 49.99999
    True
    >>> d < 50.00001
    True
    >>> dist_between_lat_lng(0, 0, 0, 0)
    0.0
    """
    p0 = lat_lng_to_meters(lat0, lng0)
    p1 = lat_lng_to_meters(lat1, lng1)
    dx = p1[0]-p0[0]
    dy = p1[1]-p0[1]
    return math.sqrt(dx*dx + dy*dy)

def interpolate_between_targets(current_target, prev_target, at_time):
    """ Determine the latitude, longitude and yaw positions for a location
        between two Targets at the given time.
        at_time is in terms of seconds since user.epoch

    >>> from datetime import timedelta, datetime
    >>> from collections import namedtuple
    >>> MockTarget = namedtuple('MockTarget', ['start_time', 'arrival_time', 'lat', 'lng', 'yaw'])
    >>> HOURS = 60*60
    >>> now = 1200 # Seconds since epoch
    >>> t1 = MockTarget(now, now + (6*HOURS), 66.25, 85.0, 1.0)
    >>> t2 = MockTarget(now - (6*HOURS), now, 33.25, 85.0, 1.0)
    >>> interpolate_between_targets(t1, t2, now - (6*HOURS))
    (33.25, 85.0, 1.0)
    >>> interpolate_between_targets(t1, t2, now)
    (33.25, 85.0, 1.0)
    >>> interpolate_between_targets(t1, t2, now + (2*HOURS))
    (44.25, 85.0, 1.0)
    >>> interpolate_between_targets(t1, t2, now + (4*HOURS))
    (55.25, 85.0, 1.0)
    >>> interpolate_between_targets(t1, t2, now + (6*HOURS))
    (66.25, 85.0, 1.0)
    >>> interpolate_between_targets(t1, t2, now + (12*HOURS))
    (66.25, 85.0, 1.0)
    """
    # Interpolate between the start and arrival times, clamping the interp value.
    interp = float(at_time - current_target.start_time) / float(current_target.arrival_time - current_target.start_time)
    interp = min(1.0, max(0.0, interp))

    # Using this value, interpolate between the positions of the prev_target and current_target targets.
    lat = prev_target.lat * (1.0 - interp) + current_target.lat * interp
    lng = prev_target.lng * (1.0 - interp) + current_target.lng * interp
    # TODO: Compute the yaw between the prev_target and current_target targets.
    yaw = current_target.yaw
    return (lat, lng, yaw)

def clip_path(a, b, percent):
    """ Clip the line from a to b at a percentage of their current distance. 
        e.g., if percent == 1.0, return b.

    >>> clip_path([-1.0, -2.0], [1.0, 2.0], 0.0)
    (-1.0, -2.0)
    >>> clip_path([-1.0, -2.0], [1.0, 2.0], 0.5)
    (0.0, 0.0)
    >>> clip_path([-1.0, -2.0], [1.0, 2.0], 1.0)
    (1.0, 2.0)
    """
    a = Point(a[0], a[1])
    b = Point(b[0], b[1])
    return (a.x + percent * (b.x-a.x), a.y + percent * (b.y-a.y))                                                              

def _length_squared(v0, v1):
    """
    The square of the distance between points v0 and v1.
    Params: v0, and v1 are points expressed as [x, y].
    """
    dx = v1[0]-v0[0]
    dy = v1[1]-v0[1]
    return dx*dx + dy*dy

def _distance(v0, v1):
    """
    The distance between points v0 and v1.
    Params: v0, and v1 are points expressed as [x, y].
    """
    return math.sqrt(_length_squared(v0, v1))

def _point_line_halfspace(point, v0, v1):
    """
    Check which half-space the point is in relative to line [v0,v1].
    Params: Point, v0, and v1 are all arrays with x and y values.
    Return: A positive or negative value indicates the respective halfspace.
    0 means the point is on the line or the line has zero length.
    """
    v0_to_v1 = [v1[0]-v0[0], v1[1]-v0[1]]
    v0_to_point = [point[0]-v0[0], point[1]-v0[1]]
    normal = [-v0_to_v1[1], v0_to_v1[0]]

    # Take the dot product of the normal and v0_to_point.
    return normal[0]*v0_to_point[0] + normal[1]*v0_to_point[1]

def _tile_origin(level):
    """ Returns the origin map tile offset as an (x, y) tuple for our local coordinate system
    for the given map zoom level. """
    if level < 16:
        raise Exception("WARNING: Unexpected value %d for 'level' in tileOrigin.\n", level)
    x = 12847 << (level - 16)
    y = 31627 << (level - 16)
    return x, y
