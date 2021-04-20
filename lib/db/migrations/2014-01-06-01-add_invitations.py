# For players who have already tagged their disassembled rover but haven't been given any invitations,
# add 3 free invitations.  We can trigger off of MIS_FIND_STUCK_ROVER.

import uuid
from front.lib.db import setup_migration_cursor

def forward(conn):
    cursor  = setup_migration_cursor(conn)
    cursor2 = setup_migration_cursor(conn)

    # ONLY ALLOW THIS MIGRATION TO RUN IF THERE AREN'T ANY QUEUED MESSAGES OF TYPE MSG_OBELISK06a
    # If we can avoid this condition, it simplifies the migration.
    cursor.execute("SELECT count(*) FROM deferred WHERE subtype='MSG_OBELISK06a'")
    assert cursor.fetchone()[0] == 0

    # Select all users who have already finished MIS_FIND_STUCK_ROVER.
    cursor.execute("SELECT HEX(user_id) FROM missions WHERE mission_definition='MIS_FIND_STUCK_ROVER' and done=1")
    for r in cursor.fetchall():
        # Get all the info we need to customize the migration for this user.
        user_id = r[0]

        # Has message MSG_INVITATIONSa already been queued or delivered?
        cursor2.execute("SELECT count(*) FROM deferred WHERE user_id=UNHEX('%s') AND subtype='MSG_INVITATIONSa'" % (user_id))
        if cursor2.fetchone()[0] != 0:
            continue

        cursor2.execute("SELECT count(*) FROM messages WHERE user_id=UNHEX('%s') AND msg_type='MSG_INVITATIONSa'" % (user_id))
        if cursor2.fetchone()[0] != 0:
            continue

        # Create a deferred action to send the message in 5 minutes (300 seconds)
        # The message's was_delivered callback will handle adding the invitations when sent.
        deferred_id = str(uuid.uuid1()).replace('-', '')  # Strip out the dashes.
        cursor2.execute(("""
            INSERT INTO deferred (deferred_id, user_id, deferred_type, subtype, run_at, created, payload)
            VALUES (UNHEX('%s'), UNHEX('%s'), 'MESSAGE', 'MSG_INVITATIONSa', NOW()+300, NOW(), NULL)
            """) % (deferred_id, user_id))

def reverse(conn):
    cursor  = setup_migration_cursor(conn)
    
    # Delete the deferred actions.
    cursor.execute("DELETE FROM deferred where deferred_type='MESSAGE' AND subtype='MSG_INVITATIONSa'")

step(forward, reverse)
