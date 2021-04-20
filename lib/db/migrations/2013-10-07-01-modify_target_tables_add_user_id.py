from front.lib.db import setup_migration_cursor

def forward(conn):
    cursor = setup_migration_cursor(conn)

    # Add the user_id column to the targets and target data tables. Also add indexes as appropriate.
    cursor.execute("ALTER TABLE targets ADD COLUMN user_id binary(16) NOT NULL")
    cursor.execute("ALTER TABLE targets ADD KEY user_id (user_id)")
    cursor.execute("ALTER TABLE targets ADD KEY rover_id (rover_id)")
    cursor.execute("ALTER TABLE target_sounds ADD COLUMN user_id binary(16) NOT NULL")
    cursor.execute("ALTER TABLE target_sounds ADD KEY user_id (user_id)")
    cursor.execute("ALTER TABLE target_image_rects ADD COLUMN user_id binary(16) NOT NULL")
    cursor.execute("ALTER TABLE target_image_rects ADD KEY user_id (user_id)")
    cursor.execute("ALTER TABLE target_images ADD COLUMN user_id binary(16) NOT NULL")
    cursor.execute("ALTER TABLE target_images ADD KEY user_id (user_id)")
    cursor.execute("ALTER TABLE target_metadata ADD COLUMN user_id binary(16) NOT NULL")
    cursor.execute("ALTER TABLE target_metadata ADD KEY user_id (user_id)")

    # Initialize all existing targets and target data tables to have the correct user_id values.
    cursor.execute("SELECT HEX(rovers.user_id), HEX(target_id) FROM targets, rovers WHERE targets.rover_id=rovers.rover_id")
    for r in cursor.fetchall():
        cursor.execute("UPDATE targets SET user_id=UNHEX('%s') WHERE target_id=UNHEX('%s')" % (r[0], r[1]))
        cursor.execute("UPDATE target_sounds SET user_id=UNHEX('%s') WHERE target_id=UNHEX('%s')" % (r[0], r[1]))
        cursor.execute("UPDATE target_image_rects SET user_id=UNHEX('%s') WHERE target_id=UNHEX('%s')" % (r[0], r[1]))
        cursor.execute("UPDATE target_images SET user_id=UNHEX('%s') WHERE target_id=UNHEX('%s')" % (r[0], r[1]))
        cursor.execute("UPDATE target_metadata SET user_id=UNHEX('%s') WHERE target_id=UNHEX('%s')" % (r[0], r[1]))

def reverse(conn):
    cursor = setup_migration_cursor(conn)

    # Remove the user_id fields and indexes.
    cursor.execute("ALTER TABLE targets DROP KEY user_id")
    cursor.execute("ALTER TABLE targets DROP KEY rover_id")
    cursor.execute("ALTER TABLE targets DROP COLUMN user_id")
    cursor.execute("ALTER TABLE target_sounds DROP KEY user_id")
    cursor.execute("ALTER TABLE target_sounds DROP COLUMN user_id")
    cursor.execute("ALTER TABLE target_image_rects DROP KEY user_id")
    cursor.execute("ALTER TABLE target_image_rects DROP COLUMN user_id")
    cursor.execute("ALTER TABLE target_images DROP KEY user_id")
    cursor.execute("ALTER TABLE target_images DROP COLUMN user_id")
    cursor.execute("ALTER TABLE target_metadata DROP KEY user_id")
    cursor.execute("ALTER TABLE target_metadata DROP COLUMN user_id")

step(forward, reverse)
