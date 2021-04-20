# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.resource import target_node
from front.models import user

class RoverNode(resource.Resource):
    def __init__(self, request, rover_id):
        # verify that this rover belongs to the logged-in user, protecting 
        # everything under this url hierarchy
        u = user.user_from_request(request)
        self.rover = u.rovers[rover_id]
    
    @resource.child()
    def target(self, request, segments):
        return target_node.TargetParentNode(request, self.rover), segments
