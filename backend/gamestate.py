# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import urls, utils, gametime
from front.backend import edmodo_backend

def gamestate_for_user(u, request):
    """This is the top-level gamestate-building function.  It returns a Python
    dictionary which the caller can easily convert to JSON or whatever."""
    front_config = request.environ['front.config']

    # Ask the user object to load and cache all of the gamestate data so that only a few
    # queries are executed instead of a large number of queries for every collection lazy loader.
    # The results are cached in u.ctx.row_cache and used in the lazy loader functions.
    u.load_gamestate_row_cache()

    # Construct the user map tile url base by including the user_id elements.
    user_map_tile_url = "%s/%s/%s" % (
        front_config.get('map_user_tile_url'),
        str(u.user_id)[0:2],
        str(u.user_id))

    gamestate = {}
    # Construct the top level urls dictionary.
    gamestate['urls'] = {
        'map_tile':            front_config['map_tile_url'],
        'user_map_tile':       user_map_tile_url,
        # Construct the full absolute profile URL so that it can be displayed as a copy-able string
        # to the user on their in-game profile page.
        'user_public_profile': urls.user_public_profile_absolute(request, u.user_id),
        'gamestate':           urls.gamestate(),
        'fetch_chips':         urls.fetch_chips(),
        'create_progress':     urls.client_progress_create(),
        'create_invite':       urls.invite_create()
    }
    # Add the top level 'config' namespace.
    gamestate['config'] = {
        'server_time':         utils.to_ts(gametime.now()),
        'last_seen_chip_time': utils.usec_js_from_dt(gametime.now()),
        'chip_fetch_interval': int(front_config['chip_fetch_interval']),
        'use_social_networks': front_config['template.use_social_networks']
    }
    # Finally add the 'user' namespace with all of the user's game state.
    gamestate['user'] = u.to_struct()

    # If this user is a teacher who should have access to classroom data, build that struct now.
    # The attempt to fetch teacher credentials will either return None or a struct with
    # access_token, user_token, and sandbox.
    edmodo_credentials = u.get_edmodo_teacher_credentials()
    if edmodo_credentials:
        gamestate['classroom'] = edmodo_backend.get_classroom_data(request, edmodo_credentials['access_token'],
                                    edmodo_credentials['user_token'], edmodo_credentials['sandbox'])
    
    return gamestate
