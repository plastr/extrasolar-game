# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson
from front.models import user as user_module
from front.resource import decode_json, json_success_with_chips

class UserParentNode(resource.Resource):
    def __init__(self, request):
        self.user = user_module.user_from_request(request)

    @resource.child()
    def update_viewed_alerts_at(self, request, segments):
        return UpdateViewedAlertsAt(request, self.user), segments

    @resource.child()
    # Defines the handler for any /user/settings requests.
    def settings(self, request, segments):
        return UserSettings(request, self.user), segments

class UpdateViewedAlertsAt(resource.Resource):
    def __init__(self, request, user):
        self.user = user

    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        self.user.update_viewed_alerts_at()
        return json_success_with_chips(request)

class UserSettings(resource.Resource):
    def __init__(self, request, user):
        self.user = user

    @resource.child()
    def notifications(self, request, segments):
        return UserSettingsNotifications(request, self.user), segments

class UserSettingsNotifications(resource.Resource):
    def __init__(self, request, user):
        self.user = user

    @resource.POST(accept=xjson.mime_type)
    def post(self, request):
        body, error = decode_json(request, required={'activity_alert_frequency': unicode})
        if body is None: return error

        self.user.set_activity_alert_frequency(body['activity_alert_frequency'])
        return json_success_with_chips(request, json_body=body)
