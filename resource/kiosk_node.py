# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import http, resource, templating

from front.data import assets
from front.lib import urls
from front.models import user
from front.resource.auth import password, user_present, user_valid, log_user_in, log_user_out

import logging
logger = logging.getLogger(__name__)

def init_module(kiosk_campaign_name, demo_campaign_name):
    KioskNode.CAMPAIGN_NAME         = kiosk_campaign_name
    DemoNode.CAMPAIGN_NAME          = demo_campaign_name
    TabletSignupNode.CAMPAIGN_NAME  = kiosk_campaign_name

class KioskNode(password._SignupUserBase):
    KIOSK_MODE = 'KIOSK'
    TEMPLATE = 'kiosk.html'
    TEMPLATE_COMPLETE = 'unauthorized.html'
    URL_COMPLETE = urls.kiosk_complete()
    URL_COMPLETE_EXISTS = urls.kiosk_complete_exists()
    URL_KIOSK_RESTART = urls.kiosk()
    # Set in init_module
    CAMPAIGN_NAME = None

    @classmethod
    def extra_template_params(self, request):
        return {'map_tile_kiosk_url': urls.map_tile_kiosk(request),
                'assets_json_s': assets.get_asset_json(),
                'kiosk_mode': self.KIOSK_MODE}

    # If the kiosk user being signed up already exists (and the password was valid) then redirect
    # them back to /kiosk with a query parameter set so we can tell them we already have their application.
    def user_already_exists(self, request, user_id, fields):
        log_user_in(request, user_id)
        return http.see_other(self.URL_COMPLETE_EXISTS)

    def user_signup_complete(self, request, user):
        log_user_in(request, user.user_id)
        # If a campaign name was given in the query params, it should override the default.
        campaign_name = request.GET.get(urls.CAMPAIGN_NAME_PARAM, self.CAMPAIGN_NAME)
        user.add_metadata("MET_CAMPAIGN_NAME", campaign_name)
        return http.see_other(self.URL_COMPLETE)

    @resource.GET()
    def get(self, request):
        # Be very sure any user is force logged out who hits /kiosk to avoid confusion
        # with the next user signing up.
        log_user_out(request)

        content = templating.render(request, self.TEMPLATE, self.template_params(request))
        return http.ok([('content-type', 'text/html')], content)

    @resource.child('complete')
    def complete(self, request, segments):
        if user_present(request) and user_valid(request) and self.KIOSK_MODE is not 'KIOSK':
            # If we're not in kiosk mode and the user has already been authenticated, redirect to root node.
            return http.see_other(urls.auth_signup())
        elif user_present(request):
            params = {'kiosk_mode': self.KIOSK_MODE,
                      'user': user.user_from_request(request),
                      'url_restart': self.URL_KIOSK_RESTART}
            if 'exists' in request.GET:
                params['user_already_exists'] = True
            content = templating.render(request, self.TEMPLATE_COMPLETE, params)
            return http.ok([('content-type', 'text/html')], content)
        else: 
            # The request doesn't include a user. Restart the kiosk.
            return http.see_other(self.URL_KIOSK_RESTART)

class DemoNode(KioskNode):
    KIOSK_MODE = 'DEMO'
    URL_COMPLETE = urls.demo_complete()
    URL_COMPLETE_EXISTS = urls.demo_complete_exists()
    URL_KIOSK_RESTART = urls.demo()
    # Set in init_module
    CAMPAIGN_NAME = None

class TabletSignupNode(KioskNode):
    TEMPLATE = 'tablet_signup.html'
    URL_COMPLETE = urls.tablet_signup_complete()
    URL_COMPLETE_EXISTS = urls.tablet_signup_complete_exists()
    URL_KIOSK_RESTART = urls.tablet_signup()
    # Set in init_module
    CAMPAIGN_NAME = None
