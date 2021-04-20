# We moved MIS_MONUMENT_PLAYBACK to be kicked off earlier, when MSG_BACKb is sent rather than
# when MSG_MISSION04a is sent.  MIS_MONUMENT_PLAYBACK now has 2 sub-missions.
#
# For players who have unlocked message MSG_BACKb but who don't already have mission MIS_MONUMENT_PLAYBACK:
# Add mission MIS_MONUMENT_PLAYBACK and its sub-missions.  Part a should be marked as done only
# if MSG_OBELISK06a has been queued or sent.  Part b should not be marked as not done.  
#
# For players who already have MIS_MONUMENT_PLAYBACK, add database entries for the sub-missions.
# MIS_MONUMENT_PLAYBACKa should be marked done if MSG_OBELISK06a has been queued or sent.
# MIS_MONUMENT_PLAYBACKb should be marked done if MIS_MONUMENT_PLAYBACK was marked done.

import uuid
from front.lib.db import setup_migration_cursor

def forward(conn):
    cursor  = setup_migration_cursor(conn)
    cursor2 = setup_migration_cursor(conn)

    # ONLY ALLOW THIS MIGRATION TO RUN IF THERE AREN'T ANY QUEUED MESSAGES OF TYPE MSG_OBELISK06a
    # If we can avoid this condition, it simplifies the migration.
    cursor.execute("SELECT count(*) FROM deferred WHERE subtype='MSG_OBELISK06a'")
    assert cursor.fetchone()[0] == 0

    # Select all users who have unlocked MSG_BACKb.  All these users should now have MIS_MONUMENT_PLAYBACK.
    cursor.execute("SELECT HEX(user_id), sent_at FROM messages WHERE msg_type='MSG_BACKb' and locked=0")
    for r in cursor.fetchall():
        # Get all the info we need to customize the migration for this user.
        user_id              = r[0]
        mission_started_at   = r[1]
        submission_a_done_at = None
        submission_b_done_at = None
        should_create_parent_mission = True

        # Does this player already have a MIS_MONUMENT_PLAYBACK?
        cursor2.execute("SELECT done_at FROM missions WHERE user_id=UNHEX('%s') AND mission_definition='MIS_MONUMENT_PLAYBACK'" % (user_id))
        row = cursor2.fetchone();
        if row:
            submission_b_done_at = row[0]
            should_create_parent_mission = False
            
        # Has the player received MSG_OBELISK06a?
        cursor2.execute("SELECT sent_at FROM messages WHERE user_id=UNHEX('%s') AND msg_type='MSG_OBELISK06a'" % (user_id))
        row = cursor2.fetchone();
        if row:
            submission_a_done_at = row[0]

        submission_a_done = 0 if submission_a_done_at == None else 1
        submission_b_done = 0 if submission_b_done_at == None else 1

        # If needed, create the parent mission.
        if should_create_parent_mission:
            cursor2.execute("""
                INSERT INTO missions (user_id, mission_definition, specifics_hash, specifics, done, started_at,
                parent_hash, done_at, viewed_at, created) VALUES (UNHEX('%s'), 'MIS_MONUMENT_PLAYBACK', '99914b932bd37a50b983c5e7c90ae93b',
                '{}', %d, %d, '', %s, NULL, NOW())
                """ % (user_id, submission_b_done, mission_started_at, ('NULL' if submission_b_done_at == None else str(submission_b_done_at))))

        # Create the child missions.
        cursor2.execute("""
            INSERT INTO missions (user_id, mission_definition, specifics_hash, specifics, done, started_at,
            parent_hash, done_at, viewed_at, created) VALUES (UNHEX('%s'), 'MIS_MONUMENT_PLAYBACKa', '99914b932bd37a50b983c5e7c90ae93b',
            '{}', %d, %d, '99914b932bd37a50b983c5e7c90ae93b', %s, NULL, NOW())
            """ % (user_id, submission_a_done, mission_started_at, ('NULL' if submission_a_done_at == None else str(submission_a_done_at))))
        cursor2.execute("""
            INSERT INTO missions (user_id, mission_definition, specifics_hash, specifics, done, started_at,
            parent_hash, done_at, viewed_at, created) VALUES (UNHEX('%s'), 'MIS_MONUMENT_PLAYBACKb', '99914b932bd37a50b983c5e7c90ae93b',
            '{}', %d, %d, '99914b932bd37a50b983c5e7c90ae93b', %s, NULL, NOW())
            """ % (user_id, submission_b_done, mission_started_at, ('NULL' if submission_b_done_at == None else str(submission_b_done_at))))

def reverse(conn):
    cursor  = setup_migration_cursor(conn)
    cursor2 = setup_migration_cursor(conn)
    
    # Get rid of the sub-missions.
    cursor.execute("DELETE FROM missions where mission_definition='MIS_MONUMENT_PLAYBACKa' OR mission_definition='MIS_MONUMENT_PLAYBACKb'")

    # Make sure that players who have not yet received MSG_MISSION04a don't have MIS_MONUMENT_PLAYBACK.
    cursor.execute("SELECT HEX(user_id) FROM missions WHERE mission_definition='MIS_MONUMENT_PLAYBACK' AND done=0")
    for r in cursor.fetchall():
        user_id = r[0]
        # Has the player received MSG_MISSION04a?
        cursor2.execute("SELECT count(*) FROM messages WHERE user_id=UNHEX('%s') AND msg_type='MSG_MISSION04a'" % (user_id))
        if cursor2.fetchone()[0] == 0:
            cursor.execute("DELETE FROM missions where user_id=UNHEX('%s') AND mission_definition='MIS_MONUMENT_PLAYBACK'" % (user_id))

step(forward, reverse)
