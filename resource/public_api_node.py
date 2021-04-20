# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import resource

from front.lib import xjson, urls
from front.backend import highlights
from front.resource import json_api_success

class PublicAPINode(resource.Resource):
    @resource.child()
    def photo_highlights(self, request, segments):
        return PhotoHighlights()

class PhotoHighlights(resource.Resource):
    @resource.GET(accept=xjson.mime_type)
    def get(self, request):
        # Return this many highlights by default
        count = 3
        # If a count parameter was supplied use that when determining how many
        # highlights to return.
        # NOTE: If count > 10 it will be clamped to 10.
        if 'count' in request.GET:
            count = int(request.GET['count'])
            if count > 10:
                count = 10

        targets = highlights.recent_highlighted_targets(request, count)
        for t in targets:
            image_url_root = urls.absolute_root(request)
            # Target image URLs might not be absolute (e.g. for initial or testing scene images).
            # If an image URL looks like a scene, add the absolute URL from the request to the URL.
            if t['url_photo'].startswith(urls.scenes_base()):
                t['url_photo'] = urls.join(image_url_root, t['url_photo'])
                t['url_thumbnail'] = urls.join(image_url_root, t['url_thumbnail'])
            # The public photo page always needs to be made absolute and is currently hosted
            # on the same server that is serving /api requests.
            t['url_public_photo'] = urls.join(image_url_root, t['url_public_photo'])

        return json_api_success(request, {'targets': targets})
