#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse

from front import read_config_and_init, debug
from front.lib import db, get_uuid, email_module
from front.models import user as user_module

def send_email_to_user(ctx, email_type, user):
    print "Sending email to", user.email
    email_module.send_now(ctx, user, email_type)

def send_to_all_users(ctx, email_type):
    for row in debug.get_all_user_ids(ctx):
        user_id = get_uuid(row['user_id'])
        user = user_module.user_from_context(ctx, user_id)
        send_email_to_user(ctx, email_type, user)

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog email_template [user_email] [--all]")
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development unless --live is provided.",
    )
    optparser.add_option(
        "", "--all", dest="send_to_all", action="store_true", default=False,
        help="Send email to all the users currently in the database.",
    )
    optparser.add_option(
        "", "--queue", dest="run_queue", action="store_true", default=False,
        help="This flag can be set in non-live mode to force the emails to go through the email_queue for testing.",
    )
    optparser.add_option(
        "", "--live", dest="run_live", action="store_true", default=False,
        help="This flag must be set to send actually send email using the live AWS system.",
    )
    optparser.add_option(
        "", "--no_prompt", dest="no_prompt", action="store_true", default=False,
        help="Do not prompt for verification before sending emails.",
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
    email_type = args[0]

    # If in live mode, prompt by default and set the deployment.
    if opts.run_live:
        if not opts.no_prompt:
            answer = raw_input("Are you sure you want to send email to these users? (yes/no) ")
            if not answer == "yes":
                print "Aborting process."
                return
        opts.deployment = 'live'

    # Read in the deployment configuration and configure the modules.
    config = read_config_and_init(opts.deployment)

    # Neuter the email sending system in dry run mode. Perform this after reading the deployment config
    # as this might override some settings.
    if not opts.run_live:
        if opts.run_queue:
            # The email queue can be flushed by running front/cron/process_email_queue.py from the commandline.
            print "** Running in dry-run/safe mode with email_queue enabled. No emails will be sent.\n"
            email_module.set_queue_dispatcher()
        else:
            print "** Running in dry-run/safe mode. No emails will be sent.\n"
            email_module.set_echo_dispatcher(quiet=False)

    # Either we have a single email address to send to or we are sending to all users.
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            if len(args) == 2:
                user = debug.get_user_by_email(ctx, args[1])
                if user is None:
                    print "No user with email", args[1]
                    return
                send_email_to_user(ctx, email_type, user)
            elif opts.send_to_all:
                send_to_all_users(ctx, email_type)
            else:
                optparser.print_help()
                return

if __name__ == "__main__":
    main(sys.argv[1:])
