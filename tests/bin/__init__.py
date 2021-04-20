# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# This module provides the phantomjs and casperjs commands to Python code.
import os, sys

BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

# Note, this is a 32bit build for Linux.
if 'linux' in sys.platform:
    phantom_exec_name = "phantomjs.i686.linux"
elif 'darwin' in sys.platform:
    phantom_exec_name = "phantomjs.mac"
else:
    raise Exception("Cannot find phantomjs executable for platform %s" % sys.platform)

PHANTOMJS_EXECUTABLE = os.path.join(BASEDIR, "phantomjs", phantom_exec_name)
CASPER_EXECUTABLE = os.path.join(BASEDIR, "casperjs/bin/casperjs")

# Need to tell casperjs where it can find the phantomjs executable.
os.environ['PHANTOMJS_EXECUTABLE'] = PHANTOMJS_EXECUTABLE
