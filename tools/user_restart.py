#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse

from front import read_config_and_init, debug
from front.lib import db, get_uuid

def restart_user_by_id(ctx, user_id):
    print "Restarting user", user_id
    debug.restart_user_by_id(ctx, user_id)

def restart_all_users(ctx):
    for row in debug.get_all_user_ids(ctx):
        user_id = get_uuid(row['user_id'])
        restart_user_by_id(ctx, user_id)

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog [user_email] [--all]")
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development.",
    )
    optparser.add_option(
        "", "--all", dest="restart_all", action="store_true", default=False,
        help="Restart all of the users currently in the database.",
    )
    optparser.add_option(
        "", "--no_prompt", dest="no_prompt", action="store_true", default=False,
        help="Do not prompt for verification before deleting existing user.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if not opts.restart_all and len(args) < 1:
        optparser.print_help()
        return

    if not opts.no_prompt:
        answer = raw_input("Are you sure you want to restart these users, deleting existing data? (yes/no) ")
        if not answer == "yes":
            print "Aborting process."
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
                restart_user_by_id(ctx, user.user_id)
            elif opts.restart_all:
                restart_all_users(ctx)
            else:
                optparser.print_help()
                return

if __name__ == "__main__":
    main(sys.argv[1:])
