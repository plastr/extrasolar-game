# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
## This module wraps the assets.json data file in helpers to provide the server with access to the
## asset data shared by the client and server (mostly icon URLs).
import pkg_resources

from front.lib import xjson, urls

# The path relative to this package where the asset data is stored.
ASSET_DEFINITIONS = pkg_resources.resource_filename('front', 'data/asset_definitions.json')

def sender_icon_url_for_dimension(sender_key, width, height):
    """ Return the message sender icon URL for a sender_key (the 'sender_key' for a message).
        If none is defined return the DEFAULT icon. """
    base_icon_path = _g_asset_definitions['sender'].get(sender_key)
    if base_icon_path is None:
        base_icon_path = _g_asset_definitions['sender']['DEFAULT']
    return "%s%dx%d.png" % (base_icon_path, width, height)

def mission_icon_definition(mission_icon_key):
    """ Return the icon URL for a specific mission icon 'key' (the 'title_icon' or 'description_icon'
        field in mission definitions). If none is defined return the DEFAULT icon. """
    # definition is a dict mapping 'done' or 'active' to the icon URL for that state.
    definition = _g_asset_definitions['task'].get(mission_icon_key)
    if definition is None:
        definition = _g_asset_definitions['task']['DEFAULT']
    return definition

def species_icon_url_for_dimension(species_icon_key, width, height):
    """ Return the icon URL for a specific species icon 'key' (the 'icon' field in species definitions). """
    return "/static/img/species_icons/%s_%dx%d.png" % (species_icon_key, width, height);

def achievement_icon_url(achievement_icon_key):
    """ Return the icon URL for a specific archievement icon 'key' (the 'icon' field in achievement definitions). """
    return _g_asset_definitions['achievement'][achievement_icon_key]

def message_icon_url(message_icon_key):
    """ Return the icon URL for a specific message icon 'key' (derived from style and is_locked). """
    return _g_asset_definitions['message'][message_icon_key]

def ui_asset_url(asset_key):
    """ Get the URL for a UI asset.  Note that the asset will be relative -- not fully-qualified.
    :param asset_key: UI asset key, e.g., 'UI_LOADING'
    """
    asset_url = _g_asset_definitions['ui'][asset_key]
    assert asset_url is not None
    return asset_url

def get_asset_json():
    """ Return the assets.json contents as a string, ready to be fed to the client. """
    return _g_asset_json

_g_asset_definitions = None
_g_asset_json = None
def init_module():
    global _g_asset_definitions, _g_asset_json
    if _g_asset_definitions is not None: return

    # Instead of using the usual data.load_json load the file data ourselves so it can be inserted
    # directly into game.html for the client to read.
    with open(ASSET_DEFINITIONS) as f:
        _g_asset_json = f.read()
        _g_asset_definitions = xjson.loads(_g_asset_json)
