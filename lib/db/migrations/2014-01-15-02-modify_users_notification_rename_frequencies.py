from front.lib.db import setup_migration_cursor

from front import activity_alert_types

def forward(conn):
    cursor = setup_migration_cursor(conn)

    # Rename the previous INSTANT and DIGEST keys to be MEDIUM and LONG
    cursor.execute('UPDATE users_notification SET activity_alert_frequency="%s" WHERE activity_alert_frequency="INSTANT"' % activity_alert_types.MEDIUM)
    cursor.execute('UPDATE users_notification SET activity_alert_frequency="%s" WHERE activity_alert_frequency="DIGEST"' % activity_alert_types.LONG)

def reverse(conn):
    cursor = setup_migration_cursor(conn)

    cursor.execute('UPDATE users_notification SET activity_alert_frequency="INSTANT" WHERE activity_alert_frequency="%s"' % activity_alert_types.MEDIUM)
    cursor.execute('UPDATE users_notification SET activity_alert_frequency="DIGEST" WHERE activity_alert_frequency="%s"' % activity_alert_types.LONG)

step(forward, reverse)
