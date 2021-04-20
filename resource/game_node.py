# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import http, resource, templating

from front.data import assets
from front.lib import urls
from front.resource import auth

class GameNode(resource.Resource):
    """Restish node for handling everything under the /ops path.
    It's a little funky, because segments break at the / character, so
    /ops/ is different than /ops.  And Facebook really wants our app
    url to be /ops/.  So that's our canonical url, and GameNode redirects
    requests from /ops to /ops/.

    This could be substantially simpler if we didn't redirect to /ops/,
    but it's better to do the redirect.
    """
    @resource.GET()
    def html(self, request):
        return http.see_other(request.relative_url(urls.ops()))

    @resource.child('')   # /ops/  (the empty string represents the
                          # lack of characters after the final /)
    def trailing_slash(self, request, segments):
        """Dispatch to GameSlash, which does all the real work."""
        return GameSlash()

class GameSlash(resource.Resource):
    @resource.GET()
    @auth.authentication_required
    @templating.page('game.html')
    def html(self, request):
        return {
            'gamestate_url':urls.gamestate(),
            'ops_server': urls.static_root(),
            'assets_json_s':assets.get_asset_json(),
            'is_mobile': urls.is_mobile(request)
        }
