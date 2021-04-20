#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

from front.lib import planet as planet_module

if __name__ == "__main__":
    eris = planet_module.time_in_eris()
    print 'Current time = %f eris' % (eris)
    print 'In 6 hours   = %f eris' % (eris + 6.0/15.3)
  

