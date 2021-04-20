# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson
from front.models import user
from front.resource import decode_json, json_success_with_chips

class MessageParentNode(resource.Resource):
    def __init__(self, request, message_id):
        self.user = user.user_from_request(request)
        self.message = self.user.messages[message_id]
    
    @resource.GET(accept=xjson.mime_type)
    # Handles GET to /message/<message_uuid>
    def get(self, request):
        body_html = self.message.load_content()
        response = {'content_html': body_html}
        return json_success_with_chips(request, response)

    @resource.child()
    # Defines the handler for any /message/<message_uuid>/unlock requests.
    def unlock(self, request, segments):
        return MessageUnlockNode(request, self.user, self.message), segments

    @resource.child()
    # Defines the handler for any /message/<message_uuid>/forward requests.
    def forward(self, request, segments):
        return MessageForwardNode(request, self.user, self.message), segments
    
class MessageUnlockNode(resource.Resource):
    def __init__(self, request, user, message):
        self.user = user
        self.message = message

    @resource.POST(accept=xjson.mime_type)
    # Handles POST to /message/<message_uuid>/unlock
    def post(self, request):
        body, error = decode_json(request, required={'password': unicode})
        if body is None: return error

        was_unlocked, body_html = self.message.unlock(body['password'])
        response = {'content_html': body_html, 'was_unlocked': was_unlocked}
        return json_success_with_chips(request, response, json_body=body)

class MessageForwardNode(resource.Resource):
    def __init__(self, request, user, message):
        self.user = user
        self.message = message

    @resource.POST(accept=xjson.mime_type)
    # Handles POST to /message/<message_uuid>/forward
    def post(self, request):
        body, error = decode_json(request, required={'recipient': unicode})
        if body is None: return error

        self.message.forward_to(body['recipient'])
        return json_success_with_chips(request, json_body=body)
