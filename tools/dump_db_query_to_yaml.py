#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
#
# Use this tool to dump results of SQL queries (most likely in production) in a JSON format that is roughly similar
# to what would come back from a call to db.row/db.rows. This output can be useful in development and testing if
# there is data that is only produced realistically in production (like aggregate user statistics) that would be useful
# for testing and development work.
#
# Simple example usage:
# dump_db_query_to_yaml.py "SELECT COUNT(*) FROM users;"
#
# Example usage with query arguments:
# dump_db_query_to_yaml.py "SELECT DATE_FORMAT(created, :d_f) AS day FROM users WHERE;" '{"d_f": "%Y%m%d"}'
#

import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse
import yaml

from front import read_config_and_init
from front.lib import db, xjson, gametime

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog \"SQL query\" [\"JSON query arguments\"]")
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development."
    )
    optparser.add_option(
        "-v", "--verbose", dest="verbose", action="store_true", default=False,
        help="Verbose. Echo the actual query being run.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if len(args) == 1:
        params = {}
    # Handle the optional JSON query arguments if provided.
    elif len(args) == 2:
        params = xjson.loads(args[1])
    # Must have exactly 1 or 2 arguments.
    else:
        optparser.print_help()
        return

    config = read_config_and_init(opts.deployment)
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            if opts.verbose:
                query_sql = db._compose_query_string(ctx, args[0], **params)
                print
                print "Running query: \"%s\"" % query_sql
                print
            rows = db._run_query_string(ctx, args[0], **params)
            print "## START -- dump_db_query_to_yaml.py output"
            print "## Generated at %s GMT with command arguments:" % gametime.now().replace(microsecond=0)
            if len(params) > 0:
                print "## \"%s\" \'%s\'" % (args[0], args[1])
            else:
                print "## \"%s\"" % (args[0])
            print yaml.dump(rows),
            print "## END -- dump_db_query_to_yaml.py output"

if __name__ == "__main__":
    main(sys.argv[1:])
