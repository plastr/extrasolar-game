# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""
Root is the first class that Resish hits when it's trying to dispatch an
incoming http request.

Basically the Restish request handling flow is:
  1) Parse the url into segments, i.e., "/user/profile/show" would become ("user", profile", "show")
  2) Construct a Root object (with no-args constructor).
  3) If there are any unprocessed segments, try calling the appropriate @resource.child method for the first segment.
      It should construct and return a Resource subclass (in our naming convention these classnames should end in Node).
  4) Recursively do steps 3-4 on the returned objects until there are no segments left.
  5) When out of segments, look for methods on the object marked with @resource.GET (or POST) and call the appropriate
      one for the HTTP method.  This method returns an object from within the 'http' module.  That will contain the response.
  6) That's the request, discard the Node objects that were temporarily constructed during the request handling.
  
Query strings (the stuff after a ? in the url) are not explicitly a part of the dispatch logic, though their
values are accessible from the request object.
"""
from restish import http, resource, templating

from front import activity_alert_types
from front.lib import urls, forms, utils, xjson
from front.models import user
from front.resource import auth, game_node, api_node, renderer_node, admin_node, edmodo_node, decode_base62_uuid
from front.resource import gift_and_invite_node, kiosk_node
from front.resource.auth import password

import logging
logger = logging.getLogger(__name__)

class Root(resource.Resource):
    @resource.GET()
    def get(self, request):
        """This is the handler that responds to requests to path '/' 
        (i.e. the address bar reads http://host/).
        """
        # If a user is already logged-in send them to the game proper
        if auth.user_present(request):
            if auth.user_valid(request):
                return http.see_other(urls.ops())
            else:
                # user exists, but isn't validated.
                return http.see_other(urls.auth_signup_complete())
        else:
            params = {'signups_enabled': password.SIGNUPS_ENABLED,
                      'show_login_header': True}
            params.update(password.index_login_and_signup_template_params(request))
            if urls.is_mobile(request):
                # Mobile users a separate index template.
                params['error_message'] = ''
                params['is_native'] = False
                content = templating.render(request, 'mobile_index.html', params)
            else:
                content = templating.render(request, 'index.html', params)
            return http.ok([('content-type', 'text/html')], content)

    @resource.POST()
    def post(self, request):
        ok, fields = forms.fetch(request, ['form_type'])
        if ok:
            if fields['form_type'] == "login":
                return password.RootLoginNode()
            elif fields['form_type'] == "signup" or fields['form_type'] == "facebook":
                return password.RootSignupNode()
        # Log a highly suspect situation. Could be an Exception but
        # doing nothing seems fine in this case.
        logger.error("Badly formed login/signup POST. [%s]", fields)
        return http.see_other(request.path_qs)

    @resource.child('terms_of_service')
    def terms_of_service(self, request, segments):
        content = templating.render(request, 'terms_of_service.html')
        return http.ok([('content-type', 'text/html')], content)

    @resource.child('privacy_policy')
    def privacy_policy(self, request, segments):
        content = templating.render(request, 'privacy_policy.html')
        return http.ok([('content-type', 'text/html')], content)

    @resource.child('signup_complete')
    def signup_complete(self, request, segments):
        if auth.user_present(request) and not auth.user_valid(request):
            # user exists but isn't validated.
            if urls.is_mobile(request):
                # For mobile, mobile_index will display the 'unauthorized' message.
                params = {'error_message':'', 'is_native':False}
                content = templating.render(request, 'mobile_index.html', params)
                return http.ok([('content-type', 'text/html')], content)
            else:
                params = {'user': user.user_from_request(request)}
                content = templating.render(request, 'unauthorized.html', params)
                return http.ok([('content-type', 'text/html')], content)
        else:
            # The user either doesn't exist or is already validated. Let the Root node handle this case.
            return http.see_other(urls.auth_signup())

    @resource.child('invite/{invite_id}/{token}')
    @decode_base62_uuid('invite_id')
    def invite(self, request, segments, invite_id, token):
        # Verify this invite_id actually exists.
        u = user.user_from_invite_id(request, invite_id)
        if u is None:
            return http.bad_request([('content-type', 'text/html')], "Invalid request.")

        # Verify the invite_id has not been tampered with.
        invite = u.invitations[invite_id]
        if not invite.is_valid_invite_token(token):
            return http.bad_request([('content-type', 'text/html')], "Invalid request.")

        # If this invite has already been accepted, redirect to /
        if invite.was_accepted():
            return http.see_other(urls.root())

        # If the invite has a gift attached, then use the gift redeemption nodes, otherwise use
        # the simplier and more direct invite signup node.
        if invite.has_gift():
            return gift_and_invite_node.GiftChoiceNode(invite.gift, invite=invite)
        else:
            return gift_and_invite_node.InviteSignupNode(invite)

    @resource.child('gift/{gift_id}/{token}')
    @decode_base62_uuid('gift_id')
    def gift(self, request, segments, gift_id, token):
        # Verify this gift_id actually exists.
        creator = user.creator_from_gift_id(request, gift_id)
        if creator is None:
            return http.bad_request([('content-type', 'text/html')], "Invalid request.")

        # Verify the gift_id has not been tampered with.
        gift = creator.gifts_created[gift_id]
        if not gift.is_valid_gift_token(token):
            return http.bad_request([('content-type', 'text/html')], "Invalid request.")

        # If this gift was attached to an invite, send that to the node to make the invite available
        # to the template and to make the invite as accepted when the gift is redeemed.
        if gift.has_invite():
            return gift_and_invite_node.GiftChoiceNode(gift, invite=gift.invite)
        else:
            return gift_and_invite_node.GiftChoiceNode(gift)

    @resource.child()
    def login(self, request, segments):
        # If the user is already logged in, redirect them to the root page which can sort out where to send them.
        if auth.user_present(request):
            return http.see_other(urls.root())

        return password.SimpleLoginNode()

    @resource.child()
    def login_fb(self, request, segments):
        # If the user is already logged in, redirect them to the root page which can sort out where to send them.
        if auth.user_present(request):
            return http.see_other(urls.root())

        return password.FacebookLoginNode()

    @resource.child()
    def logout(self, request, segments):
        return password.LogoutNode()

    @resource.child('backdoor/{token}')
    def backdoor(self, request, segments, token):
        if not auth.user_present(request):
            return http.see_other(urls.add_original_url_param(urls.root(), request.path_qs))

        u = user.user_from_request(request)
        # If somehow this user was deleted (in development), then redirect to /
        if u is None:
            return http.see_other(urls.root())

        # If user is already validated, redirect to /ops.
        if u.valid:
            return http.see_other(urls.ops())

        # Otherwise, attempt to validate the user. If the token is invalid or was for another
        # user, redirect to /
        if not u.validate_with_token(token):
            return http.see_other(urls.root())

        # Otherwise, the user has been marked valid and display backdoor.html
        content = templating.render(request, 'backdoor.html')
        return http.ok([('content-type', 'text/html')], content)

    @resource.child('reset')
    def reset(self, request, segments):
        return password.RequestPasswordResetNode()

    @resource.child('reset/{user_id}/{token}/{timestamp}')
    @decode_base62_uuid('user_id')
    def password_reset(self, request, segments, user_id, token, timestamp):
        return password.ResetPasswordNode(user_id, token, timestamp)

    @resource.child('unsubscribe/{user_id}/{token}')
    @decode_base62_uuid('user_id')
    @templating.page('unsubscribe.html')
    def unsubscribe(self, request, segments, user_id, token):
        # Verify the user_id is a real user.
        u = user.user_from_context(request, user_id, check_exists=True)
        if u is None:
            return {'error': utils.tr("This user does not exist.")}

        # And that the token is valid.
        if not u.is_valid_unsubscribe_token(token):
            logger.error("Invalid token when attempting unsubscribe. (%s, %s)", user_id, token)
            return {'error': utils.tr("Unsubscribe link is invalid.")}

        # Data looks good, unsubscribe the user and display the unsubscribe page.
        u.set_activity_alert_frequency(activity_alert_types.OFF)
        return {'user': u}

    @resource.child('profile/{user_id}')
    @decode_base62_uuid('user_id')
    @templating.page('profile.html')
    def profile(self, request, segments, user_id):
        u = user.user_from_context(request, user_id, check_exists=True)
        if u is None:
            return {'error': utils.tr("This user does not exist.")}
        return {'user': u}

    @resource.child('photo/{target_id}')
    @decode_base62_uuid('target_id')
    @templating.page('photo.html')
    def photo(self, request, segments, target_id):
        u = user.user_from_target_id(request, target_id)
        if u is None:
            return {'error': utils.tr("This photo does not exist.")}
        target = u.rovers.find_target_by_id(target_id)
        if not target.has_been_arrived_at():
            return {'error': utils.tr("This photo is not available.")}
        if target.is_classified():
            return {'error': utils.tr("This photo is classified.")}
        # Convert all of the user's targets non-classified, arrived at photos into a JSON list
        # ready to be used by the Javascript thumbnail filmstrip code.
        target_structs = [t.to_struct_public() for t in u.all_arrived_picture_targets()
                                                     if not t.is_classified()]

        return {'user': u, 'target': target, 'target_structs': xjson.dumps(target_structs)}

    @resource.child('kiosk')
    def kiosk(self, request, segments):
        return kiosk_node.KioskNode()

    @resource.child('demo')
    def demo(self, request, segments):
        return kiosk_node.DemoNode()

    @resource.child('tablet_signup')
    def tablet_signup(self, request, segments):
        return kiosk_node.TabletSignupNode()

    @resource.child()
    def ops(self, request, segments):
        """Hands control of everything under '/ops' to GameNode which
        is in front/resource/game_node.py"""
        return game_node.GameNode()

    @resource.child()
    def api(self, request, segments):
        """Handles everything under /api"""
        return api_node.APINode()

    @resource.child()
    def service(self, request, segments):
        """Handles everything under /service, which starts the path for
        all web services. e.g., /service/renderer/..."""
        return ServiceNode()

    @resource.child()
    def edmodo(self, request, segments):
        """Handles everything under /edmodo"""
        return edmodo_node.EdmodoNode()

    # Verification links: These are used by Google or other third-party websites to verify
    # website ownership.
    @resource.child('google6d8e089d8c46c7d0.html')
    @templating.page('verification/google6d8e089d8c46c7d0.html')
    def verify_google(self, request, segments):
        return {}

    @auth.authentication_required
    @resource.child()
    def protected(self, request, segments):
        """This exists only for testing the authentication system.  Note that
        in a slight variation on the normal dispatch rules, this returns a
        function (defined at the bottom of the file).   It's basically a shorter
        implementation."""
        return http.ok([('content-type', 'text/html')], "<html><body>Protected</body></html>")

    @resource.child()
    def health_check(self, request, segments):
        """This resource is checked regularly by the Elastic Load Balancer in production.
           Any 400+/500+ HTTP response from this resource is interpreted as the app being down and
           the instance is marked as unhealthy and removed from the load balancer.
           FUTURE: Consider performing additional checks in those resource (database health?)."""
        return http.ok([('content-type', 'text/html')], "<html><body>Healthy</body></html>")

    @auth.authentication_required
    @auth.admin_required
    @resource.child()
    def admin(self, request, segments):
        """The Admin node handles all /admin requests."""
        return admin_node.AdminNode()

class ServiceNode(resource.Resource):
    @resource.child()
    def renderer(self, request, segments):
        return renderer_node.RendererNode()
