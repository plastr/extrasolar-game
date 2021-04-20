# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
'''
Defines assets known to the renderer and functions to lookup current assets for a user.
'''

from front.models import progress

def assets_for_user_at_time(user, active_rover, at_time):
    """ at_time is in terms of seconds since user.epoch """
    asset_list = []
    asset_list.append(
        RendererAsset('LANDER01', active_rover.lander['lat'], active_rover.lander['lng'], 0.0, 0.0, 1, 0))

    # Pick the approprate model to be rendered for each rover.
    for rover in user.rovers.values():
        (lat, lng, yaw) = rover.location_at_time(at_time)
        if active_rover.rover_id == rover.rover_id:
            asset_list.append(RendererAsset('ROVER_SHADOW', lat, lng, 0.0, yaw, 1, 0))
        elif user.progress.has_achieved(progress.names.PRO_ROVER_STUCK):
            asset_list.append(RendererAsset('ROVER_DISASSEMBLED', lat, lng, 0.0, yaw, 1, 0))
        else:
            raise Exception("Unexpected condition in assets_for_user_at_time.")

    return asset_list

class RendererAsset(object):
    fields = frozenset(['model_name', 'lat', 'lng', 'elevation', 'yaw', 'collide', 'show_on_tile'])

    def __init__(self, model_name, lat, lng, elevation, yaw, collide, show_on_tile):
        params = locals()
        for field in self.fields:
            setattr(self, field, params[field])

    def to_struct(self):
        struct = {}
        for field in self.fields:
            struct[field] = getattr(self, field)
        return struct
