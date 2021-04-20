# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Intended to be run from a cronjob, this script will run all deferred actions which are now due.
import os, sys, optparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from front import read_config_and_init
from front.lib import db, gametime, locking
from front.lib.exceptions import notify_on_exception
from front.backend import deferred

import logging
logger = logging.getLogger('front.cron.run_deferred_actions')

LOCK_NAME = 'RUN_DEFERRED_ACTIONS'
def run_deferred_actions(ctx, since):
    try:
        with locking.acquire_db_lock_if_unlocked(ctx, LOCK_NAME):
            return deferred.run_deferred_since(ctx, since)
    except (locking.LockAlreadyLocked, locking.LockTimeoutError):
        # No deferreds run.
        return 0

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
            run_deferred_actions(ctx, since=gametime.now())

if __name__ == "__main__":
    main(sys.argv[1:])
