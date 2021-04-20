#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
# Generates the current version string, optionally writing it to a file.

# NOTE: Do not import anything from front or virtualenv installed packages so this
# can be run with any python.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)
import optparse

from front import Version

def make_optparser():
    optparser = optparse.OptionParser(usage="%prog [-w] [path]")
    optparser.add_option(
        "-w", "", dest="write_output", action="store_true", default=False,
        help="Write the version output to a file.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if opts.write_output:
        version = Version.from_current_repo()
        if len(args) == 1:
            path = os.path.join(args[0], Version.VERSION_FILE)
        else:
            path = os.path.join(BASEDIR, Version.VERSION_FILE)
        version.write(path)
        print "Wrote version file to", path
    else:
        print "Current repo version: [%s]" % Version.from_current_repo()    
    
if __name__ == "__main__":
    main(sys.argv[1:])
