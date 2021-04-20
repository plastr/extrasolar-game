# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""This file contains a relatively complete, if crappy, password authentication 
scheme.  It tries to be pretty independent from the rest of the codebase, only 
using Restish and the bare minimum of library functions.
"""
import bcrypt
import facebook
from restish import http, resource, templating

from front import Constants
from front.lib import db, get_uuid, urls, forms, utils, patterns, email_module
from front.models import user as user_module
from front.resource.auth import log_user_in, log_user_out

import logging
logger = logging.getLogger(__name__)

SIGNUPS_ENABLED = None
HASH_ROUNDS = None
def init_module(hash_rounds, signups_enabled):
    global HASH_ROUNDS, SIGNUPS_ENABLED
    HASH_ROUNDS = int(hash_rounds)
    SIGNUPS_ENABLED = signups_enabled

def password_hash(password):
    """Generates a 60-character password hash for the given password.
    Uses the adaptive bcrypt algorithm:
    http://en.wikipedia.org/wiki/Bcrypt"""
    if isinstance(password, unicode):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, bcrypt.gensalt(HASH_ROUNDS))

def check_password(password, hashed):
    if isinstance(password, unicode):
        password = password.encode('utf-8')
    return bcrypt.hashpw(password, hashed) == hashed

def verify_password_for_email(ctx, email, password):
    """ Verify the email is an existing user and the password hash matches. """
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, "get_user_password_by_email", email=email)
    assert len(rows) <= 1
    if len(rows) == 0:
        return False, None
    row = rows[0]
    return check_password(password, row['password']), get_uuid(row['user_id'])

def log_user_in_and_redirect(request, user_id):
    """ Log the given user_id in and redirect to the root or to an optionally requested next page
        provided in the request query parameter identified by the urls.ORIGINAL_URL_PARAM key. """
    log_user_in(request, user_id)
    return http.see_other(str(request.GET.get(urls.ORIGINAL_URL_PARAM, urls.root())))

def index_login_and_signup_template_params(request, fields=None):
    """ Return all template fields required for both the login and signup forms (for the root index.html page). """
    if fields is None: fields = {}
    fields.update(RootSignupNode.default_template_params(request))
    fields.update(RootLoginNode.default_template_params(request))
    return fields

def insert_password_user(ctx, email, password, first_name, last_name, invite=None, gift=None, mark_valid=False):
    """ Insert the bare users and users_password entries for a new user. Intended to be used only
        by this module and unit tests.
        If mark_valid is True, the user will start with the 'valid' field set to 1, meaning that
        the email address has been validated etc.
        :param invite: An optional Invite object if this new user signed up via an invitation.
        :param gift: An optional Gift object if this new user signed up redeeming a gift (either direct or via invite)."""
    user_id = user_module.insert_new_user(ctx, email, first_name, last_name, invite=invite, gift=gift, mark_valid=mark_valid)
    db.run(ctx, "insert_user_password", user_id=user_id, password=password_hash(password))
    return user_id

def insert_facebook_user(ctx, email, facebook_uid, first_name, last_name, invite=None, gift=None, mark_valid=False):
    """ Insert the bare users and users_facebook entries for a new user. Intended to be used only
        by this module and unit tests.
        If mark_valid is True, the user will start with the 'valid' field set to 1, meaning that
        the email address has been validated etc.
        :param invite: An optional Invite object if this new user signed up via an invitation.
        :param gift: An optional Gift object if this new user signed up redeeming a gift (either direct or via invite)."""
    user_id = user_module.insert_new_user(ctx, email, first_name, last_name, invite=invite, gift=gift, mark_valid=mark_valid, auth="FB")
    db.run(ctx, "insert_user_facebook", user_id=user_id, uid=facebook_uid)
    return user_id

## Abstract base signup and login nodes.
class _SignupUserBase(resource.Resource):
    """ This is a baseclass node, meant to hold the common functionality used when signing up a user
        shared by specific subclass nodes, like the RootSignup and InviteSignupNode nodes. """
    # These are the common form fields used by all nodes performing signup operations.
    FIELDS = ['form_type']
    PASSWORD_FIELDS = ['signup_email', 'signup_password', 'first_name', 'last_name']
    FACEBOOK_FIELDS = ['facebook_token']
    # Optionally, additional signup form fields can be required. by a subclass.
    EXTRA_FIELDS = []
    # This is the name of the template file used when showing the subclasses forms and views,
    # including error messages.
    TEMPLATE = None

    def extra_user_params(self):
        """ A subclass can optionally provide additional parameters to the various user creation functions
            as keyword arguments, e.g. an invitation object. """
        return {}

    def validate_extra_fields(self, request, fields):
        """ If a subclass has additional form fields, override this method to perform validation
            of those fields.
            Returns an 'ok' status (True/False), and if False, an error message as the second argument. """
        return True, None

    def extra_template_params(self, request):
        """ A subclass can optionally provide additional template parameters here. """
        return {}

    @classmethod
    def signup_form_action_url(cls, request):
        """ A subclass can optionally change the URL that the signup form action points at.
            Defaults to be the same page as the original request. """
        return request.path_qs

    def user_already_exists(self, request, user_id, fields):
        """ A subclass can optionally change this default behavior of what happens if the user credentials
            being signed up are already a valid, existing user. """
        return log_user_in_and_redirect(request, user_id)

    def user_signup_complete(self, request, user):
        """ A subclass can optionally change this default behavior of what happens when a user has been signed up. """
        return log_user_in_and_redirect(request, user.user_id)

    ## End subclass override variables and methods.

    @classmethod
    def default_template_params(cls, request):
        """ Return a new dict of the required template fields for this page. """
        default_fields = dict([(f, '') for f in cls.FIELDS + cls.PASSWORD_FIELDS + cls.FACEBOOK_FIELDS + cls.EXTRA_FIELDS])
        # Add the signup_form_action_url
        default_fields['signup_form_action_url'] = cls.signup_form_action_url(request)
        default_fields['facebook_login_url'] = cls.signup_form_action_url(request)
        return default_fields

    def template_params(self, request, fields={}):
        """ Return all the fields and values required for this signup page. Override values by providing 'fields'. """
        default_fields = self.default_template_params(request)
        # Include any extra fields.
        default_fields.update(self.extra_template_params(request))
        # Override with any provided values.
        default_fields.update(fields)
        return default_fields

    @resource.POST()
    def post(self, request):
        # Make sure all the required form data was provided. Different signup types have different requirements.
        ok, fields = forms.fetch(request, self.FIELDS)
        if ok and fields['form_type'] == 'facebook':
            ok, fields = forms.fetch(request, self.FIELDS + self.FACEBOOK_FIELDS + self.EXTRA_FIELDS)
        elif ok and fields['form_type'] == 'signup':
            ok, fields = forms.fetch(request, self.FIELDS + self.PASSWORD_FIELDS + self.EXTRA_FIELDS)
        else:
            ok = False  # Unexpected or undeclared form_type.

        if not ok:
            # Invalid signup form, let the user try again by rendering the page
            # with the data they tried to submit already populated.
            fields['signup_error'] = utils.tr("Required data not provided, try again.")
            content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
            return http.ok([('content-type', 'text/html')], content)

        if fields['form_type'] == 'signup':
            # Enforce maximum field lengths.
            # Strip the email and name fields of whitespace and lowercase the email address.
            email      = fields['signup_email'][:Constants.MAX_LEN_EMAIL].strip().lower()
            password   = fields['signup_password'][:Constants.MAX_LEN_PASS]
            first_name = fields['first_name'][:Constants.MAX_LEN_FIRST].strip()
            last_name  = fields['last_name'][:Constants.MAX_LEN_LAST].strip()

            # If the email address doesn't look right. Return an error message to the form.
            if not patterns.is_email_address(email):
                fields['signup_error'] = utils.tr("Email address does not appear valid.")
                content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
                return http.ok([('content-type', 'text/html')], content)

        elif fields['form_type'] == 'facebook':
            # Authenticate the user with the Facebook API. We need to make sure that the token is legit
            # and extend access from a short-term to long-term token.
            graph = facebook.GraphAPI(fields['facebook_token'])
            profile = graph.get_object('me')

            # TODO: If we want to access the Facebook API later, exchange our short-term token for a
            # long-term token and save it in the users_facebook table.
            #conf = request.environ['front.config']
            #response = graph.extend_access_token(conf['template.fb_application_id'], conf['fb.application_secret'])
            #access_token = response['access_token']
            
            # If a Facebook-linked account exist for this user, skip the rest of the signup process.
            # Note that user_already_exists can be overridden by a subclass to do things like gift code validation.
            user = user_module.user_from_facebook_uid(request, profile['id'])
            if user:
                return self.user_already_exists(request, user.user_id, fields)

            # There is no account for this user, so we'll create one.
            # Enforce maximum field lengths.
            # Strip the email and name fields of whitespace and lowercase the email address.
            email = None
            if 'email' in profile.keys():
                email    = profile['email'][:Constants.MAX_LEN_EMAIL].strip().lower()
            facebook_uid = profile['id']
            first_name   = profile['first_name'][:Constants.MAX_LEN_EMAIL].strip()
            last_name    = profile['last_name'][:Constants.MAX_LEN_EMAIL].strip()
        else:
            assert(False)  # Unexpected form_type

        # Validate any additional fields a subclass might require.
        ok, result = self.validate_extra_fields(request, fields)
        if not ok:
            return result

        # If this email is already assigned to a user, attempt to login the user using the provided password.
        # If the password is invalid, return an error indicating this email was already used.
        with db.conn(request) as ctx:
            if email != None and db.row(ctx, "user_email_exists", email=email)['exist']:
                # If we're attempting a Facebook login, return an appropriate warning.
                if fields['form_type'] == 'facebook':
                    # Revoke Login (https://developers.facebook.com/docs/facebook-login/permissions/v2.1#revokelogin)
                    status = graph.delete_object('/%s/permissions' % (facebook_uid))
                    if status == False:
                        fields['facebook_error'] = utils.tr("The email address for your Facebook account (%s) is already associated with a different account. Attempt to revoke login failed." % email);
                    else:
                        fields['facebook_error'] = utils.tr("The email address for your Facebook account (%s) is already associated with a different account. Please try logging in with the main login form instead." % email)
                    content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
                    return http.ok([('content-type', 'text/html')], content)

                # If no email matched or the hash did not match, return 401.
                valid, user_id = verify_password_for_email(request, email, password)
                if not valid:
                    fields['signup_error'] = utils.tr("Email %s already taken" % email)
                    content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
                    return http.ok([('content-type', 'text/html')], content)

                # If the password matches, log the user in and redirect to homepage or requested next page
                # as the default behavior or do whatever a subclass override decides.
                return self.user_already_exists(request, user_id, fields)

            if fields['form_type'] == 'facebook':
                # Insert the users_facebook row used for authentication.
                new_id = insert_facebook_user(ctx, email, facebook_uid, first_name, last_name, **self.extra_user_params())
            else:
                # Insert the users_password row used for authentication.
                new_id = insert_password_user(ctx, email, password, first_name, last_name, **self.extra_user_params())

            # And then perform additional user setup, including creating the users row
            # and the initial gamestate data.
            user = user_module.new_user_setup(ctx, new_id, **self.extra_user_params())

            # If a campaign_name was passed through in a query parameter
            # save that as user metadata.
            campaign_name = request.GET.get(urls.CAMPAIGN_NAME_PARAM, None)
            if campaign_name is not None:
                user.add_metadata("MET_CAMPAIGN_NAME", campaign_name)

        # After signup, log the user in and redirect to homepage or requested next page.
        return self.user_signup_complete(request, user)

class _LoginUserBase(resource.Resource):
    # These are the common form fields used by all nodes performing login operations.
    FIELDS = ['login_email', 'login_password']
    # This is the name of the template file used when showing the subclasses forms and views,
    # including error messages.
    TEMPLATE = None

    def extra_template_params(self, request):
        """ A subclass can optionally provide additional template parameters here. """
        return {}

    @classmethod
    def login_form_action_url(cls, request):
        """ A subclass can optionally change the URL that the login form action points at.
            Defaults to be the same page as the original request. """
        return request.path_qs

    def user_complete_login(self, request, user_id, fields):
        """ A subclass can optionally change this default behavior of what happens when a user is ready to be logged in. """
        return log_user_in_and_redirect(request, user_id)

    ## End subclass override variables and methods.

    @resource.POST()
    def post(self, request):
        # Route Facebook login attempts through the signup node.
        ok, fields = forms.fetch(request, ['form_type'])
        if ok and fields['form_type'] == "facebook":
            return RootSignupNode()

        ok, fields = forms.fetch(request, self.FIELDS)
        if not ok:
            fields['login_error'] = utils.tr("Required data not provided, try again.")
            content = templating.render(request, self.TEMPLATE, self.template_params(request, fields))
            return http.unauthorized([('content-type', 'text/html')], content)

        # Enforce maximum field lengths.
        # Strip the email field of whitespace and lowercase the email address.
        email    = fields['login_email'][:Constants.MAX_LEN_EMAIL].strip().lower()
        password = fields['login_password'][:Constants.MAX_LEN_PASS]

        # Verify the password hash matches.
        valid, user_id = verify_password_for_email(request, email, password)
        # If no email matched or the hash did not match, return 401.
        if not valid:
            template_fields = {'login_email':email, 'login_error': utils.tr("Email or password incorrect")}
            content = templating.render(request, self.TEMPLATE, self.template_params(request, template_fields))
            return http.unauthorized([('content-type', 'text/html')], content)

        # If the password matches, log the user in and redirect to homepage or requested next page.
        return self.user_complete_login(request, user_id, fields)

    @classmethod
    def default_template_params(cls, request):
        """ Return a new dict of the required template fields for this page. """
        default_fields = dict([(f, '') for f in cls.FIELDS])
        # Add the login_form_action_url
        default_fields['login_form_action_url'] = cls.login_form_action_url(request)
        default_fields['facebook_login_url'] = cls.login_form_action_url(request)
        # If a campaign name was passed to us, pass it along to the demo_url with "_demo" appended to it.
        campaign_id = urls.campaign_name_from_path_qs(request.path_qs)
        if campaign_id:
            default_fields['demo_url'] = urls.add_campaign_name_url_param(urls.demo(), campaign_id+'_demo')
        else:
            default_fields['demo_url'] = urls.demo()
        return default_fields

    def template_params(self, request, fields={}):
        """ Return all the fields required for the login form. Override values by providing fields. """
        default_fields = self.default_template_params(request)
        # Include any extra fields.
        default_fields.update(self.extra_template_params(request))
        # Override with any provided values.
        default_fields.update(fields)
        return default_fields


## Signup nodes.
class RootSignupNode(_SignupUserBase):
    TEMPLATE = 'index.html'

    def extra_template_params(self, request):
        params = {'signups_enabled': SIGNUPS_ENABLED,
                  'show_login_header': True}
        # As the template is index.html need to include the blank login fields.
        params.update(RootLoginNode.default_template_params(request))
        return params

    # Fail any attempt at a POST to signup page if signups are disabled.
    def validate_extra_fields(self, request, fields):
        assert SIGNUPS_ENABLED, "Signups are disabled."
        return True, None


## Login nodes.
class RootLoginNode(_LoginUserBase):
    TEMPLATE = 'index.html'

    def extra_template_params(self, request):
        params = {'signups_enabled': SIGNUPS_ENABLED,
                  'show_login_header': True}
        # As the template is index.html need to include the blank signup fields.
        params.update(RootSignupNode.default_template_params(request))
        return params

class SimpleLoginNode(_LoginUserBase):
    TEMPLATE = 'login.html'

    @resource.GET()
    def get(self, request):
        return http.ok([('content-type', 'text/html')], templating.render(request, self.TEMPLATE, self.template_params(request)))

class FacebookLoginNode(_LoginUserBase):
    TEMPLATE = 'login_fb.html'

    @resource.GET()
    def get(self, request):
        return http.ok([('content-type', 'text/html')], templating.render(request, self.TEMPLATE, self.template_params(request)))

## Logout nodes.
class LogoutNode(resource.Resource):
    """
    A user can logout either by POSTing or GETing /logout.
    The former should be used from /ops to keep things controllable from the JS if need be,
    the latter is useful for development/testing.
    """
    @resource.POST()
    def post(self, request):
        log_user_out(request)
        return http.see_other(urls.root())

    @resource.GET()
    def get(self, request):
        log_user_out(request)
        return http.see_other(urls.root())

## Password reset nodes.
class RequestPasswordResetNode(resource.Resource):
    @resource.GET()
    @templating.page('request_password_reset.html')
    def get(self, request):
        # Short cut if there was a ?success query parameter passed. Display a success message.
        if 'success' in request.GET:
            return {'request_was_sent': True}
        if 'no_user' in request.GET:
            return {'error': utils.tr("There is no user for that email.")}
        if 'auth' in request.GET:
            auth_type = request.GET.get('auth', 'PASS')
            if auth_type == 'FB':
                return {'error': utils.tr("The user for the email you entered logs in with Facebook. Unable to reset password.")}
            if auth_type == 'EDMO':
                return {'error': utils.tr("The user for the email you entered logs in with Edmodo. Unable to reset password.")}
            return {'error': utils.tr("The user for the email you entered doesn't login with the password form. Unable to reset password.")}
        return {}

    @resource.POST()
    def post(self, request):
        ok, fields = forms.fetch(request, ['email'])
        if ok:
            email = fields['email']
            # Load the user object from the email address. Redirect to GET handler above
            # with error query parameter if no user for that email.
            user = user_module.user_from_email(request, email)
            if user is None:
                return http.see_other(urls.add_query_param_to_url(request.path_qs, no_user=1))
            elif user.auth != "PASS":
                return http.see_other(urls.add_query_param_to_url(request.path_qs, auth=user.auth))

            # Send the email with the reset URL.
            email_module.send_now(request, user, "EMAIL_PASSWORD_RESET")
            # Add the 'success' query parameter which is detected by the GET handler above.
            return http.see_other(urls.add_query_param_to_url(request.path_qs, success=1))
        else:
            return http.bad_request([('content-type', 'text/html')], "Bad parameters.")

class ResetPasswordNode(resource.Resource):
    def __init__(self, user_id, token, timestamp):
        self.user_id = user_id
        self.token = token
        self.timestamp = timestamp

    @resource.GET()
    @templating.page('password_reset.html')
    def get(self, request):
        # Short cut if there was a ?success query parameter passed. Display a succes message
        # and a link to the ops page.
        if 'success' in request.GET:
            return {'password_was_changed': True}

        # Verify the user_id is a real user.
        user = user_module.user_from_context(request, self.user_id, check_exists=True)
        if user is None:
            return {'error': utils.tr("This user does not exist.")}

        # And that the token is valid and not expired.
        if not user.is_valid_password_reset_token(self.token, self.timestamp):
            logger.error("Invalid token when attempting password reset, expired? (%s, %s)", self.user_id, self.token)
            return {'error': utils.tr("Password reset link has expired or is invalid.")}

        # Data looks good, display the reset password form.
        return {'user': user}

    @resource.POST()
    def post(self, request):
        # Double check the URL parameters and load the user.
        user = user_module.user_from_context(request, self.user_id, check_exists=True)
        if user is None:
            return http.bad_request([('content-type', 'text/html')], "Invalid request.")

        if not user.is_valid_password_reset_token(self.token, self.timestamp):
            return http.bad_request([('content-type', 'text/html')], "Invalid request.")

        ok, fields = forms.fetch(request, ['new_password'])
        if ok:
            password = fields['new_password'][:Constants.MAX_LEN_PASS]
            # Change the password after hashing, and log the user in.
            user.change_password_hash(password_hash(password))
            log_user_in(request, user.user_id)
            # Add the 'success' query parameter which is detected by the GET handler above.
            return http.see_other(urls.add_query_param_to_url(request.path_qs, success=1))
        else:
            return http.bad_request([('content-type', 'text/html')], "Bad parameters.")
