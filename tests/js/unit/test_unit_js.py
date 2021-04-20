# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os

from front.tests import base
from front.tests.js import RunProcessForTest

BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))

class TestQUnitJS(base.TestCase):
    def test_qunit_tests(self):
        with run_qunit_test(self.app) as run:
            testing_url = os.environ['APPLICATION_URL'] + "unit"
            run(os.path.join(BASEDIR, 'run-qunit-in-casperjs.js'), testing_url)


## A context manager to run the qunit unit tests with casperjs.
from webtest.compat import to_bytes, to_string
from front.tests.bin import CASPER_EXECUTABLE
class run_qunit_test(RunProcessForTest):
    def create_cmdline(self, script, url, *args):
        self.script = script
        cmd = [CASPER_EXECUTABLE] + [self.script, url] + list(args)
        return cmd

    def process_output(self, output, returncode):
        if to_bytes('Total: 0') in output:
            raise AssertionError('No tests ran in: %s\n%s' % (self.script, to_string(output)))
        if to_bytes('Failed: 0') not in output:
            raise AssertionError('Tests failed in: %s\n%s' % (self.script, to_string(output)))
        elif to_bytes('Passed') not in output:
            raise Exception('Tests failed to run in: %s\n%s' % (self.script, to_string(output)))
        else:
            print(to_string(output))
