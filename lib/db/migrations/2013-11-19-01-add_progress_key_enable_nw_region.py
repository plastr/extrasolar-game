from front.lib.db import setup_migration_cursor

def forward(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("SELECT hex(user_id), sent_at FROM messages WHERE msg_type='MSG_OBELISK03a'")
    for r in cursor.fetchall():
        user_id = r[0]
        sent_at = r[1]
        cursor.execute("INSERT INTO users_progress (user_id, users_progress.key, value, achieved_at) VALUES (unhex('%s'), 'PRO_ENABLE_NW_REGION', '', %d)" % (user_id, sent_at))

def reverse(conn):
    cursor = setup_migration_cursor(conn)
    cursor.execute("DELETE FROM users_progress WHERE users_progress.key='PRO_ENABLE_NW_REGION'")

step(forward, reverse)
