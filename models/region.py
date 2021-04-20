# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import models
from front.lib import geometry
from front.data import load_json, schemas
from front.models import chips

class RegionGeography(object):
    """
    A mixin class providing geometry related methods to Region 'like' classes.
    It is expected classes mixing in this class will provide the following properties at least:
    'shape', 'verts', 'center' and 'radius'
    """

    def point_inside(self, lat, lng):
        """
        Return True if the lat/lng point is inside this region, False otherwise.
        :param lat, lng: The latitude and longitude of the point.
        """
        if self.shape == shapes.POLYGON:
            return geometry.point_inside_polygon([lat, lng], self.verts)

        elif self.shape == shapes.CIRCLE or (self.shape == shapes.POINT and self.radius > 0):
            coords = geometry.lat_lng_to_meters(lat, lng)
            center_coords = geometry.lat_lng_to_meters(self.center[0], self.center[1])
            return geometry.point_inside_circle(coords, center_coords, self.radius)

        raise Exception("Unknown Region shape %s encountered in point_inside [%s]" % (self.shape, self.region_id))

    def coords_traverse(self, p, q):
        """
        Return True if the line segment connecting the [lat, lng] point p and q traverses this region,
        False otherwise. Line segments which fall entirely inside the region or are tangent are
        considered to travese the region.
        :param p, q: The latitude and longitude points of the line segment as arrays, [lat, lng].
        """
        if self.shape == shapes.CIRCLE:
            # Convert the lat/long coordinates into our local meter grid system.
            p_coords = geometry.lat_lng_to_meters(p[0], p[1])
            q_coords = geometry.lat_lng_to_meters(q[0], q[1])
            center_coords = geometry.lat_lng_to_meters(self.center[0], self.center[1])

            return geometry.lineseg_intersects_circle(p_coords, q_coords,
                                                      center_coords, self.radius)

        if self.shape == shapes.POLYGON:
            return geometry.lineseg_intersects_polygon(p, q, self. verts)

        # TODO: Check against other shape types.
        raise Exception("Unknown Region shape encountered in coords_traverse.")

# Region shape definitions.
class shapes(object):
    POLYGON  = "POLYGON"
    POLYLINE = "POLYLINE"
    CIRCLE   = "CIRCLE"
    POINT    = "POINT"
    ALL = set([POLYGON, POLYLINE, CIRCLE, POINT])

def add_region_to_user(ctx, user, region_id, **kwargs):
    """
    Create a Region model from a given name which is a key in the regions.json file. This adds
    the region to the User's regions collection and issues an ADD chip.
    """
    new_region = user.regions.create_child(region_id=region_id, **kwargs)
    new_region.send_chips(ctx, user)
    return new_region

def from_id(region_id, **kwargs):
    """
    Create a Region model from a given name which is a key in the regions.json file. This does
    not issue a chip, it is just a factory method.
    """
    return Region(region_id, **kwargs)

class Region(chips.Model, RegionGeography, models.UserChild):
    """
    Holds the parameters for a single region that may be displayed on the map.
    :param region_id: unique key used to access this region.
    """
    id_field = 'region_id'
    fields = frozenset(['title', 'description', 'restrict', 'visible', 'style',
                        'shape', 'marker_icon', 'region_icon', 'verts', 'center', 'radius'])
    def __init__(self, region_id, **kwargs):
        # Populate the fields which come from the regions definition.
        definition = _get_region_definition(region_id)
        params = {}
        for field in self.fields:
            if field == 'verts':
                value = definition.get(field, [])
            # Ignore comment fields.
            elif field == 'comment':
                continue
            else:
                value = definition.get(field, None)
            params[field] = value

        # Optionally override any value from or missing from the description, for example
        # some regions might have a location set by a mission specific situation.
        params.update(kwargs)
        # And now populate the fields.
        super(Region, self).__init__(region_id=region_id, **params)

        # Finally, validate that we have a minimum set of useful information, especially as some
        # regions expect the constructor to supply data not in the description file.
        if self.shape in [shapes.CIRCLE, shapes.POINT]:
            if self.center == [] or self.radius == None:
                raise Exception("Region %s is missing required data. verts=%s, center=%s, radius=[%s]"
                    % (self.region_id, self.verts, self.center, self.radius))
        elif self.shape in [shapes.POLYGON, shapes.POLYLINE]:
            if self.verts == []:
                raise Exception("Region %s is missing required data. verts=%s, center=%s, radius=[%s]"
                    % (self.region_id, self.verts, self.center, self.radius))
        else:
            raise Exception("Region %s has unknown shape %s" % (self.region_id, self.shape))

    @property
    def user(self):
        # self.parent is user.regions, the parent of that is the User itself
        return self.parent.parent

def is_known_region_id(region_id):
    """ Returns True if the given region_id was defined in the region definitions. """
    return region_id in _get_all_region_definitions()

def _get_all_region_definitions():
    """ Return the region definitions as loaded from the JSON data file. """
    return _g_region_definitions

def _get_region_definition(region_id):
    """
    Return the region definition as a dictionary for the given region_id.

    :param region_id: str key for this region definition e.g RGN_ISLAND01. Defined in
    regions.json
    """
    return _get_all_region_definitions()[region_id]

# Fields with 'None' default values are optional in the regions.json file and will have the value of
# None/null in the gamestate if not defined in that file.
def _add_region_definition(region_id, title, description, restrict, style, visible, shape, verts, center, radius,
                            region_icon=None, marker_icon=None, comment=None):
    # Skip values from the method parameters which are None.
    definition = dict([(key, value) for (key, value) in locals().iteritems()
                       if value is not None])
    _g_region_definitions[region_id] = definition

_g_region_definitions = None
def init_module(regions_path):
    global _g_region_definitions
    if _g_region_definitions is not None: return

    _g_region_definitions = {}
    definitions = load_json(regions_path, schema=schemas.REGION_DEFINITIONS)
    for region_id, definition in definitions.iteritems():
        _add_region_definition(region_id, **definition)
