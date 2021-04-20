from front.lib.db import setup_migration_cursor

def forward(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("ALTER TABLE targets ADD COLUMN render_at datetime NOT NULL")

    # Set all the existing targets render_at times to be the start_time of each target converted to UTC
    # using the user's epoch.
    cursor.execute("UPDATE targets SET render_at=(SELECT epoch + INTERVAL start_time SECOND FROM users WHERE targets.user_id=users.user_id LIMIT 1)")

def reverse(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("ALTER TABLE targets DROP COLUMN render_at")

step(forward, reverse)
