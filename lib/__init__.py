# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

import uuid

def get_uuid(thing, allow_none=False):
    if thing is None:
        if allow_none:
            return None
        else:
            raise Exception("Cannot get a UUID from a None object.")

    if isinstance(thing, uuid.UUID):
        return thing
    elif isinstance(thing, (str, unicode)):
        try:
            return uuid.UUID(bytes=thing)
        except ValueError:
            return uuid.UUID(thing)
    elif isinstance(thing, (int, long)):
        return uuid.UUID(int=thing)
