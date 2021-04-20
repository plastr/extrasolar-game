# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import read_config
from front.lib import db

## These setUp and tearDown functions are called at the start and end of the test suite for this package
## and any sub packages.

# Create the database once for the entire test package/suite.
def setUp():
    db.create_database(read_config('test'), apply_schema=True)

# Destroy the database after the entire test package has run.
def tearDown():
    db.destroy_database(read_config('test'))
