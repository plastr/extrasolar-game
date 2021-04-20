# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Intended to be run from a cronjob, this script will send all emails in the email queue.
import os, sys, optparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from front import read_config_and_init
from front.lib import db, locking
from front.lib.exceptions import notify_on_exception
from front.backend import email_queue

import logging
logger = logging.getLogger('front.cron.process_email_queue')

LOCK_NAME = 'PROCESS_EMAIL_QUEUE'
def process_email_queue(ctx):
    try:
        with locking.acquire_db_lock_if_unlocked(ctx, LOCK_NAME):
            return email_queue.process_email_queue(ctx)
    except (locking.LockAlreadyLocked, locking.LockTimeoutError):
        # No email processed.
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
            process_email_queue(ctx)

if __name__ == "__main__":
    main(sys.argv[1:])
