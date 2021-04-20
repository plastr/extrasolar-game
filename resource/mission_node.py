# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson
from front.models import user
from front.resource import json_success_with_chips

class MissionParentNode(resource.Resource):
    def __init__(self, request, mission_id):
        self.user = user.user_from_request(request)
        self.mission = self.user.missions[mission_id]
    
    @resource.child()
    def mark_viewed(self, request, segments):
        return MarkViewedNode(self.mission), segments

class MarkViewedNode(resource.Resource):
    def __init__(self, mission):
        self.mission = mission

    @resource.POST(accept=xjson.mime_type)
    def mark_viewed(self, request):
        self.mission.mark_viewed()
        return json_success_with_chips(request)
