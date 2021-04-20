# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import models, Constants
from front.lib import db, gametime, get_uuid, utils
from front.models import chips

def create_new_maptile(ctx, user, zoom, x, y, arrival_time):
    """
    This creates a new MapTile object and persists it. These are used to describe custom
    map tiles that should be displayed for a User's rover path. If the User already has
    a map file for the given zoom, x and y, it will be updated to point at the new
    arrival_time and the old DB record will be flagged to be expired.
    Given the fact that this might be creating data that is hidden from the gamestate until the future,
    no MapTile object is returned from the function.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param zoom: int The zoom level for this map tile.
    :param x: int The horizontal placement for this map tile.
    :param y: int The vertical placement for this map tile.
    :param arrival_time: int When the user's rover will arrive at this tile. Essentially,
    when this tile should be displayed on the user's map. Seconds since user.epoch
    """
    params = {}
    params['zoom'] = zoom
    params['x'] = x
    params['y'] = y
    params['arrival_time'] = arrival_time
    params['user_id'] = user.user_id

    with db.conn(ctx) as ctx:
        # Deliver any chips at the arrival time of the target with a little padding to be sure it is available
        # within the fetch chips time polling window.
        deliver_at = user.after_epoch_as_datetime(arrival_time - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # The tile key is the zoom level and x,y coordinates.
        tile_key = make_tile_key(zoom, x, y)
        # Lost the list of all map tiles defined for this x,y,zoom tile
        all_map_tiles = user.all_map_tiles[tile_key]

        # If there are no existing tiles, then this is the first one. Insert it into the database and issue an ADD chip.
        if len(all_map_tiles) == 0:
            # Set expiry_time to NULL as this is the first tile.
            params['expiry_time'] = None
            # Create the MapTileRow instance and add it to the all_map_tiles list.
            new_tile = MapTileRow(**params)
            all_map_tiles.append(new_tile)
            # Insert the tile into the database.
            db.run(ctx, "insert_user_map_tile", created=gametime.now(), **params)
            # Send a future ADD chip with the new map tile delivered at the arrival_time.
            chips.add_in_future(ctx, user, user.map_tiles, deliver_at=deliver_at, **params)
            return

        # Determine if the tile key at arrival_time already exists. If so, this is an already created target
        # being reprocessed in which case do nothing.
        found = [t for t in all_map_tiles if t.arrival_time == arrival_time]
        # Due to a database constraint, there can never be more than one tile at a given zoom,x,y,arrival_time
        # so the one existing tile has been found.
        if len(found) > 0:
            assert len(found) == 1
            # This existing tile is for a target that is being reprocessed, do nothing.
            return

        # Otherwise, this must be a new target in an area with existing tiles.
        # Create a new MapTileRow object for this new tile being added and set its expiry_time.
        newer_tiles = [t for t in all_map_tiles if t.arrival_time > arrival_time]
        # If there are no tiles newer than this one, then its expiry_time is NULL. Otherwise, its expiry_time
        # is the tile that is next newest.
        if len(newer_tiles) == 0:
            params['expiry_time'] = None
        else:
            params['expiry_time'] = user.after_epoch_as_datetime(newer_tiles[0].arrival_time)
        # Determine what tiles have not been arrived at before modifying the all_map_tiles
        unarrived_tiles = [t for t in all_map_tiles if t.arrival_time > user.epoch_now]
        # This will be True if all existing tiles have not yet been arrived at.
        are_all_tiles_unarrived = (len(unarrived_tiles) == len(all_map_tiles))

        # Insert the new MapTileRow it into the correct location in the user.all_map_tiles list, which might be
        # at the end of the list if there are no newer tiles.
        new_tile = MapTileRow(**params)
        all_map_tiles.insert(len(all_map_tiles)-len(newer_tiles), new_tile)

        # Insert the new tile into the database.
        db.run(ctx, "insert_user_map_tile", created=gametime.now(), **params)

        # If all of the existing tiles have not yet been arrived at (for instance if there are only future targets
        # that affect this tile key location), then need to issue an ADD for this tile even if an ADD has already been
        # sent because the client won't necessarily have an existing model object to merge a MOD into. The client side
        # chips code always merges an ADD if the chip path points at an existing model as this is how the client
        # id being set to the server id system works.
        if are_all_tiles_unarrived:
            # Send a future ADD chip with the new map tile delivered at the arrival_time.
            chips.add_in_future(ctx, user, user.map_tiles, deliver_at=deliver_at, **params)

        # Otherwise there is an existing tile for this tile key already on the client and issue a MOD to change
        # that tile's arrival_time when this new tile becomes available.
        else:
            # There might not be a visible tile in the gamestate map_tiles collection (if the tile/target has not
            # been arrived at) so create a dummy instance used only to issue the MOD chip to the correct path.
            dummy_tile = user.map_tiles.model_class.create(**params)
            # Silently set the model's collection so the chip path is correct. Does not add the model to the collection.
            dummy_tile._set_parent(user.map_tiles)
            # Send a future MOD chip with the new arrival_time tile time delivered at the padded arrival_time.
            new_params = {'arrival_time':arrival_time}
            chips.modify_in_future(ctx, user, dummy_tile, deliver_at=deliver_at, **new_params)

        # Enforce that every tile that isn't the last tile's expiry_time is the next tile's arrival_time.
        # This might be required if the target for the tile just created is not the last target or if there
        # are a number of future targets not yet arrived at that have tiles at this same location.
        for this_tile, next_tile in zip(all_map_tiles[:-1], all_map_tiles[1:]):
            # Verify that the order of the tiles has been maintained.
            assert this_tile.arrival_time < next_tile.arrival_time
            # If any tile but the last one has no expiry_time or it has the incorrect expiry_time, fix it.
            expiry_time_epoch = this_tile.expiry_time_epoch(user)
            if expiry_time_epoch is None or expiry_time_epoch != next_tile.arrival_time:
                this_tile.expire_at(ctx, user.after_epoch_as_datetime(next_tile.arrival_time))
        # The last tile's expiry_time must be NULL. If all of the previous code is working correctly this
        # block should never run so it is acting as an invariant enforcement instead of having an assertion.
        last_tile = all_map_tiles[-1]
        if last_tile.expiry_time is not None:
            last_tile.expire_at(ctx, None)
        return

def make_tile_key(zoom, x, y):
    return "%d,%d,%d" % (zoom, x, y)

class MapTile(chips.Model, models.UserChild):
    """
    Holds the parameters for a single user's current custom map tile.
    Lives in the gamestate in the user.maptiles collection.
    """
    id_field = 'tile_key'
    fields = frozenset(['zoom', 'x', 'y', 'arrival_time', 'expiry_time'])
    computed_fields = {
        'arrival_time_date': models.EpochDatetimeField('arrival_time')
    }
    server_only_fields = frozenset(['expiry_time'])

    # user_id, created and updated are database only fields.
    def __init__(self, user_id=None, created=None, updated=None, **params):
        tile_key = make_tile_key(params['zoom'], params['x'], params['y'])
        super(MapTile, self).__init__(tile_key=tile_key, **params)

    @property
    def user(self):
        # self.parent is user.map_tiles, the parent of that is the User itself
        return self.parent.parent

class MapTileRow(object):
    """
    Holds the parameters for a single user's custom map tile.
    Meant to hold map tile data in the user.all_map_tile field, which is not a chip Collection and
    is not in the gamestate.
    """
    fields = frozenset(['tile_key', 'zoom', 'x', 'y', 'arrival_time', 'expiry_time', 'user_id'])
    def __init__(self, created=None, updated=None, **row):
        for field in self.fields:
            if field  == 'user_id':
                value = get_uuid(row[field])
            elif field == "tile_key":
                value = make_tile_key(row['zoom'], row['x'], row['y'])
            else:
                value = row[field]
            setattr(self, field, value)

    def expiry_time_epoch(self, user):
        if self.expiry_time is None: return None
        return utils.seconds_between_datetimes(user.epoch, self.expiry_time)

    def expire_at(self, ctx, expiry_time):
        with db.conn(ctx) as ctx:
            db.run(ctx, "update_user_map_tile_expire_previous", user_id=self.user_id,
                   zoom=self.zoom, x=self.x, y=self.y,
                   expiry_time=expiry_time, arrival_time=self.arrival_time)
            self.expiry_time = expiry_time  # Make our state mirror the database's.

    def __repr__(self):
        return '(%s)(%s)' % (self.tile_key, self.arrival_time)
