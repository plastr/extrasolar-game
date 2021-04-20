from front.lib.db import setup_migration_cursor

def forward(conn):
    # Any player who has tagged any obelisk (species_id 15728672) should have the PRO_TAGGED_ONE_OBELISK progress key set.
    cursor = setup_migration_cursor(conn)
    cursor.execute("SELECT hex(user_id), detected_at FROM species WHERE species_id=0xf00020")
    for r in cursor.fetchall():
        user_id     = r[0]
        achieved_at = r[1]
        cursor.execute("INSERT INTO users_progress (user_id, users_progress.key, value, achieved_at) VALUES (unhex('%s'), 'PRO_TAGGED_ONE_OBELISK', '', %d)" % (user_id, achieved_at))

def reverse(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("DELETE FROM users_progress WHERE users_progress.key='PRO_TAGGED_ONE_OBELISK'")

step(forward, reverse)
