from front.lib.db import setup_migration_cursor

from front.backend import deferred

FIELDS = ['deferred_id', 'user_id', 'deferred_type', 'subtype', 'created', 'run_at', 'payload']
def forward(conn):
    cursor = setup_migration_cursor(conn)
    cursor2 = setup_migration_cursor(conn)

    cursor.execute("SELECT " + ",".join(FIELDS) + " FROM deferred WHERE deferred_type='TARGET_ARRIVED' ORDER BY run_at")
    for r in cursor.fetchall():
        params = dict([(f, r[idx]) for idx, f in enumerate(FIELDS)])
        def_row = deferred.DeferredRow(**params)
        # Skip any rows already migrated.
        if def_row.payload is None:
            continue
        target_id_subtype = str(def_row.payload['target_id']).replace('-', '')
        hex_deferred_id = str(def_row.deferred_id).replace('-', '')

        # If there is already a new format deferred row to run on arrival for this target, delete the duplicate row.
        cursor2.execute("SELECT COUNT(*) FROM deferred WHERE deferred_type='TARGET_ARRIVED' AND subtype='%s'" % target_id_subtype)
        count = cursor2.fetchall()[0][0]
        if count > 0:
            cursor2.execute("DELETE FROM deferred WHERE deferred_id=unhex('%s')" % hex_deferred_id)
        # Otherwise, update the subtype value to contain the target_id which is the new schema for these rows.
        else:
            # NOTE: Not clearing payload as a safety precaution in case we need to try and reverse this in production.
            # These migrated rows with the extra payload information will be deleted when the deferred row is run.
            cursor2.execute("UPDATE deferred SET subtype='%s' WHERE deferred_id=unhex('%s')" % (target_id_subtype, hex_deferred_id))

def reverse(conn):
    # Cannot be reversed as original subtype data is lost.
    pass

step(forward, reverse)
