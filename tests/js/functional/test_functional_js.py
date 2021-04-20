# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os, re, subprocess
from datetime import datetime
from front.lib import gametime, urls

from front.tests import base
from front.tests.js import RunProcessForTest

BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

TEST_EMAIL    = 'testuser@example.com'
TEST_PASSWORD = 'password'
# Pass the login credentials via the casperjs command line.
ARGS =  ['--login_email='+TEST_EMAIL, '--login_password='+TEST_PASSWORD]
        # Need to disable web-security so that the facebook login system works.
ARGS += ['--web-security=no']

class FunctionalJSBase(base.TestCase):
    def setUp(self):
        super(FunctionalJSBase, self).setUp()
        self.create_validated_user(TEST_EMAIL, TEST_PASSWORD)

        # gametime was frozen by the setup_user call, so restore it to the wallclock though
        # factor in any time adjustments that were made.
        # NOTE: If any helper code is called while the casperjs process is running which freezes
        # gametime restore_tick MUST be called after that code otherwise the casperjs process
        # client wallclock time will diverge from the unit test servers wallclock which
        # will break things like fetch chips last_seen_chip_time
        gametime.restore_tick()

class TestLoginTut01(FunctionalJSBase):
    def test_login_simulator_tut01(self):
        with run_casperjs_test(self.app, self) as run:
            run(os.path.join(BASEDIR, 'test_login_and_tutorials.js'), *ARGS)

class TestCompiledJS(FunctionalJSBase):
    # Override the Paste configuration by using this facility defined in base.py
    PASTE_CONFIG = '#compiled_javascript'
    # Path to the Javascript compiler script
    COMPILE_JS = os.path.join(BASEDIR, '../../../..', 'bin/compile-js.sh')
    # Path relative to the testing cache directory in var where the compiled .js should be written
    COMPILED_OUTPUT = "compiled_js"

    # Generate the compiled JS files into the testing specific cache_dir which will be served by the
    # #compiled_javascript Paste app in test.ini and then run some JS functional tests against the compiled
    # JS code to make sure the gamestate etc. are still working.
    def test_compiled_js(self):
        # Run the Javascript compiler/concatenator and output the .js to a testing only
        # path which will be served by the #compiled_javascript app in test.ini
        output_dir =  os.path.join(self.conf['cache_dir'], self.COMPILED_OUTPUT)
        output = subprocess.check_output([self.COMPILE_JS, "-c", output_dir], stderr=subprocess.STDOUT)
        if 'ERROR' in output:
            errors = [m for m in re.findall(r'.* ERROR - .*\n.*', output)]
            raise AssertionError("Closure Compiler reported errors:\n\n " + '\n\n'.join(errors))

        with run_casperjs_test(self.app, self) as run:
            run(os.path.join(BASEDIR, 'test_compiled_js.js'), *ARGS)


## A context manager to run the casperjs functional tests.
from webtest.compat import to_bytes, to_string
from front.tests.bin import CASPER_EXECUTABLE
# pre.js provides common useful functionality and values for our functional Javascript tests as
# run from the webtest harness.
PREJS = os.path.join(BASEDIR, 'pre.js')

class run_casperjs_test(RunProcessForTest):
    def __init__(self, test_app, test):
        super(run_casperjs_test, self).__init__(test_app)
        # Override our base URL to correspond to the testing web server.
        urls.TOOLS_ABSOLUTE_ROOT = self.app.application_url[:-1]  # Strip trailing /
        self.tick = datetime.utcnow()
        self.test = test

    def create_cmdline(self, script, *args):
        self.script = script
        # casperjs should be handling this for us, but its path error causes the process to hang
        # because exitOnError is set to false.
        if not os.path.exists(self.script):
            raise Exception("casperjs testing script cannot be found: %s" % self.script)

        cmd = [CASPER_EXECUTABLE, 'test', '--pre=' + PREJS] + list(args) + [self.script]
        return cmd

    def process_output(self, output, returncode):
        if to_bytes('FAIL') in output:
            raise AssertionError('Tests failed in: %s\n%s' % (self.script, to_string(output)))
        elif to_bytes('passed') not in output:
            raise Exception('Tests failed to run in: %s\n%s' % (self.script, to_string(output)))

    def output_line(self, line):
        # Suppress verbose phantomjs 1.9.2 logs about CoreText performance first seen in OSX 10.9 (Mavericks).
        # FUTURE: Remove these once the underlying code is fix in phantomjs.
        if "CoreText performance note: Client called CTFontCreateWithName() using name" in line:
            return
        if "CoreText performance note: Set a breakpoint on CTFontLogSuboptimalRequest to debug" in line:
            return

        # Handle the test client requesting to render the newest target.
        if "TEST.CMD RENDER TARGET" in line:
            result = self.test.render_next_target(assert_only_one=True)
            (user_id, rover_id, target_id, arrival_time, metadata) = self.test.renderer_decompose_next_target(result)

        # Handle the test client requesting to render the newest target.
        elif "TEST.CMD ADVANCE GAME" in line:
            # The travel time is passed through at the end of the command line "[INTEGER SECONDS]"
            travel_time = int(re.search(r' \[([0-9]+)\]$', line).group(1))
            (deferred_rows, activated_chips) = self.test.advance_game_and_activate_chips(seconds=travel_time)
            # gametime was frozen by the advance_game_and_activate_chips call, so restore it to the
            # wallclock though factor in any time adjustments that were made.
            gametime.restore_tick()

        else:
            # Echo each non-command line as it happens so if the tests are run with the -s flag you see
            # the output in realtime like the Python tests.
            print to_string(line),

        # NOTE: If these tests end up running for significant amounts of time it might eventually be
        # necessary to track elpased time in the test and run deferred actions every minute instead
        # of relying on the client to signal advancing the game.
