#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse

from front import read_config_and_init, debug
from front.lib import db, get_uuid
from front.models import user as user_module

def increment_user_invites_left(ctx, user, verbose=True):
    before = user.invites_left
    user.increment_invites_left()
    if verbose:
        print "%s: invites_left increased from %d to %d" % (user.email, before, user.invites_left)
    return user

def increment_all_users(ctx):
    count = 0
    for row in debug.get_all_user_ids(ctx):
        user_id = get_uuid(row['user_id'])
        user = user_module.user_from_context(ctx, user_id)
        increment_user_invites_left(ctx, user)
        count += 1
    return count

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog [user_email] [--all]")
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development.",
    )
    optparser.add_option(
        "", "--all", dest="increment_all", action="store_true", default=False,
        help="Increment the invites_left count of the users currently in the database.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if not opts.increment_all and len(args) < 1:
        optparser.print_help()
        return

    # Either we have an email address to restart or we are restarting all users.
    config = read_config_and_init(opts.deployment)
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            if len(args) == 1:
                user = debug.get_user_by_email(ctx, args[0])
                if user is None:
                    print "No user with email", args[0]
                    return
                increment_user_invites_left(ctx, user)
            elif opts.increment_all:
                count = increment_all_users(ctx)
                print "Total of %d users incremented." % count
            else:
                optparser.print_help()
                return

if __name__ == "__main__":
    main(sys.argv[1:])
