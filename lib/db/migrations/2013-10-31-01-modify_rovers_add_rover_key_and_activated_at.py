from front.lib.db import setup_migration_cursor

from front import rover_keys

def forward(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("ALTER TABLE rovers ADD COLUMN rover_key char(32) NOT NULL")
    cursor.execute("ALTER TABLE rovers ADD COLUMN activated_at int(10) unsigned NOT NULL")

    # Set all the existing rover activated_at times to be the start_time of each rover's first target.
    cursor.execute("UPDATE rovers SET activated_at=(SELECT start_time FROM targets WHERE targets.rover_id=rovers.rover_id ORDER BY start_time LIMIT 1)")

    # Set all of the rover_key values by iterating through every rover grouped by user_id and sorted by the rover
    # creation time. Lookup the rover_key in the rover_keys constant by index.
    cursor.execute("SELECT hex(user_id), hex(rover_id), created FROM rovers ORDER BY user_id, created")
    current_user_id = None
    rover_index = 0
    for r in cursor.fetchall():
        user_id = r[0]
        rover_id = r[1]
        if current_user_id != user_id:
            current_user_id = user_id
            rover_index = 0
        else:
            rover_index += 1
        rover_key = rover_keys.ALL[rover_index]
        cursor.execute("UPDATE rovers SET rover_key='%s' WHERE rovers.rover_id=unhex('%s')" % (rover_key, rover_id))

def reverse(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("ALTER TABLE rovers DROP COLUMN rover_key")
    cursor.execute("ALTER TABLE rovers DROP COLUMN activated_at")

step(forward, reverse)
