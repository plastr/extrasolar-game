# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource
from front.resource import stripe_node

class ShopNode(resource.Resource):
    @resource.child()
    def stripe(self, request, segments):
        return stripe_node.StripeParentNode(request), segments
