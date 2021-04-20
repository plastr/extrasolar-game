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
    optparser = optparse.OptionParser(usage="%prog email_or_id")
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development.",
    )
    optparser.add_option(
        "", "--auth", dest="auth", default="PASS",
        help="Set the authorization type to search on. PASS, EDMO, or FB. By default, auth=PASS, search by email.",
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

    # Delete the provided user by email address.
    config = read_config_and_init(opts.deployment)
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            if opts.auth == "PASS":
                user = debug.get_user_by_email(ctx, args[0])
            elif opts.auth == "FB":
                user = debug.get_user_by_facebook_uid(ctx, args[0])
            elif opts.auth == "EDMO":
                user = debug.get_user_by_edmodo_uid(ctx, args[0])
            else:
                print "Unrecognized auth type", opts.auth
                return
            if user is None:
                print "No user matching search string %s, auth type %s." % (args[0], opts.auth)
                return

            answer = raw_input("Are you sure you want to delete this user [%s] and all their data? (yes/no) " % user.email)
            if not answer == "yes":
                print "Aborting process."
                return

            debug.delete_user_and_data(ctx, user.user_id, include_user_table=True)

if __name__ == "__main__":
    main(sys.argv[1:])
