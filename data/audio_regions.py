# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Defines audio regions which are server only Region like objects used to determine when
# targets pass through or near audio detection areas on the map.
from front.data import load_json, schemas
from front.models import region, mission

def target_traverses_active_audio_region(target):
    """ 
    Returns True if the rover has/will traverse any 'active' audio regions when moving
    from the previous target to the given target. An active audio region is one in which
    the user has not already detected and identified the source of the audio signal.
    """
    return len(active_audio_regions_traversed_by_target(target)) > 0

def active_audio_regions_traversed_by_target(target):
    """ 
    Returns the list of 'active' audio regions that the rover traversed while moving
    from the previous target to the given target. An active audio region is one in which
    the user has not already detected and identified the source of the audio signal.
    """
    user = target.user
    active_regions = []
    for audio_region in _iterate_all_regions():
        # A region is active if the rover path crosses through it...
        if target.traverses_region(audio_region):
            existing = user.missions.get_only_by_definition(audio_region.mission_definition)
            # and if there are no existing missions for the associated mission_definition
            # for this user.
            if existing is None:
                active_regions.append(audio_region)
    return active_regions

class AudioRegion(region.RegionGeography):
    """
    Holds the parameters for a single audio region. This is similar to a models.Region object, yet
    only resides on the server, and is used for triggering audio capturing missions.
    :param region_id: unique key used to access this region.
    """
    fields = frozenset(['region_id', 'mission_definition', 'shape', 'verts', 'center', 'radius'])

    def __init__(self, **kwargs):
        # Populate the fields which come from the regions definition.
        for field in self.fields:
            setattr(self, field, kwargs[field])

def _get_all_regions():
    """ Return the audio region data decoded from JSON data file. Keyed by region_id. """
    return _g_audio_regions

def _iterate_all_regions():
    return _get_all_regions().itervalues()

def _get_region_by_id(region_id):
    return _get_all_regions()[region_id]

_g_audio_regions = None
def init_module(audio_regions_path):
    global _g_audio_regions
    if _g_audio_regions is not None: return

    definitions = load_json(audio_regions_path, schema=schemas.AUDIO_REGION_DEFINITIONS)
    _g_audio_regions = {}
    for region_id in definitions:
        # Perform some additional validation, namely that every mission definition listed in
        # an audio region is a known definition
        try:
            mission.get_mission_definition(definitions[region_id]['mission_definition'])
        except KeyError, e:
            raise ValueError("mission_definition unknown in audio region description. %s %s" % (str(e), region_id))
        _g_audio_regions[region_id] = AudioRegion(region_id=region_id, **definitions[region_id])
