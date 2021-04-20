# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson, utils
from front.models import user
from front.resource import json_success_with_chips, json_bad_request

class AchievementParentNode(resource.Resource):
    def __init__(self, request, achievement_key):
        self.user = user.user_from_request(request)
        self.achievement = self.user.achievements[achievement_key]
    
    @resource.child()
    def mark_viewed(self, request, segments):
        return MarkViewedNode(self.achievement), segments

class MarkViewedNode(resource.Resource):
    def __init__(self, achievement):
        self.achievement = achievement

    @resource.POST(accept=xjson.mime_type)
    def mark_viewed(self, request):
        # Do not allow an achievement that has not been achieved to be marked viewed.
        if not self.achievement.was_achieved():
            return json_bad_request(utils.tr("Unachieved achievement can not be marked viewed."))
        self.achievement.mark_viewed()
        return json_success_with_chips(request)
