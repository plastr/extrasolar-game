#!/usr/bin/env python
# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys, optparse
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

from yoyo.scripts import migrate

from front import read_config_and_init
from front.lib import db

DEFAULT_LOCATION = os.path.join(BASEDIR, "front/lib/db/migrations")

def run_migrations(config, location=DEFAULT_LOCATION, action="apply", create_database=False, no_prompt=False, verbose=True):
    dburi = "mysql://%s:%s@%s/%s" % (
        config['database.username'], config['database.password'],
        config['database.host'], config['database.name'])

    if create_database:
        if no_prompt:
            answer = 'yes'
        else:
            answer = raw_input("Are you sure you want to wipe and recreate the database? (yes/no) ")
        if answer == "yes":
            print "Destroying and creating database:", dburi
            db.destroy_database(config)
            db.create_database(config)
        else:
            raise Exception("Aborting process.")

    if verbose:
        print "Performing migrations on:", dburi
        verbosity_level = '2'
    else:
        verbosity_level = '0'
    # Apply forward migrations in batch mode, meaning no user prompting will occur.
    if no_prompt:
        migrate.main([action, location, dburi, '--batch', '--verbosity='+verbosity_level, '--no-cache'])
    else:
        migrate.main([action, location, dburi, '--verbosity='+verbosity_level, '--no-cache'])

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog <deployment>")
    optparser.add_option(
        "-c", "--create", dest="create_database", action="store_true", default=False,
        help="Create the database if needed.",
    )
    optparser.add_option(
        "-r", "--rollback", dest="rollback_migrations", action="store_true", default=False,
        help="Rollback migrations.",
    )
    optparser.add_option(
        "", "--no_prompt", dest="no_prompt", action="store_true", default=False,
        help="Do not prompt for user verification when applying migrations.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if len(args) == 0:
        optparser.print_help()
        return

    deployment = args[0]
    if deployment is None:
        optparser.error("Please specify deployment name, e.g. development or live")

    if not opts.rollback_migrations:
        run_migrations(read_config_and_init(deployment), action="apply", create_database=opts.create_database, no_prompt=opts.no_prompt)
    else:
        run_migrations(read_config_and_init(deployment), action="rollback", create_database=opts.create_database, no_prompt=opts.no_prompt)

if __name__ == "__main__":
    main(sys.argv[1:])
