# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
GameNode is the main node for the game.  Largely this file is about constructing
the gamestate object and getting it to the browser by various means.  The 
gamestate gets converted from its database representation to a JSON
structure here.
"""
from datetime import timedelta
from restish import resource
from front.lib import get_uuid, xjson, db, gametime
from front.data import scene
from front.backend import renderer
from front.models import maptile
from front.models import user as user_module
from front.resource import json_success, decode_json

# The authorization preshared key that the renderer uses to authenticate itself.
AUTH_TOKEN = None

# Needs to be called before this module can be used to initialize the authorization token.
def init_module(auth_token):
    global AUTH_TOKEN
    AUTH_TOKEN = auth_token

# If a locked target hasn't been processed in this number of minutes then something has failed
# in the renderer and that target needs to be processed again.
LOCK_TIMEOUT = 5

class RendererNode(resource.Resource):
    @resource.child()
    def next_target(self, request, segments):
        return NextTarget()

    @resource.child()
    def target_processed(self, request, segments):
        return TargetProcessed()

class NextTarget(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={'auth': unicode})
        if body is None: return error
        _require_auth(body)

        with db.conn(request) as ctx:
            render_after = gametime.now()
            lock_timeout = gametime.now() - timedelta(minutes=LOCK_TIMEOUT)
            # Select the next unprocessed picture target to render, whose render_at time has been arrived at
            # and which is not locked or whose lock has expired.
            rows = db.rows(ctx, 'get_unprocessed_target', render_after=render_after, lock_timeout=lock_timeout)
            # Nothing needs processing.
            if len(rows) == 0:
                return json_success({'status': 'ok'})

            row = rows[0]
            user_id = get_uuid(row['user_id'])
            rover_id = get_uuid(row['rover_id'])
            target_id = get_uuid(row['target_id'])
            user = user_module.user_from_context(ctx, user_id)

            target = user.rovers[rover_id].targets[target_id]
            # Lock the target during processing so only one renderer instance is processing it at a time.
            target.lock_for_processing()

            struct = renderer.process_target_struct(user, target)
            return json_success(struct)

class TargetProcessed(resource.Resource):
    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={
            'auth': unicode,
            'user_id': unicode,
            'rover_id': unicode,
            'target_id': unicode,
            'arrival_time': int,
            'classified': int,
            'images': dict,
            'metadata': dict,
            'tiles': list
        })
        if body is None: return error
        _require_auth(body)

        user_id = body['user_id']
        rover_id = body['rover_id']
        target_id = body['target_id']
        classified = body['classified']
        arrival_time = body['arrival_time']
        new_scene = scene.from_struct(body['images'])
        metadata = body['metadata']

        with db.conn(request) as ctx:
            user = user_module.user_from_context(ctx, user_id)
            target = user.rovers[rover_id].targets[target_id]
            # Mark the target as processed and add the target images. Also issue a future
            # chip to make this target available on the client when arrival_time has been reached
            target.mark_processed_with_scene(new_scene, metadata=metadata, classified=classified)
            # Add each user map tile to the database and issue future chips to be
            # delivered at arrival_time
            for tile in body['tiles']:
                maptile.create_new_maptile(ctx, user,
                    tile['zoom'], tile['x'], tile['y'], arrival_time)

        return json_success({'status': 'ok'})

def _require_auth(body):
    auth_token = body['auth']
    assert auth_token == AUTH_TOKEN
