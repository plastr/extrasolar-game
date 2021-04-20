# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Intended to be run from a cronjob, this script will vacuum/delete old chips.
import os, sys, optparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from datetime import timedelta

from front import read_config_and_init
from front.lib import db, gametime, utils, locking
from front.lib.exceptions import notify_on_exception

# Delete chips older than this number of hours ago.
DELETE_SINCE_HOURS = 1

LOCK_NAME = 'VACUUM_OLD_CHIP'
def vacuum_chips(ctx, since):
    try:
        with locking.acquire_db_lock_if_unlocked(ctx, LOCK_NAME):
            with db.conn(ctx) as ctx:
                db.run(ctx, 'chips/delete_chips_since', since=utils.usec_db_from_dt(since))
    except (locking.LockAlreadyLocked, locking.LockTimeoutError):
        return

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

    with notify_on_exception():
        with db.commit_or_rollback(read_config_and_init(deployment)) as ctx:
            since = gametime.now() - timedelta(hours=DELETE_SINCE_HOURS)
            vacuum_chips(ctx, since=since)

if __name__ == "__main__":
    main(sys.argv[1:])
