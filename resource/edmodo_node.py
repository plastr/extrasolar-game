# Copyright (c) 2014 Lazy 8 Studios, LLC.
# All rights reserved.
from restish import http, resource, templating
from front import Constants
from front.lib import edmodo, forms, urls, db, gametime, xjson
from front.models import user as user_module
from front.models import voucher as voucher_module
from front.resource import auth, json_success
from front.resource.auth import password, log_user_in

# The Edmodo launch flow is slightly different than the typical login flow.
# The game is launched with a call to /edmodo/api/launch. At that time, if the Edmodo
# user doesn't yet have an account, a new account is created. On the landing page,
# players can see the YouTube teaser video and are asked to answer some
# survey questions. When they submit their application, they're directed to the
# 'unauthorized' page at /edmodo/unauthorized, where kryptex provides a backdoor link.

def insert_edmodo_user(ctx, email, edmodo_uid, first_name, last_name, user_type, user_token, access_token, sandbox, 
    invite=None, gift=None, mark_valid=False):
    """ Insert the bare users and users_edmodo entries for a new user. Intended to be used only
        by this module and unit tests.
        If mark_valid is True, the user will start with the 'valid' field set to 1, meaning that
        the email address has been validated etc.
        :param invite: An optional Invite object if this new user signed up via an invitation.
        :param gift: An optional Gift object if this new user signed up redeeming a gift (either direct or via invite)."""
    user_id = user_module.insert_new_user(ctx, email, first_name, last_name, invite=invite, gift=gift, mark_valid=mark_valid, auth="EDMO")
    db.run(ctx, "insert_user_edmodo", user_id=user_id, uid=edmodo_uid, user_type=user_type,
        user_token=user_token, access_token=access_token, sandbox=sandbox)
    return user_id

def _get_edmodo_server_and_key(request):
    # We need to use different servers and secret keys, depending on if this request is
    # coming from the Edmodo sandbox.
    conf = request.environ['front.config']
    edmodo_servers = conf['edmodo.servers'].split(',')
    edmodo_secret_keys = conf['edmodo.secret_keys'].split(',')
    use_sandbox = request.GET.get('sandbox', '0')
    if use_sandbox == '1':
        return {'sandbox':1, 'server':edmodo_servers[0], 'secret_key':edmodo_secret_keys[0]}
    else:
        return {'sandbox':0, 'server':edmodo_servers[1], 'secret_key':edmodo_secret_keys[1]}

class EdmodoNode(resource.Resource):
    @auth.authentication_required
    @resource.child()
    def unauthorized(self, request, segments):
        """Players who have not yet followed the backdoor link are direced to this page after
        visiting the launch page."""
        content = templating.render(request, 'unauthorized.html', {'user':user_module.user_from_request(request), 'kiosk_mode':'EDMODO'})
        return http.ok([('content-type', 'text/html')], content)

    @resource.child()
    def api(self, request, segments):
        return EdmodoAPINode()

    @resource.child()
    def cookie(self, request, segments):
        """ In order for your app to set cookies from within an iframe, newer versions of Safari
            require a cookie from your domain be set prior to your app loading. This page is launched
            as a pop-up by Edmodo in order to establish your app's ability to set cookies."""
        content = templating.render(request, 'edmodo_cookie.html', {})
        return http.ok([('content-type', 'text/html')], content)

class EdmodoAPINode(resource.Resource):
    """ /edmodo/api/install is called when a teacher tries to install the app for their group. """
    @resource.child()
    def install(self, request, segments):
        return EdmodoInstall()

    """ /edmodo/api/launch is called when a player launches in an iframe within Edmodo. """
    @resource.child()
    def launch(self, request, segments):
        return EdmodoLaunch()

class EdmodoInstall(resource.Resource):
    """ An Ajax POST call is made to /edmodo/api/install when a teacher tries to install the app
    for a new group. The group data isn't particularly important to us, so we just ignore it
    and return success. We'll treat group member logins as we do with Facebook and create an account
    when they first connect.
    Documentation: https://lazy8studios.edmodobox.com/home#/developer/api """
    @resource.POST()
    def post(self, request):
        edmodo_conf = _get_edmodo_server_and_key(request)

        # We expect that the 'install' data has been passed to us in the POST parameters.
        install = xjson.loads(request.POST['install'])
        if not ('user_token' in install and 'access_token' in install and 'groups' in install and type(install['groups']) is list):
            return json_success({'status':'failed', 'error_message':'Installation call had missing or improperly formatted parameters.'})
        user_token   = install['user_token']
        access_token = install['access_token']
        groups       = install['groups']

        try:
            # Initialize the Edmodo API helper.
            edmodoAPI = edmodo.EdmodoAPI(server=edmodo_conf['server'], api_version='v1.1')
            # Check with Edmodo's servers to make sure this is valid user data. If not, it should throw an exception.
            valid_user = edmodoAPI.get_object('/users', api_key=edmodo_conf['secret_key'], access_token=access_token, user_tokens='["%s"]' % user_token)
 
            # Insert the groups one at a time.
            with db.conn(request) as ctx:
                for group_id in groups:
                    try:
                        db.run(ctx, "insert_edmodo_group", group_id=group_id, sandbox=edmodo_conf['sandbox'], created=gametime.now())
                    except db.UnexpectedResultError:
                        json_success({'status':'failed', 'error_message':'Error while inserting group %d into database.' % group_id})

            return json_success({'status':'success'})

        except edmodo.EdmodoAPIError, e:
            return json_success({'status':'failed', 'error_message':'Edmodo API Error on app install: %s' % str(e)})

class EdmodoLaunch(resource.Resource):
    """ An Ajax POST call is made to /edmodo/api/launch when a player launches in an iframe
    within Edmodo.
    Documentation: https://lazy8studios.edmodobox.com/home#/developer/api """
    @resource.POST()
    def post(self, request):
        edmodo_conf = _get_edmodo_server_and_key(request)

        # We expect that the launch_key has been passed to us in the query string.
        launch_key = request.GET.get('launch_key', None)
        if launch_key is None:
            return http.bad_request([('content-type', 'text/html')], "Bad parameters.")

        try:
            # Initialize the Edmodo API helper.
            edmodoAPI = edmodo.EdmodoAPI(server=edmodo_conf['server'], api_version='v1.1')
            # Make sure we've been passed a valid launch key
            profile = edmodoAPI.get_object('/launchRequests', api_key=edmodo_conf['secret_key'], launch_key=launch_key)
            
        except edmodo.EdmodoAPIError, e:
            return http.bad_request([('content-type', 'text/html')], "Edmodo API Error: %s" % str(e))

        # We should now have a valid profile for an Edmodo user.
        with db.conn(request) as ctx:
            # If an Edmodo-linked account exist for this user, log the user in and redirect to the appropriate page.
            user = user_module.user_from_edmodo_uid(request, profile['user_id'])
            if user:
                # If we have a valid user matching this ID, update the users's launch key in the DB and log the user in.
                # For teachers, a valid launch key will be needed to retrieve the classroom data as part of the gamestate.
                log_user_in(request, user.user_id)
                db.run(ctx, "update_edmodo_access_token", user_id=user.user_id, access_token=profile['access_token'])
                if user.valid:
                    # If the user is already valid, redirect to root.
                    return http.see_other(str(request.GET.get(urls.ORIGINAL_URL_PARAM, urls.root())))
                else:
                    # Else render a custom template that serves as the Edmodo entry point.
                    content = templating.render(request, 'edmodo_launch.html', {'first_name':user.first_name})
                    return http.ok([('content-type', 'text/html')], content)

            # There is no account for this user, so we'll create one.
            # Enforce maximum field lengths.
            # Strip the email and name fields of whitespace and lowercase the email address.
            email = None
            if 'email' in profile.keys():
                email    = profile['email'][:Constants.MAX_LEN_EMAIL].strip().lower()
            edmodo_uid   = profile['user_id']
            first_name   = profile['first_name'][:Constants.MAX_LEN_EMAIL].strip()
            last_name    = profile['last_name'][:Constants.MAX_LEN_EMAIL].strip()
            user_type    = profile['user_type']
            user_token   = profile['user_token']
            access_token = profile['access_token']
            sandbox      = edmodo_conf['sandbox']

            # If this email is already assigned to a user, give a warning.
            if email != None and db.row(ctx, "user_email_exists", email=email)['exist']:
                content = """The email address for your Edmodo account (%s) is already associated with a different
                Extrasolar account. If you believe you've reached this message in error, please contact
                extrasolar-support@lazy8studios.com.""" % (email)
                return http.ok([('content-type', 'text/html')], content)
       
            # Insert the users_password row used for authentication.
            new_id = insert_edmodo_user(ctx, email, edmodo_uid, first_name, last_name, user_type, user_token, access_token, sandbox)

            # And then perform additional user setup, including creating the users row
            # and the initial gamestate data.
            user = user_module.new_user_setup(ctx, new_id)

            # Edmodo users should be created with an all-access voucher. Suppress the callbacks
            # so that the "Thanks for your purchase" message doesn't get sent.
            voucher_module.deliver_new_voucher(ctx, user, 'VCH_ALL_PASS', suppress_callbacks=True)

            # If a campaign_name was passed through in a query parameter
            # save that as user metadata.
            campaign_name = request.GET.get(urls.CAMPAIGN_NAME_PARAM, None)
            if campaign_name is not None:
                user.add_metadata("MET_CAMPAIGN_NAME", campaign_name)

            # After signup, log the new user in, overriding the default session parameters so that
            # the cookie expires at the end of the session.
            session = request.environ['beaker.session']
            session.cookie_expires = True
            log_user_in(request, new_id)

            # Render a custom template that serves as the Edmodo entry point.
            content = templating.render(request, 'edmodo_launch.html', {'first_name':user.first_name})
            return http.ok([('content-type', 'text/html')], content)

