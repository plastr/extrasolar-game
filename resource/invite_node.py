# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson
from front.models import invite as invite_module
from front.models import user as user_module
from front.resource import decode_json, json_success_with_chips, json_bad_request

class InviteParentNode(resource.Resource):
    def __init__(self, request):
        self.user = user_module.user_from_request(request)

    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={
            'recipient_email': unicode,
            'recipient_first_name': unicode,
            'recipient_last_name': unicode,
            'recipient_message': unicode
        })
        if body is None: return error

        # Validate the user supplied invite parameters are correct. This function will truncate or otherwise
        # modify any parameters it can and if it is unable to fix a given parameter it will return None and
        # an error message.
        params, error = invite_module.validate_invite_params(self.user,
                                                             body['recipient_email'], body['recipient_first_name'],
                                                             body['recipient_last_name'], body['recipient_message'])
        if params is None:
            return json_bad_request(error)

        # Create the new invitation and send an email to the recipient.
        invite_module.create_new_invite(request, self.user, **params)

        # The new invite and related data will be returned via a chip.
        return json_success_with_chips(request, json_body=body)
