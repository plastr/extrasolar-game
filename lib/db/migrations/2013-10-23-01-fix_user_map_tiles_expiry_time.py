import collections
from datetime import timedelta

from front.lib import utils
from front.lib.db import setup_migration_cursor
from front.models import maptile

def forward(conn):
    cursor = setup_migration_cursor(conn)

    # Migrate all existing user_map_tiles to conform to the invariant they always should had if not for bugs.
    # - All user map tiles for a given zoom,x,y should have the next tile's arrival_time as their expiry_time
    #   when sorted by arrival_time
    # - Except the last tile, which should have NULL as its expiry_time.
    # This code was adapted to work outside of the normal database context/named queries from similar
    # code now in map_tile.create_new_maptile

    # Ignore updated and created fields.
    cursor.execute("SELECT zoom, x, y, arrival_time, expiry_time, user_map_tiles.user_id, epoch FROM user_map_tiles, users WHERE user_map_tiles.user_id=users.user_id ORDER BY arrival_time")
    all_users_epochs = {}
    all_users_tiles = collections.defaultdict(lambda : collections.defaultdict(list))
    # Load all of the map tiles for all users, and decode them into MapTileRow objects. Place them into
    # a dictionary keyed off of user_id and then the map tile key with a list of all tiles for that key sorted
    # by arrival_time.
    for r in cursor.fetchall():
        tile = maptile.MapTileRow(zoom=r[0], x=r[1], y=r[2], arrival_time=r[3], expiry_time=r[4], user_id=r[5])
        all_users_tiles[tile.user_id][tile.tile_key].append(tile)
        # Also track the user's epoch too
        all_users_epochs[tile.user_id] = r[6]

    # Iterate through each user in turn, and then each of their tile keys.
    for user_id, user_tiles in all_users_tiles.iteritems():
        user_epoch = all_users_epochs[user_id]
        # For each tile_key, iterate through every tile for that key sorted by arrival_time.
        for tile_key, all_map_tiles in user_tiles.iteritems():
            for this_tile, next_tile in zip(all_map_tiles[:-1], all_map_tiles[1:]):
                # Verify that the order of the tiles has been maintained.
                assert this_tile.arrival_time < next_tile.arrival_time
                # If any tile but the last one has no expiry_time or it has the incorrect expiry_time, fix it.
                expiry_time_epoch = tile_expiry_time_epoch(this_tile, user_epoch)
                if expiry_time_epoch is None or expiry_time_epoch != next_tile.arrival_time:
                    tile_expire_at(cursor, this_tile, after_epoch_as_datetime(user_epoch, next_tile.arrival_time))

            # The last tile's expiry_time must be NULL. If all of the previous code is working correctly this
            # block should never run so it is acting as an invariant enforcement instead of having an assertion.
            last_tile = all_map_tiles[-1]
            if last_tile.expiry_time is not None:
                tile_expire_at(cursor, last_tile, None)

def tile_expiry_time_epoch(tile, epoch):
    if tile.expiry_time is None: return None
    return utils.seconds_between_datetimes(epoch, tile.expiry_time)

def tile_expire_at(cursor, tile, expiry_time):
    expiry_time_str = "'"+expiry_time.isoformat(' ')+"'" if expiry_time is not None else "NULL"
    cursor.execute("UPDATE user_map_tiles SET expiry_time=%s WHERE user_id=UNHEX('%s') AND zoom=%d AND x=%d AND y=%d AND arrival_time=%d" %
        (expiry_time_str, str(tile.user_id).replace('-', ''), tile.zoom, tile.x, tile.y, tile.arrival_time))
    tile.expiry_time = expiry_time  # Make our state mirror the database's.

def after_epoch_as_datetime(epoch, seconds_after_epoch):
    return epoch + timedelta(seconds=seconds_after_epoch)

def reverse(conn):
    # Cannot be reversed
    pass

step(forward, reverse)
