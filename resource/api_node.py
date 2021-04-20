# Copyright (c) 2010-2014 Lazy 8 Studios, LLC.
# All rights reserved.
import json
import facebook

from restish import resource, http
from front import Constants
from front.lib import db, utils, forms, patterns, urls
from front.resource import auth, ops_api_node, public_api_node
from front.resource.auth import log_user_in
from front.resource.auth import password as password_node
from front.models import user as user_module

def json_response_success(user):
    """
    Return a successful JSON response for this user. If the user is not yet valid, include the
    first name and backdoor link so that these can be displayed in a message from Kryptex.
    """
    assert(user)
    if user.valid:
        return http.ok([('content-type', 'text/html')], json.dumps({"status": "ok", "valid":1}))
    else:
        return http.ok([('content-type', 'text/html')], json.dumps({"status": "ok", "valid":0,
            "first_name":user.first_name, "url_validate":user.url_api_validate()}))

def json_response_error(error_message):
    """
    Return a JSON error message.
    """
    return http.unauthorized([('content-type', 'text/html')], json.dumps({"status": "error", "error_message":error_message}))

def is_app_version_ok(version):
    """
    Native apps should always send the app_version when they send a request to the API.
    This function returns True if the version is compatible, false otherwise.
    """
    if version=="1.0":
        return True
    return False

class APINode(resource.Resource):
    # All resources served from /api/ops require the user to be authenticated.
    @auth.authentication_required_json
    @resource.child()
    def ops(self, request, segments):
        return ops_api_node.OpsAPINode()

    @resource.child()
    def public(self, request, segments):
        return public_api_node.PublicAPINode()

    @resource.child('login')
    def login(self, request, segments):
        return APILoginNode()

    @resource.child('signup')
    def signup(self, request, segments):
        return APISignupNode()

    @resource.child('backdoor/{token}')
    def backdoor(self, request, segments, token):
        # No valid session? Return an error message.
        if not auth.user_present(request):
            return json_response_error("No valid user session was present.")

        u = user_module.user_from_request(request)
        # If somehow this user was deleted (in development), return an error message.
        if u is None:
            return json_response_error("No valid user.")

        # If user is already validated.
        if u.valid:
            return json_response_success(u)

        # Otherwise, attempt to validate the user. If the token is invalid or was for another
        # user, return an error message.
        if not u.validate_with_token(token):
            return json_response_error("Invalid authentication token.")

        # Otherwise, the user has been marked valid. Next steps, display the backdoor success message.
        return json_response_success(u)

    @resource.child('check_session')
    def check_session(self, request, segments):
        """
        Check if there is a valid session associated with this HTTP request.
        """
        app_version = request.GET.get('version', None)
        if not is_app_version_ok(app_version):
            return json_response_error("Your app is out of date. Please update it to the latest version to continue.")

        if auth.user_present(request):
            user = user_module.user_from_request(request)
            return json_response_success(user)
        else:
            return json_response_error("No valid session.")

class APILoginNode(resource.Resource):
    @resource.POST()
    def post(self, request):
        """
        Even though this is an API node accessed through an AJAX query, note that we
        respond with HTTP rather than JSONP so that we can properly set the session
        cookie on a successful login.
        """
        ok, fields = forms.fetch(request, ['login_email', 'login_password', 'form_type', 'version'])
        if not ok:
            return json_response_error("Required data not provided.")

        if not is_app_version_ok(fields['version']):
            return json_response_error("Your app is out of date. Please update it to the latest version to continue.")

        # Enforce maximum field lengths.
        # Strip the email field of whitespace and lowercase the email address.
        email    = fields['login_email'][:Constants.MAX_LEN_EMAIL].strip().lower()
        password = fields['login_password'][:Constants.MAX_LEN_PASS]

        # Verify the password hash matches.
        valid, user_id = password_node.verify_password_for_email(request, email, password)
        # If no email matched or the hash did not match, return an error message.
        if not valid:
            return json_response_error("Incorrect email or password.")

        # If the password matches, log the user in and return success.
        log_user_in(request, user_id)
        user = user_module.user_from_request(request)
        if user is None:
            return json_response_error("Internal error. No valid user.")

        return json_response_success(user)

class APISignupNode(resource.Resource):
    @resource.POST()
    def post(self, request):
        """
        Even though this is an API node accessed through an AJAX query, note that we
        respond with HTTP rather than JSONP so that we can properly set the session
        cookie on a successful login.
        """
        # Make sure all the required form data was provided. Different signup types have different requirements.
        ok, fields = forms.fetch(request, ['form_type'])
        if ok and fields['form_type'] == 'facebook':
            ok, fields = forms.fetch(request, ['facebook_token', 'form_type', 'version'])
        elif ok and fields['form_type'] == 'signup':
            ok, fields = forms.fetch(request, ['first_name', 'last_name', 'signup_email', 'signup_password', 'form_type', 'version'])
        else:
            ok = False  # Unexpected or undeclared form_type.

        if not ok:
            # Invalid signup data. Return an error.
            return json_response_error("Required data was not provided.")

        if not is_app_version_ok(fields['version']):
            return json_response_error("Your app is out of date. Please update it to the latest version to continue.")

        if fields['form_type'] == 'signup':
            # Enforce maximum field lengths.
            # Strip the email and name fields of whitespace and lowercase the email address.
            email      = fields['signup_email'][:Constants.MAX_LEN_EMAIL].strip().lower()
            password   = fields['signup_password'][:Constants.MAX_LEN_PASS]
            first_name = fields['first_name'][:Constants.MAX_LEN_FIRST].strip()
            last_name  = fields['last_name'][:Constants.MAX_LEN_LAST].strip()

            # If the email address doesn't look right. Return an error message to the form.
            if not patterns.is_email_address(email):
                return json_response_error("Email address does not appear valid.")

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
                log_user_in(request, user.user_id)
                return json_response_success(user)

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

        # If this email is already assigned to a user, attempt to login the user using the provided password.
        # If the password is invalid, return an error indicating this email was already used.
        with db.conn(request) as ctx:
            if email != None and db.row(ctx, "user_email_exists", email=email)['exist']:
                # If we're attempting a Facebook login, return an appropriate warning.
                if fields['form_type'] == 'facebook':
                    # Revoke Login (https://developers.facebook.com/docs/facebook-login/permissions/v2.1#revokelogin)
                    status = graph.delete_object('/%s/permissions' % (facebook_uid))
                    if status == False:
                        response = utils.tr("The email address for your Facebook account (%s) is already associated with a different account. Attempt to revoke login failed." % email);
                    else:
                        response = utils.tr("The email address for your Facebook account (%s) is already associated with a different account. Please try logging in with the main login form instead." % email)
                    return json_response_error(response)

                # If no email matched or the hash did not match, return 401.
                valid, user_id = password_node.verify_password_for_email(request, email, password)
                if not valid:
                    return json_response_error("Email %s already taken." % email)

                # If the password matches, log the user in and skip the backdoor step.
                log_user_in(request, user_id)
                user = user_module.user_from_request(request)
                return json_response_success(user)

            if fields['form_type'] == 'facebook':
                # Insert the users_facebook row used for authentication.
                new_id = password_node.insert_facebook_user(ctx, email, facebook_uid, first_name, last_name)
            else:
                # Insert the users_password row used for authentication.
                new_id = password_node.insert_password_user(ctx, email, password, first_name, last_name)

            # And then perform additional user setup, including creating the users row
            # and the initial gamestate data.
            user = user_module.new_user_setup(ctx, new_id)

            # If a campaign_name was passed through in a query parameter
            # save that as user metadata.
            campaign_name = request.GET.get(urls.CAMPAIGN_NAME_PARAM, None)
            if campaign_name is not None:
                user.add_metadata("MET_CAMPAIGN_NAME", campaign_name)

        # After signup, log the user in and return success.
        log_user_in(request, user.user_id)
        return json_response_success(user)
