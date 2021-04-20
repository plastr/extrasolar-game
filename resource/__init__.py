# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from functools import wraps
from restish import http

from front.models import chips, user
from front.lib import get_uuid, xjson, utils
from front.data import validate_dict

import logging
logger = logging.getLogger(__name__)

def decode_base62_uuid(arg_name):
    """
    Decorator which converts a base62 encoded URL parameter into a UUID object.
    Currently supports being placed after a resource.child decorator e.g.
    @resource.child('url/{user_id}')
    @decode_base62_uuid('user_id')
    def url(self, request, segments, user_id):
        # user_id will be a UUID object.
    """
    def decorator(func):
        @wraps(func)
        def decorated(page, request, *a, **k):
            if arg_name not in k:
                raise Exception("Cannot find base62 argument to decode to UUID [%s]" % arg_name)
            # Decode the argument and replace its value before continuing with the request value.
            try:
                k[arg_name] = get_uuid(utils.base62_to_int(k[arg_name]))
            except ValueError:
                logger.warn("Bad encoded UUID URL parameter: [%s][%s]" % (k[arg_name], request.path_qs))
                return http.bad_request([('content-type', 'text/html')], "Badly formed URL or parameters.")
            return func(page, request, *a, **k)
        return decorated
    return decorator

def decode_json(request, required={}):
    """
    Decode/deserialize a JSON body from the given request.
    :param required: Optionally pass a dict of required fields. If any are missing,
        an error response is created. The dict maps requied field names to their required
        data types (int, float, etc). The field value will be cast into the required type
        if they are not already and if that conversion fails, an error will be returned.
    Returns the Python object body after deserialization. If this is None, then the second
        returned argument will be a fully populated HTTP error response, ready to be returned
        from the node/resource.
    """
    body = xjson.loads(request.body)
    body, error = validate_dict(body, required=required)
    if body is not None:
        return body, None
    else:
        return None, json_bad_request(error)

## JSON response helpers meant to be used in 'game' context, meaning not publicly accessible and
#  behind authentication and support chips. This means they DO NOT support JSONP and CORS usage.
def json_success(response=None):
    """
    Indicate a successful request by returning this from a request handler.
    No chips will be added to the response.
    :param response: Optionally pass in a response dict to return additional data in the response.
    """
    if response is None: response = {}
    return http.ok([xjson.content_type], xjson.dumps(response))

def json_success_with_chips(request, response=None, json_body=None):
    """
    See json_success. Chips will be added to the response.
    :param json_body: Optionally pass in an already deserialized request JSON body dict.
    """
    if response is None: response = {}
    response, error = update_response_with_chips_from_request(response, request, json_body=json_body)
    if error is not None: return error
    return json_success(response)

def json_bad_request(error_msg, response=None):
    """
    Pass in an error message and return this from a request handler to indicate a failure with request
    arguments. A 400 HTTP error code will be returned as well.
    The JSON response will include the supplied error message in the 'errors' array.
    No chips will be added to the response.
    :param response: Optionally pass in a response dict to return additional data in the response.
    """
    if response is None: response = {}
    response['errors'] = [error_msg]
    return http.bad_request([xjson.content_type], xjson.dumps(response))

def json_bad_request_with_chips(request, error_msg, response=None):
    """
    See json_bad_request. Chips will be added to the response.
    """
    if response is None: response = {}
    response, error = update_response_with_chips_from_request(response, request)
    if error is not None: return error
    return json_bad_request(error_msg, response)

def update_response_with_chips_from_request(response, request, json_body=None):
    """
    This sticks any pending chips for the user onto a response object from a request object.

    :param response: Outgoing response object, must be a dict or else.
    :param request: The request object. Expected to have a chips.last_seen_chip_time as a JSON body if
        a POST, otherwise a request parameter last_seen_chip_time if a GET.
    :param json_body: If the body of the request has already been deserialized from JSON, pass that dict
        as this parameter so that it does not need to be deserialized again.
    Returns the response, None if all required data was in the request, otherwise it returns
        None, error where error is a fully populated HTTP response string.
    """
    u = user.user_from_request(request)
    if u is None:
        raise Exception("Unable to load user_id from request when getting chips for response.")

    if request.method == "GET":
        if 'last_seen_chip_time' not in request.params:
            return None, json_bad_request(utils.tr("Missing required parameter last_seen_chip_time."))
        last_seen_chip_time = utils.usec_dt_from_js(request.params['last_seen_chip_time'])
    else:
        if json_body is None:
            json_body = xjson.loads(request.body)
        if 'chips' not in json_body or 'last_seen_chip_time' not in json_body['chips']:
            return None, json_bad_request(utils.tr("Missing required parameter chips.last_seen_chip_time."))
        last_seen_chip_time = utils.usec_dt_from_js(json_body['chips']['last_seen_chip_time'])
    return chips.update_response(request, u, response, last_seen_chip_time), None

## JSON response helpers meant to be used in 'API' situations, meaning publicly accessible.
#  This means they support JSONP and CORS usage.
#  NOTE: CORS is not supported in IE8/9 even with jQuery being used. Custom code would need to be
#  added on the client or CORS should not be considered unsafe for those browsers.
#  See: http://blogs.msdn.com/b/ieinternals/archive/2010/05/13/xdomainrequest-restrictions-limitations-and-workarounds.aspx
def json_api_success(request, response=None):
    headers, data = _json_api_response(request, response)
    return http.ok(headers, data)

def json_api_bad_request(request, error_msg, response=None):
    if response is None: response = {}
    response['errors'] = [error_msg]
    headers, data = _json_api_response(request, response)
    return http.bad_request(headers, data)

CALLBACK_PARAM = 'callback'
def _json_api_response(request, response=None):
    if response is None: response = {}
    json = xjson.dumps(response)
    headers = []
    # If there is a callback parameter in the GET arguments, assume this is a JSONP request.
    # Wrap the JSON into a Javascript function using the callback argument as the function name.
    # NOTE: JSONP can only be used with GETs.
    if 'callback' in request.GET:
        callback = request.GET['callback']
        data = "%s(%s)" % (str(callback), json)
        headers.append(('content-type', 'application/javascript'))

    # If there is an Origin parameter in the headers, then this is a CORS request.
    elif 'Origin' in request.headers:
        headers.append(xjson.content_type)
        # NOTE: We could be more strict about the list of allowed domains.
        # if origin not in self.ALLOWED_ORIGINS:
        #     return json_bad_request(utils.tr("Unauthorized request."))
        # headers.append(('Access-Control-Allow-Origin', origin))
        headers.append(('Access-Control-Allow-Origin', '*'))
        # NOTE: Consider allowing cookie information in CORS context.
        # headers.append(('Access-Control-Allow-Credentials', 'true'))
        data = json

    # Otherwise assume this is a same origin standard AJAX JSON request.
    else:
        headers.append(xjson.content_type)
        data = json

    return headers, data
