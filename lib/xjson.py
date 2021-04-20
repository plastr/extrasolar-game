# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""Some json-serialization-related program activities."""

import json
from datetime import datetime
import uuid
from front.lib import utils

mime_type = 'application/json'
content_type = ('content-type', mime_type)
accept = ('accept', mime_type)

def additional_default(obj):
    if isinstance(obj, datetime):
        return utils.to_ts(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    # Serialize sets as arrays.
    elif isinstance(obj, set):
        return list(obj)
    return str(obj)

def dumps(obj, **kw):
    return json.dumps(obj, default=additional_default, **kw)

def prints(obj):
    """ Small helper to print a large dict object. """
    import pprint
    pprint.pprint(obj, indent=2)

loads = json.loads    
load = json.load
