# Copyright (c) 2014 Lazy 8 Studios, LLC.
# All rights reserved.
# Intended to be run from a cronjob, this script deletes certain types of old target metadata
# that is only used for assessing render performance (TGT_RDR_*).
import os, sys, optparse
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from front import read_config_and_init
from front.lib import db
from front.lib.locking import acquire_db_lock
from front.lib.exceptions import notify_on_exception

# The threshold, before which old target metadata should be deleted.
CLEANUP_THRESHOLD_DAYS = 30
RENDER_METADATA_PREFIX = "TGT_RDR_%"
LOCK_NAME = 'CLEANUP_TARGET_METADATA'

def delete_target_render_metadata(ctx):
    '''
    Delete old target metadata with keys starting with TGT_RDR_.
    '''
    with acquire_db_lock(ctx, LOCK_NAME, 30):
        with db.conn(ctx) as ctx:
            db.run(ctx, 'delete_target_render_metadata_older_than', days=CLEANUP_THRESHOLD_DAYS, match=RENDER_METADATA_PREFIX)

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
            delete_target_render_metadata(ctx)


if __name__ == "__main__":
    main(sys.argv[1:])
