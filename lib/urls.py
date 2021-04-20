# Copyright (c) 2010-2014 Lazy 8 Studios, LLC.
# All rights reserved.
'''
All URLs used by this sytem should be defined in this module.
'''
import urllib, urlparse

from front import VERSION
from front.lib import utils
from user_agents import parse

TOOLS_ABSOLUTE_ROOT = None
STRIPE_CHARGE_URL = None
def init_module(absolute_root, stripe_charge_url):
    global TOOLS_ABSOLUTE_ROOT, STRIPE_CHARGE_URL
    TOOLS_ABSOLUTE_ROOT = absolute_root
    STRIPE_CHARGE_URL = stripe_charge_url

## Root/base URLs.
def root():
    ''' Returns the URL for the root/login page. '''
    return "/"

def absolute_root(request):
    '''Fully-qualified http root to the requesting webpage.  e.g., http://www.extrasolar.com/'''
    return request.host_url

def static_root():
    ''' Fully-qualified http root that should be used for URLs that may not be called from the
        same domain. For instance, URLs that may be used by a native app.'''
    return TOOLS_ABSOLUTE_ROOT

def tools_absolute_root():
    '''Fully-qualified http root for use by tools only (when we don't have a request).'''
    return TOOLS_ABSOLUTE_ROOT

def static_url_version(url):
    ''' Add a query parameter to the given URL (a static resource) to force a new download if
        the application version changes. '''
    version_param = "%s%s" % (VERSION.rev, VERSION.date)
    return add_version_url_param(url, version_param)

def message_attachment_root():
    ''' Returns the absolute root URL for where the message attachments (e.g. PDFs) are served (S3).'''
    return 'https://s3-us-west-1.amazonaws.com/static.extrasolar.com/attachments'

## Email address
def email_address_store_support():
    return "store-support@extrasolar.com"

## Authentication
def auth_signup():
    return "/"

def auth_signup_complete():
    return "/signup_complete"

def auth_login():
    return "/"

def auth_login_simple():
    return "/login"

# Responds to both GET and POST
def auth_logout():
    return "/logout"

## Non-API public pages.
def ops():
    ''' Returns the URL for the operations/game root page. '''
    return "/ops/"

def user_public_profile(user_id):
    ''' Returns the URL for a user's public profile. '''
    return "/profile/%s" % utils.int_to_base62(user_id.int)

def user_public_profile_absolute(request, user_id):
    ''' Returns the absolute URL for a user's public profile. '''
    return absolute_root(request) + user_public_profile(user_id)

def target_public_photo(target_id):
    ''' Returns the URL for a target's public photo page. '''
    return "/photo/%s" % utils.int_to_base62(target_id.int)

def validate(token):
    '''
    Returns the URL that should be for validating a user account.
    :param token: str, The token needed to validate this user.
    '''
    return tools_absolute_root() + "/backdoor/" + token

def invite_accept(invite_id, token):
    '''
    Returns the URL that should be for accepting an invitation.
    :param token: str, The token needed to validate this invitation.
    '''
    return tools_absolute_root() + "/invite/%s/%s" % (utils.int_to_base62(invite_id.int), token)

def gift_redeem(gift_id, token):
    '''
    Returns the URL that should be for choosing how to redeeming a gift.
    :param token: str, The token needed to validate this gift.
    '''
    return tools_absolute_root() + "/gift/%s/%s" % (utils.int_to_base62(gift_id.int), token)

def gift_redeem_new_user(gift_id, token):
    '''
    Returns the URL that should be for redeeming a gift for a newly signed up user.
    :param token: str, The token needed to validate this gift.
    '''
    return gift_redeem(gift_id, token) + "/new"

def gift_redeem_existing_user(gift_id, token):
    '''
    Returns the URL that should be for redeeming a gift for an existing user.
    :param token: str, The token needed to validate this gift.
    '''
    return gift_redeem(gift_id, token) + "/existing"

def request_password_reset():
    '''
    Returns the URL for where a user can request a password reset.
    '''
    return "/reset"

def password_reset(user_id, token, timestamp):
    '''
    Returns the URL for resetting a user's password.
    :param token: str, The token needed to validate this user, base62 encoded.
    :param timestamp: str, The base62 encoded timestamp, from secure_tokens module.
    '''
    return tools_absolute_root() + "/reset/%s/%s/%s" % (utils.int_to_base62(user_id.int), token, timestamp)

def unsubscribe(user_id, token):
    '''
    Returns the URL for unsubscribing a user from all notifications without requiring password authentication.
    :param token: str, The token needed to validate this user, base62 encoded.
    '''
    return tools_absolute_root() + "/unsubscribe/%s/%s" % (utils.int_to_base62(user_id.int), token)

def kiosk():
    ''' Returns the URL for the kiosk mode signup page. '''
    return "/kiosk"

def kiosk_complete():
    ''' Returns the URL for the page to land on after the kiosk mode signup page is finished. '''
    return kiosk() + "/complete"

def kiosk_complete_exists():
    ''' Returns the URL for the page to land on if a kiosk signup user already exists. '''
    return add_query_param_to_url(kiosk_complete(), exists=1)

def tablet_signup():
    ''' Returns the URL for the tablet_signup page. '''
    return "/tablet_signup"

def tablet_signup_complete():
    ''' Returns the URL for the page to land on after the tablet_signup page is finished. '''
    return tablet_signup() + "/complete"

def tablet_signup_complete_exists():
    ''' Returns the URL for the page to land on if a tablet_signup user already exists. '''
    return add_query_param_to_url(tablet_signup_complete(), exists=1)

def demo():
    ''' Returns the URL for the demo mode signup page. '''
    return "/demo"

def demo_complete():
    ''' Returns the URL for the page to land on after the demo mode signup page is finished. '''
    return demo() + "/complete"

def demo_complete_exists():
    ''' Returns the URL for the page to land on if a demo signup user already exists. '''
    return add_query_param_to_url(demo_complete(), exists=1)

def map_tile_kiosk(request):
    ''' Returns the URL base for the map tiles that are used by the kiosk simulator. '''
    front_config = request.environ['front.config']
    return front_config.get('map_tile_kiosk_url')

def scenes_base():
    ''' The base URL pattern for locally served scene images. '''
    return "/img/scenes"

def scene(scene_name):
    '''
    Returns the URL that should be used to serve a specific scene images locally.
    :param scene_name: The name of the scene, without any image file extensions (e.g. t.jpg, png etc.)
    '''
    return "/img/scenes/%s" % scene_name

## OPS "Pages"
def ops_home():
    return tools_absolute_root() + "/ops/#home"
def ops_map():
    return tools_absolute_root() + "/ops/#map"
def ops_profile():
    return tools_absolute_root() + "/ops/#profile"
def ops_mail():
    return tools_absolute_root() + "/ops/#mail"
def ops_message(message_id):
    return tools_absolute_root() + "/ops/#message," + str(message_id)
def ops_tasks():
    return tools_absolute_root() + "/ops/#tasks"
def ops_task(mission_id):
    return tools_absolute_root() + "/ops/#task," + str(mission_id)
def ops_gallery():
    return tools_absolute_root() + "/ops/#gallery"
def ops_picture(target_id):
    return tools_absolute_root() + "/ops/#picture," + str(target_id)
def ops_catalog():
    return tools_absolute_root() + "/ops/#catalog"
def ops_species(species_id):
    return tools_absolute_root() + "/ops/#catalog," + str(species_id)
def ops_copyright():
    return tools_absolute_root() + "/ops/#copyright"

## Email URLs
def email_asset_base():
    ''' The base URL for images used by email templates '''
    return tools_absolute_root() + "/img/email"

## Make URLs fully-qualified for use in emails or external webpages.
# Note that the following 2 functions are identical but may change when we move assets to S3.
def fully_qualified_asset_url(url):
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return tools_absolute_root() + url

def fully_qualified_game_url(url):
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return tools_absolute_root() + url

## Shared URL parameters
# List all project-wide query parameter key names here.
ORIGINAL_URL_PARAM  = 'o'
CAMPAIGN_NAME_PARAM = 'c'
VERSION_URL_PARAM   = 'v'
def campaign_name_from_path_qs(path_qs):
    '''
    Extract the campaign name from the query string. If not found, return None.
    :param path_qs: The query string (e.g., ?c=my_campaign) for the URL.
    '''
    parsed = urlparse.parse_qs(urlparse.urlparse(path_qs).query)
    if CAMPAIGN_NAME_PARAM in parsed:
        return parsed[CAMPAIGN_NAME_PARAM][0]
    return None

def add_original_url_param(url, path):
    '''
    Use this query parameter in the auth system to signal where the user should be redirected to
    upon successful authentication.
    :param path: The relative URL to redirect to upon login/signup, e.g. /ops/.
    '''
    return add_query_param_to_url(url, **{ORIGINAL_URL_PARAM: path})

def add_campaign_name_url_param(url, campaign_name):
    '''
    Use this query parameter in the auth system to signal what marketing campaign the user came from.
    :param campaign_name: The name of the campaign.
    '''
    return add_query_param_to_url(url, **{CAMPAIGN_NAME_PARAM: campaign_name})

def add_version_url_param(url, version):
    '''
    Use this query parameter to make a static resource (js, css, image) be redownloaded whenever
    the provided version string changes (useful for production, usually based on VERSION values).
    :param campaign_name: The name of the campaign.
    '''
    return add_query_param_to_url(url, **{VERSION_URL_PARAM: version})

## Operations/Game API
def gamestate():
    ''' Returns the URL to load the gamestate as JSON. '''
    return "/api/ops/gamestate"

def fetch_chips():
    ''' Returns the URL where chip change data is loaded as JSON. '''
    return "/api/ops/fetch_chips"

def user_update_viewed_alerts_at():
    return "/api/ops/user/update_viewed_alerts_at"

def user_settings_notifications():
    return "/api/ops/user/settings/notifications"

def _rover_target_base(rover_id):
    '''
    The base URL pattern for rover target URLs.
    :param rover_id: UUID object for unique rover identifier.
    '''
    return "/api/ops/rover/%s/target" % (rover_id)

def rover_target_create(rover_id):
    '''
    Returns the URL that should be used to create a new target for a given rover.
    :param rover_id: UUID object for unique rover identifier.
    '''
    return _rover_target_base(rover_id)

def rover_target(rover_id, target_id):
    '''
    Returns the URL that should be used to get information and update a given target for a given rover.
    :param rover_id: UUID object for unique rover identifier.
    :param target_id: UUID object for unique target identifier.
    '''
    return "%s/%s" % (_rover_target_base(rover_id), target_id)

def rover_target_check_species(rover_id, target_id):
    '''
    Returns the URL that should be used to perform a check_species request on a given target
        for a given rover.
    :param rover_id: UUID object for unique rover identifier.
    :param target_id: UUID object for unique target identifier.
    '''
    return "%s/check_species" % (rover_target(rover_id, target_id))

def rover_target_abort(rover_id, target_id):
    '''
    Returns the URL that should be used to abort this given target for a given rover.
    :param rover_id: UUID object for unique rover identifier.
    :param target_id: UUID object for unique target identifier.
    '''
    return "%s/abort" % (rover_target(rover_id, target_id))

def rover_target_mark_viewed(rover_id, target_id):
    '''
    Returns the URL that should be used to perform a mark_viewed request on a given target
        for a given rover.
    :param rover_id: UUID object for unique rover identifier.
    :param target_id: UUID object for unique target identifier.
    '''
    return "%s/mark_viewed" % (rover_target(rover_id, target_id))

def rover_target_download_image(rover_id, target_id):
    '''
    Returns the URL that should be used to redirect to a download (content-disposition attachment) URL for the
        given image type.
    NOTE: The target image type (e.g. WALLPAPER) must be added to the end of this URL.
    :param rover_id: UUID object for unique rover identifier.
    :param target_id: UUID object for unique target identifier.
    '''
    return "%s/download_image" % (rover_target(rover_id, target_id))

def client_progress_create():
    '''
    Returns the URL that should be used to create a new progress key from the client.
    Only whitelisted progress keys are allowed to be created from the client, see progress.py
    '''
    return "/api/ops/progress"

def client_progress_reset(progress_key):
    '''
    Returns the URL that should be used to reset a progress key from the client, which removes it.
    Only whitelisted progress keys are allowed to be reset from the client, see progress.py
    '''
    return "/api/ops/progress/%s/reset" % progress_key

def message_content(message_id):
    '''
    Returns the URL that should be used to fetch this messages's content
    :param message_id: UUID object for unique message identifier.
    '''
    return "/api/ops/message/%s" % (message_id)

def message_unlock(message_id):
    '''
    Returns the URL that should be used in an ajax request to unlock this message.
    :param message_id: UUID object for unique message identifier.
    '''
    return "/api/ops/message/%s/unlock" % (message_id)

def message_forward(message_id):
    '''
    Returns the URL that should be used in an ajax request to forward this message.
    :param message_id: UUID object for unique message identifier.
    '''
    return "/api/ops/message/%s/forward" % (message_id)

def mission_mark_viewed(mission_id):
    '''
    Returns the URL that should be used to perform a mark_viewed request on a given mission.
    :param mission_id: The mission_id to mark viewed.
    '''
    return "/api/ops/mission/%s/mark_viewed" % (mission_id)

def species_mark_viewed(species_id):
    '''
    Returns the URL that should be used to perform a mark_viewed request on a given species.
    :param species_id: The species_id to mark viewed.
    '''
    return "/api/ops/species/%s/mark_viewed" % (species_id)

def achievement_mark_viewed(achievement_key):
    '''
    Returns the URL that should be used to perform a mark_viewed request on a given achievement.
    :param achievement_key: The achievement_key to mark viewed.
    '''
    return "/api/ops/achievement/%s/mark_viewed" % (achievement_key)

def invite_create():
    '''
    Returns the URL that should be used to create a new invitation from the client.
    '''
    return "/api/ops/invite"

def shop_stripe_purchase_products():
    '''
    Returns the URL that should be used to purchase products with Stripe.
    '''
    return "/api/ops/shop/stripe/purchase_products"

def shop_stripe_remove_saved_card():
    '''
    Returns the URL that should be used to remove the Stripe saved credit card.
    '''
    return "/api/ops/shop/stripe/remove_saved_card"

def api_user_login_ajax():
    '''
    Returns the URL that should be used in an ajax request to login the player.
    '''
    return "/api/login"

def api_user_signup_ajax():
    '''
    Returns the URL that should be used in an ajax request to login the player.
    '''
    return "/api/signup"

def api_check_session(app_version):
    '''
    Returns the URL that should be used via an HTTP request to see if the browser has a valid session.
    '''
    return "/api/check_session?version=" + app_version

def api_validate(token):
    '''
    Returns the URL that should be for validating a user account with an ajax request (native API).
    :param token: str, The token needed to validate this user.
    '''
    return tools_absolute_root() + "/api/backdoor/" + token

## Public API
def api_public_photo_highlights():
    return '/api/public/photo_highlights'

def api_public_photo_highlights_jsonp(callback_name):
    return add_query_param_to_url(api_public_photo_highlights(), callback=callback_name)

## Admin
def admin_root():
    return '/admin'

def admin_user(user_id):
    return '/admin/user/%s' % user_id

def admin_user_map(user_id):
    return '/admin/user/%s/map' % user_id

def admin_target(target_id):
    return '/admin/target/%s' % target_id

def admin_invoice(invoice_id):
    return '/admin/invoice/%s' % invoice_id

def admin_gifts_recent():
    return '/admin/gifts'

def admin_gifts_mine():
    return '/admin/gifts/mine'

def admin_gifts_new():
    return '/admin/gifts/new'

def admin_invites_recent():
    return '/admin/invites'

def admin_invites_system():
    return '/admin/invites/system'

def admin_invites_new():
    return '/admin/invites/new'

def admin_users():
    return '/admin/users'

def admin_users_by_campaign_name(campaign_name):
    return add_query_param_to_url(admin_users(), campaign_name=campaign_name)

def admin_search_users():
    return '/admin/search_users'

def admin_search_users_with_term(search_term):
    return add_query_param_to_url(admin_search_users(), search_term=search_term)

def admin_targets():
    return '/admin/targets'

def admin_transactions():
    return '/admin/transactions'

def admin_deferreds():
    return '/admin/deferreds'

def admin_email_queue():
    return '/admin/email_queue'

def admin_stats():
    return '/admin/stats'

def admin_stats_attrition():
    return '/admin/stats/attrition'

## Admin API
def admin_recent_users_and_targets_html():
    return '/admin/recent_users_and_targets_html'

def admin_api_chart_data():
    return '/admin/api/chart_data'

def admin_api_user_increment_invites_left():
    return '/admin/api/user_increment_invites_left'

def admin_api_user_edit_campaign_name():
    return '/admin/api/user_edit_campaign_name'

def admin_api_reprocess_target():
    return '/admin/api/reprocess_target'

def admin_api_highlight_add():
    return '/admin/api/highlight_add'

def admin_api_highlight_remove():
    return '/admin/api/highlight_remove'

def admin_species_id_img(image_url):
    '''
    If the image_url and inspector tool are on the same server, then view the image in
    the inspector.  Otherwise, browsers will tend to raise security concerns, so just
    return the link to the raw image.
    '''
    url_inspector = 'https://s3-us-west-2.amazonaws.com/images.extrasolar.com/inspector.html'
    parsed_inspector = urlparse.urlparse(url_inspector)
    parsed_img = urlparse.urlparse(image_url)
    if parsed_inspector.scheme == parsed_img.scheme and parsed_inspector.netloc == parsed_img.netloc:
        return url_inspector + '?img=' + image_url
    return image_url

## Admin Payments
def admin_stripe_charge_info(stripe_charge_id):
    return (STRIPE_CHARGE_URL + '/%s') % stripe_charge_id

## Web Services
def renderer_next_target():
    '''
    Returns the URL for the web service to fetch an unprocessed target.
    '''
    return "/service/renderer/next_target"

def renderer_processed_target():
    '''
    Returns the URL for the renderer to inform the web service that a target is processed.
    '''
    return "/service/renderer/target_processed"

## Utilities
def join(root, relative):
    """ Join two URL strings together correctly. The first is the absolute root, the second is a
        relative path. A new absolute URL will be returned. """
    return urlparse.urljoin(root, relative)

def add_query_param_to_url(url, **params):
    """
    Add the given keyword arguments as encoded query parameters to the given URL string.

    >>> add_query_param_to_url("http://example.com/", p='')
    'http://example.com/?p='
    >>> add_query_param_to_url("http://example.com/?blank", p='')
    'http://example.com/?p=&blank='
    >>> add_query_param_to_url("http://example.com/", p="test")
    'http://example.com/?p=test'
    >>> add_query_param_to_url("http://example.com/?q=value", p="test")
    'http://example.com/?q=value&p=test'
    >>> add_query_param_to_url("http://example.com/?p=old", p="new")
    'http://example.com/?p=new'
    >>> add_query_param_to_url("http://example.com/", p="encode& this")
    'http://example.com/?p=encode%26+this'
    >>> add_query_param_to_url("http://example.com/", p=u"S\xc3\xa9bas")
    'http://example.com/?p=S%C3%83%C2%A9bas'
    """
    url_parts = list(urlparse.urlparse(url))
    query = dict(urlparse.parse_qsl(url_parts[4], keep_blank_values=True))
    query.update(params)
    # Be sure any query parameter values which are unicode objects are encoded as UTF-8 str/bytes
    # which is all urllib.urlencode can handle if the unicode object contains non-ASCII.
    for k, v in query.iteritems():
        if isinstance(v, unicode):
            query[k] = v.encode('utf8')
    url_parts[4] = urllib.urlencode(query)
    return urlparse.urlunparse(url_parts)

def is_mobile(request):
    # Return true if the the request includes the query param ?force_mobile=1
    parsed = urlparse.parse_qs(urlparse.urlparse(request.path_qs).query)
    if 'force_mobile' in parsed and parsed['force_mobile'][0] == '1':
        return True
    return parse(request.headers.get('User-Agent', 'Unknown')).is_mobile
