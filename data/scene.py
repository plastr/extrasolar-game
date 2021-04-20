# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
'''
Defines scenes served by the local server, e.g. the initial scene and scenes for unit testing.
'''
from front import target_image_types
from front.lib import urls

class Scene(object):
    def __init__(self, photo, thumb, species, wallpaper, infrared, thumb_large):
        self.photo = photo
        self.thumb = thumb
        self.species = species
        self.wallpaper = wallpaper
        self.infrared = infrared
        self.thumb_large = thumb_large

    def to_struct(self):
        server_struct = {target_image_types.PHOTO: self.photo,
                         target_image_types.THUMB: self.thumb,
                         target_image_types.SPECIES: self.species,
                         target_image_types.WALLPAPER: self.wallpaper}
        if self.infrared    != None: server_struct[target_image_types.INFRARED]    = self.infrared
        if self.thumb_large != None: server_struct[target_image_types.THUMB_LARGE] = self.thumb_large
        return server_struct

    def to_struct_for_client(self):
        """ The client side/gamestate does not get the species image. """
        client_struct =  {target_image_types.PHOTO: self.photo,
                          target_image_types.THUMB: self.thumb,
                          target_image_types.WALLPAPER: self.wallpaper}
        if self.infrared    != None: client_struct[target_image_types.INFRARED]    = self.infrared
        if self.thumb_large != None: client_struct[target_image_types.THUMB_LARGE] = self.thumb_large
        return client_struct

def from_struct(struct):
    return Scene(photo=struct[target_image_types.PHOTO],
                 thumb=struct[target_image_types.THUMB],
                 species=struct[target_image_types.SPECIES],
                 wallpaper=struct[target_image_types.WALLPAPER],
                 infrared=struct[target_image_types.INFRARED] if struct.has_key(target_image_types.INFRARED) else None,
                 thumb_large=struct[target_image_types.THUMB_LARGE] if struct.has_key(target_image_types.THUMB_LARGE) else None)

def define_scene(scene_name, is_panorama=False, has_infrared=False, scene_url=None):
    if scene_url is None:
        scene_url = urls.scene(scene_name)
    wallpaper_url = scene_url + "_1920x1440.jpg"
    thumb_large_url = None
    if is_panorama:
        wallpaper_url = scene_url + "_5120x1280.jpg"
        thumb_large_url = scene_url + "_400x210.jpg"
    infrared_url = None
    if has_infrared:
        infrared_url = scene_url + "ir.jpg"
    return Scene(photo=scene_url + ".jpg", thumb=scene_url + "t.jpg", species=scene_url + "id.png",
        wallpaper=wallpaper_url, infrared=infrared_url, thumb_large=thumb_large_url)

INITIAL_NORTH = define_scene("first_scene_north")
INITIAL_SOUTH = define_scene("first_scene_south")
INITIAL_WEST = define_scene("first_scene_west")
INITIAL_EAST = define_scene("first_scene_east")
DISTRESS01 = define_scene("distress01")
TESTING          = define_scene("test_scene", has_infrared = False)
TESTING_INFRARED = define_scene("test_scene", has_infrared = True)
TESTING_PANORAMA = define_scene(scene_name="test_scene_panorama", is_panorama=True)
