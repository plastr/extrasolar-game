# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import select
import subprocess
import cStringIO

from webtest.ext import TestApp

class RunProcessForTest(object):
    """
    An abstract baseclass for context manager which runs a process inside of a webtest unit test. Uses
    webtest's external process TestApp wrapper (which forks a webserver for the duration of the process)
    and then executes an external process to run (presumably Javascript) unit tests against that webserver.
    Cleans everything up when the context manager exits.

    Example:
    with RunProcessForTest(self.app) as run:
        run(full_path_to_js_script, *ARGS)
    """
    # The number of seconds to wait for a new line of output from the external process.
    TIMEOUT = 120.0

    # Nose should not execute this class as a test.
    __test__ = False

    def __init__(self, test_app):
        self.app = TestApp(test_app.app)

    def create_cmdline(self, *args):
        """ Return the array of command line arguments. Override this method in subclass. """
        return []

    def process_output(self, output, returncode):
        """ Process the entire command output string. The int return code is also supplied.
            Override this method in subclass. """
        pass

    def output_line(self, line):
        """ Called after every line of output.
            Optionally override this method in subclass. """
        pass

    def __enter__(self):
        def run(*args):
            # Setup the command to call casperjs.
            self.cmd = self.create_cmdline(*args)
            p = subprocess.Popen(self.cmd, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT,
                                           stdin=subprocess.PIPE)
            # Run the command, capturing the stdout/stderr pipeline stream.
            output_io = cStringIO.StringIO()
            try:
                # Use select to make sure there is data to be read from the test runner process.
                # If more than 'TIMEOUT' seconds elapse before new output appears, then the process
                # is terminated and an exception is raised.
                # select.select is used because it is available on MacOS and Linux.
                while True:
                    readable, writable, exceptional = select.select([p.stdout], [], [p.stdout], self.TIMEOUT)
                    if readable or exceptional:
                        line = p.stdout.readline()
                        output_io.write(line)
                        self.output_line(line)
                        # End of output.
                        if line == "":
                            break
                    else:
                        raise Exception('Tests timed out, process failed %s' % " ".join(self.cmd))

            finally:
                # If the process hasn't quit, kill it
                if p.poll() is None:
                    p.terminate()

            output = output_io.getvalue()
            output_io.close()

            self.process_output(output, p.returncode)
            # If no code in process_output handled this, catch it here.
            if p.returncode != 0:
                raise Exception('Failure to execute %s\n%s' % (" ".join(self.cmd), output))

        return run

    def __exit__(self, exception_type, value, tb):
        self.app.close()
        if exception_type == OSError:
            raise Exception("Failed to execute process. Unable to find executable? %s" % " ".join(self.cmd))

## Monkey patch the WSGIServer and simple_server.ServerHandler classes to not spew socket errors
# to stderr. These errors occurr because the client side process (in this case phantomjs/casperjs)
# appears to terminate (usually when a test fails) before it has read all of the data from the server
# response and the server complains about this. Annoyingly it complains about this to stderr deep within
# the server handling classes by printing to stderr instead of letting the exceptions bubble up.
# These monkey patched methods appear to be public API and would be expected to be overriden in a subclass.
from webtest.sel import WSGIServer
from wsgiref import simple_server
import errno
import socket
import sys

# Ignore "Broken pipe" and "Connection reset by peer" errors from the server socket.
IGNORE_ERRNO = (errno.EPIPE, errno.ECONNRESET)

handle_error_original = WSGIServer.handle_error
def handle_error_override(self, request, client_address):
    exc_type, exc_value = sys.exc_info()[:2]
    if exc_type == socket.error and exc_value.errno in IGNORE_ERRNO:
        return

    return handle_error_original(self, request, client_address)
WSGIServer.handle_error = handle_error_override

log_exception_original = simple_server.ServerHandler.log_exception
def log_exception_override(self, exc_info):
    exc_type, exc_value, exc_traceback = exc_info
    if exc_type == socket.error and exc_value.errno in IGNORE_ERRNO:
        return

    return log_exception_original(self, exc_info)
simple_server.ServerHandler.log_exception = log_exception_override
