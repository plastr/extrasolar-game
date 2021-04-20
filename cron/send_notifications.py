# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Intended to be run from a cronjob, this script will send email alert notifications which are now due.
import os, sys, optparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from front import read_config_and_init
from front.lib import db, gametime, locking
from front.lib.exceptions import notify_on_exception
from front.backend import notifications

import logging
logger = logging.getLogger('front.cron.send_notifications')

ALERT_TYPES = {
    'activity_alerts': (notifications.send_activity_alert_at,
                        notifications.send_activity_alert_email_callback,
                        'SEND_NOTIFICATIONS_ACTIVITY_ALERTS'),
    'lure_alerts':     (notifications.send_lure_alert_at,
                        notifications.send_lure_alert_email_callback,
                        'SEND_NOTIFICATIONS_LURE_ALERTS')
}
ALERT_TYPES_HELP = ", ".join(ALERT_TYPES.keys())

def send_notifications(ctx, alert_type, at_time):
    alert_function, alert_callback, lock_name = ALERT_TYPES[alert_type]
    try:
        with locking.acquire_db_lock_if_unlocked(ctx, lock_name):
            return alert_function(ctx, at_time=at_time, notify_activity_callback=alert_callback, continue_on_fail=True)
    except (locking.LockAlreadyLocked, locking.LockTimeoutError):
        # No alerts processed.
        return 0

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = optparse.OptionParser(usage="%prog <deployment> <alert_type>\nAlert types: " + ALERT_TYPES_HELP)
    opts, args = optparser.parse_args(argv)

    if len(args) != 2:
        optparser.print_help()
        return

    deployment = args[0]
    if deployment is None:
        optparser.error("Please specify deployment name, e.g. development or live")

    alert_type = args[1]
    if alert_type is None:
        optparser.error("Please specify alert type: " + ALERT_TYPES_HELP)
    if alert_type not in ALERT_TYPES:
        optparser.error("Unknown alert type: " + alert_type)

    with notify_on_exception():
        with db.commit_or_rollback(read_config_and_init(deployment)) as ctx:
            send_notifications(ctx, alert_type, at_time=gametime.now())

if __name__ == "__main__":
    main(sys.argv[1:])
