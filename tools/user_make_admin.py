#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse

from front import read_config_and_init, debug
from front.lib import db

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog user_email")
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if len(args) < 1:
        optparser.print_help()
        return

    # Make the provided user an admin by email address.
    config = read_config_and_init(opts.deployment)
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            user = debug.get_user_by_email(ctx, args[0])
            if user is None:
                print "No user with email", args[0]
                return

            debug.make_user_admin_by_id(ctx, user.user_id)
            print "User is now an admin [%s]" % user.email

if __name__ == "__main__":
    main(sys.argv[1:])
