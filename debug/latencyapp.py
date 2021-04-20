# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import time, re

from paste import httpexceptions

import logging
logger = logging.getLogger(__name__)

class LatencyApplication(object):
    """
    A WSGI application which handles no resources but injects latency into every request.
    Example use in a paste .ini file:

    [composite:main]
    use = egg:Paste#cascade
    app1 = latency

    [app:latency]
    use = call:front.debug.latencyapp:application
    ; Optionally the latency value can be provided.
    latency = 0.2
    ; Optionally a regex pattern can be provided to only add latency to matching requests
    pattern = /path/.*
    """
    def __init__(self, latency=0.3, pattern=None):
        self.latency = float(latency)
        if pattern is not None:
            self.pattern = re.compile(pattern)
        else:
            self.pattern = None

    def __call__(self, environ, start_response):
        if self.pattern is not None:
            # Normally would use wsgiref.util.request_uri(environ) but only really
            # care about this portion of the URI in this case.
            path = environ['PATH_INFO']
            if self.pattern.match(path):
                logger.info("Request path [%s] matched pattern, adding latency [%ss]" % (path, self.latency))
                time.sleep(self.latency)
        else:
            time.sleep(self.latency)

        exc = httpexceptions.HTTPNotFound('No resources handled by this application.')
        return exc.wsgi_application(environ, start_response)

def application(global_conf, latency=0.3, pattern=None):
    return LatencyApplication(latency=latency, pattern=pattern)
