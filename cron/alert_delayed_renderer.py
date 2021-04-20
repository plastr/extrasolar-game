# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Intended to be run from a cronjob, this script will alert admins if the target renderer queue is backed up.
import os, sys, optparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from datetime import timedelta

from front import read_config_and_init, VERSION
from front.lib import db, gametime, email_module
from front.lib.exceptions import notify_on_exception
from front.lib.locking import acquire_db_lock

# Alert on targets which have been unprocessed and were created more than this number of minutes ago.
ALERT_PROCESSED_MINUTES = 30

# The email template name used when composing the alert email.
TEMPLATE_NAME = "EMAIL_ALERT_UNPROCESSED_TARGETS"

LOCK_NAME = 'ALERT_DELAYED_RENDERER'
def alert_unprocessed_targets_before(ctx, render_after, email_address):
    '''
    Return a list of {target_id, render_at} target data for any picture target that is unprocessed and whose render_at
    time is earlier than the supplied datetime.
    '''
    # NOTE: Intentionally not wrapping this in acquire_db_lock_if_unlocked. If this process gets deadlocked in
    # production notification of the timeouts acquiring the lock is desired.
    with acquire_db_lock(ctx, LOCK_NAME, 30):
        with db.conn(ctx) as ctx:
            rows = db.rows(ctx, 'select_unprocessed_targets_older_than', render_after=render_after)

    # No unprocessed targets, do nothing.
    if len(rows) == 0:
        return rows

    template_data = {
        'gametime': gametime.now(),
        'version': VERSION,
        'hostname': os.uname()[1],
        'target_count': len(rows),
        'unprocessed_minutes': ALERT_PROCESSED_MINUTES
    }
    email_module.send_alarm(email_address, TEMPLATE_NAME, template_data=template_data)
    return rows

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = optparse.OptionParser(usage="%prog <deployment>")
    opts, args = optparser.parse_args(argv)

    if len(args) == 0:
        optparser.print_help()
        return

    deployment = args[0]
    if deployment is None:
        optparser.error("Please specify deployment name, e.g. development or live")

    conf = read_config_and_init(deployment)
    if conf['developer_email_address'] == "DISABLED":
        print "Refusing to run as developer_email_address is DISABLED in deployment config .ini"
        return

    with notify_on_exception():
        with db.commit_or_rollback(conf) as ctx:
            render_after = gametime.now() - timedelta(minutes=ALERT_PROCESSED_MINUTES)
            alert_unprocessed_targets_before(ctx, render_after, conf['developer_email_address'])


if __name__ == "__main__":
    main(sys.argv[1:])
