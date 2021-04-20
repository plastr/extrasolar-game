# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson
from front.models import user
from front.resource import json_success_with_chips

class SpeciesParentNode(resource.Resource):
    def __init__(self, request, species_id):
        self.user = user.user_from_request(request)
        self.species = self.user.species[species_id]
    
    @resource.child()
    def mark_viewed(self, request, segments):
        return MarkViewedNode(self.species), segments

class MarkViewedNode(resource.Resource):
    def __init__(self, species):
        self.species = species

    @resource.POST(accept=xjson.mime_type)
    def mark_viewed(self, request):
        self.species.mark_viewed()
        return json_success_with_chips(request)
