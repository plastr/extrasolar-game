# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import http, resource, templating

from front.lib import utils
from front.models import user as user_module
from front.resource.auth import password

import logging
logger = logging.getLogger(__name__)

## Invite nodes.
class InviteSignupNode(password._SignupUserBase):
    """ This node is used for accepting an invitation which does not have a gift. """
    TEMPLATE = 'invite_signup.html'

    def __init__(self, invite):
        self.invite = invite

    def extra_template_params(self, request):
        return {'invite': self.invite}

    def extra_user_params(self):
        return {'invite': self.invite}

    @resource.GET()
    def get(self, request):
        content = templating.render(request, self.TEMPLATE, self.template_params(request, _signup_fields_from_invite(self.invite)))
        return http.ok([('content-type', 'text/html')], content)


## Gift nodes.
class GiftChoiceNode(resource.Resource):
    """ This node is used for redeeming a gift or accepting invitation with a gift. """
    TEMPLATE = "gift_choice.html"

    def __init__(self, gift, invite=None):
        self.gift = gift
        self.invite = invite

    @resource.GET()
    def get(self, request):
        ok, error_response = self._is_gift_valid(request)
        if not ok: return error_response
        params = { 'gift': self.gift }
        if self.invite is not None:
            params['invite'] = self.invite
        return http.ok([('content-type', 'text/html')], templating.render(request, self.TEMPLATE, params))

    @resource.child()
    def new(self, request, segments):
        ok, error_response = self._is_gift_valid(request)
        if not ok: return error_response
        return GiftRedeemSignupNode(self.gift, self.invite), segments

    @resource.child()
    def existing(self, request, segments):
        ok, error_response = self._is_gift_valid(request)
        if not ok: return error_response
        return GiftRedeemLoginNode(self.gift, self.invite), segments

    def _is_gift_valid(self, request):
        if self.gift.was_redeemed():
            params = {'gift_error': utils.tr("This gift has already been redeemed.")}
            content = templating.render(request, self.TEMPLATE, params)
            return False, http.ok([('content-type', 'text/html')], content)
        return True, None

class GiftRedeemSignupNode(password._SignupUserBase):
    TEMPLATE = 'gift_signup.html'

    def __init__(self, gift, invite=None):
        self.gift = gift
        self.invite = invite

    def extra_user_params(self):
        return {'invite': self.invite, 'gift': self.gift}

    # If the redeemer signs up in with an existing users credentials, then attempt to redeem the gift as them.
    def user_already_exists(self, request, user_id, fields):
        user = user_module.user_from_context(request, user_id)
        ok, error = self.gift.can_user_redeem(user)
        if not ok:
            fields['signup_error'] = error
            content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
            return http.ok([('content-type', 'text/html')], content)
        self.gift.mark_redeemed_by_user(user)
        # If the gift being redeemed was attached to an invite, then mark that invite as accepted.
        if self.invite is not None:
            self.invite.mark_accepted_by_user(user)
        return password.log_user_in_and_redirect(request, user_id)

    @resource.GET()
    def get(self, request):
        fields = {}
        # If there is an invite for this gift, populate the signup form with the invite data.
        if self.invite is not None:
            fields.update(_signup_fields_from_invite(self.invite))
        content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
        return http.ok([('content-type', 'text/html')], content)

class GiftRedeemLoginNode(password._LoginUserBase):
    TEMPLATE = 'gift_login.html'

    def __init__(self, gift, invite=None):
        self.gift = gift
        self.invite = invite

    def user_complete_login(self, request, user_id, fields):
        user = user_module.user_from_context(request, user_id)

        ok, error = self.gift.can_user_redeem(user)
        if not ok:
            fields['login_error'] = error
            # Zero out the password
            fields['login_password'] = ""
            content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
            return http.ok([('content-type', 'text/html')], content)
        self.gift.mark_redeemed_by_user(user)
        # If the gift being redeemed was attached to an invite, then mark that invite as accepted.
        # Ordinarily the user would have gone through the /invite URL but this is a safety catch in case they
        # somehow find the gift_id and go through the /gift URL.
        if self.invite is not None:
            self.invite.mark_accepted_by_user(user)
        return password.log_user_in_and_redirect(request, user_id)

    def extra_template_params(self, request):
        # Route Facebook gift redemption through the new (Signup) rather than the existing (Login) node.
        params = {'facebook_login_url': request.path_qs.replace('/existing', '/new')}
        return params

    @resource.GET()
    def get(self, request):
        content = templating.render(request, self.TEMPLATE, self.template_params(request))
        return http.ok([('content-type', 'text/html')], content)

## Utility functions
def _signup_fields_from_invite(invite):
    """ Return the signup form fields derived from the given invite object. """
    return {
        'signup_email': invite.recipient_email,
        'first_name':   invite.recipient_first_name,
        'last_name':    invite.recipient_last_name,
        # Pass the invite_token as a fake 'secret code' value to display to the invited user to
        # make the invitation seem more special and secretive.
        'invite_code':  invite.invite_token
    }
