# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Contains utilities for working with HTML form data.

def fetch(request, fields, blanks=[]):
    """ Extremely rudimentary validation simply checks whether the
    fields are present and non-empty in the POST parameters. """
    values = {}
    ok = True
    for field in fields:
        val = request.POST.get(field, '')
        if val == '' and field not in blanks:
            ok = False
        values[field] = val
    return ok, values
