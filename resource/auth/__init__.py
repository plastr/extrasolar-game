# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
Basic authentication methods used by most Nodes in the system.  It's 
one abstraction layer up from the metal, since it knows about two
different authentication schemes: psaswords and facebook.
"""
from restish import http
import uuid
from functools import wraps

from front.lib import urls, utils
from front.models import user
from front.resource import json_bad_request

def log_user_in(request, user_id):
    """Sets things up in the session so that the user is logged on.
    """
    assert isinstance(user_id, uuid.UUID)
    session = request.environ['beaker.session']
    session['user_id'] = user_id
    session.save()

def log_user_out(request):
    """Logs the user out by nuking their session."""
    session = request.environ['beaker.session']
    # Delete does not seem to fully clear the client-side cookie, so be sure
    # the user_id field is cleared as well.
    # The user_id field might not be in the session if this user is already
    # logged out yet logout has been attempted again, if for instance the JS client
    # is still performing fetch chips but the user was deleted.
    if 'user_id' in session:
        del session['user_id']
    session.save()
    session.delete()

def user_present(request):
    """Returns true if someone is logged in."""
    return bool(request.environ['beaker.session'].get('user_id'))

def user_valid(request):
    """Check if the session user is valid (has a valid email address)."""
    u = user.user_from_request(request)
    return (u != None) and u.valid

def authentication_required(func):
    """This is a decorator function.  It's intended to be stuck on Restish handle 
    functions (not dispatch functions).  It checks for user credentials and 
    throws errors before calling the decorated method.  The decorated method can
    then assume that it's A-OK to proceed if it gets called. This decorator only makes
    sense for plain requests expecting HTML responses. It will not work cleanly for JSON
    requests.
    """
    @wraps(func)
    def call(*args):
        # The request object is either the first parameter when used to decorate a freestanding function
        # otherwise it is the second argument if used to decorate a resource method.
        if isinstance(args[0], http.Request):
            request = args[0]
        else:
            request = args[1]
        if user_present(request):
            if user_valid(request):
                # User logged in and valid, continue processing the resource.
                return func(*args)
            else:
                # User exists but has not been validated, redirect to / which
                # will display a useful message
                return http.see_other(urls.root())
        else:
            # User is not authenticated, redirect them to simple login page.
            # NOTE: The portion of the url following the pound sign is not sent
            # by the browser to the server, so it will not get appended here.
            if urls.is_mobile(request):
                # The simple login page isn't mobile-optimized, so just redirect to root.
                return http.see_other(urls.root())
            else:
                return http.see_other(urls.add_original_url_param(urls.auth_login_simple(), request.path_qs))
                
    return call

def authentication_required_json(func):
    """This is a decorator function.  It's intended to be stuck on Restish handle 
    functions (not dispatch functions).  It checks for user credentials and 
    returns JSON errors as the response if the user is not authenticated.
    """
    @wraps(func)
    def call(*args, **kwargs):
        # The request object is either the first parameter when used to decorate a freestanding function
        # otherwise it is the second argument if used to decorate a resource method.
        if isinstance(args[0], http.Request):
            request = args[0]
        else:
            request = args[1]
        if user_present(request):
            if user_valid(request):
                # user logged in and valid, good to go
                return func(*args, **kwargs)
            else:
                # User exists but has not been validated, return an error.
                return json_bad_request(utils.tr("Unauthorized request."))
        else:
            # user is not authenticated, return an error.
            return json_bad_request(utils.tr("Unauthorized request."))
    return call

def admin_required(func):
    @wraps(func)
    def call(*args, **kwargs):
        # The request object is either the first parameter when used to decorate a freestanding function
        # otherwise it is the second argument if used to decorate a resource method.
        if isinstance(args[0], http.Request):
            request = args[0]
        else:
            request = args[1]
        u = user.user_from_request(request)
        if not u.is_admin():
            return http.unauthorized([('content-type', 'text/html')], 'Nothing to see here, move along.')
        else:
            return func(*args, **kwargs)
    return call
