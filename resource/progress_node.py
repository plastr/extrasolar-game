# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson, utils
from front.models import progress
from front.models import user as user_module
from front.resource import json_success_with_chips, json_bad_request, decode_json

class ProgressParentNode(resource.Resource):
    def __init__(self, request):
        self.user = user_module.user_from_request(request)

    @resource.POST()
    # Handles POST to /progress
    def post(self, request):
        body, error = decode_json(request, required={
            'key': unicode,
            'value': unicode
        })
        if body is None: return error
        # The key must start with a valid client progress key prefix.
        if not progress.is_valid_client_key(body['key']):
            return json_bad_request(utils.tr("Invalid client progress key."))

        # The key must NOT exist in user.progress already.
        if body['key'] in self.user.progress:
            return json_bad_request(utils.tr("Progress key already present."))

        progress.create_new_client_progress(request, self.user, body['key'], body['value'])
        return json_success_with_chips(request)

    @resource.child('{key}/reset')
    def reset(self, request, segments, key):
        return ProgressResetNode(request, self.user, key), segments

class ProgressResetNode(resource.Resource):
    def __init__(self, request, user, key):
        self.user = user
        self.key = key

    @resource.POST(accept=xjson.mime_type)
    # Handles POST to /progress/<key>/reset
    def post(self, request):
        # The key must start with a valid client progress key prefix.
        if not progress.is_valid_client_key(self.key):
            return json_bad_request(utils.tr("Invalid client progress key."))

        # The key must exist in user.progress already.
        if self.key not in self.user.progress:
            return json_bad_request(utils.tr("Key not present, cannot be reset."))

        progress.reset_client_progress(request, self.user, self.key)
        return json_success_with_chips(request)
