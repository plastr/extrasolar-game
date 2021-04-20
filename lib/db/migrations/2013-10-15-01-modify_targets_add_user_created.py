from front.lib.db import setup_migration_cursor

def forward(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("ALTER TABLE targets ADD COLUMN user_created tinyint(1) NOT NULL DEFAULT '0'")

    # For any existing target that is user created, toggle the default value from 0 to 1.
    # At the time this migration was created, the EPOCH_START_HOURS value is 30 hours, which is 108000 seconds.
    # So any target arriving after that time relative to the user's epoch and that is a picture was user created.
    # Technically is at least one picture target at the end of the game (distress photo) which is not user_created
    # but no one has reached that yet in production so going to ignore it.
    cursor.execute("UPDATE targets set user_created=1 WHERE picture=1 AND arrival_time > 108000")

def reverse(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("ALTER TABLE targets DROP COLUMN user_created")

step(forward, reverse)
