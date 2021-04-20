# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os, shutil, re
from datetime import timedelta
import unittest, webtest
import logging
import facebook

from front import read_config, debug, InitialMessages, Constants
from front.lib import db, xjson, utils, urls, gametime, email_module, email_ses
from front.data import validate_struct, schemas, scene
from front.models import maptile, message
from front.models import user as user_module
from front.models import progress as progress_module
from front.models import capability as capability_module
from front.backend import deferred

# Used by shop_stripe_purchase_products method.
from front.tests import mock_stripe
from front.backend.shop import stripe_gateway
from front.tests.mock_stripe import ChargeAlwaysSuccess, FAKE_CHARGE_ID_1
from front.tests.mock_stripe import FAKE_CARD_NUMBER, FAKE_CARD_EXP_MONTH, FAKE_CARD_EXP_YEAR, FAKE_CARD_NAME

# Used by the replay_game method.
from front.tools import replay_game as replay_game_tool
from front.debug.stories import fastest_game_story

# basedir is "../.."
BASEDIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# Useful constants
SIX_HOURS = utils.in_seconds(hours=6)

# A url that is really only meant for testing which requires authentication.
PROTECTED_URL='/protected'

# Provide the test image rectanges from this class, as imported from debug.
from front.debug import rects
rects = rects

# Test target locations, used as input for base.create_target
class points(object):
    _route_point_date = []
    # For now, derive the FIRST_MOVE, SECOND_MOVE etc. data from the fastest_story_rover1 route data.
    # Eventually we might need another route to satisfy these unit test requirements.
    from front.debug.route import Point
    for p_struct in debug.routes.struct(debug.routes.FASTEST_STORY_ROVER1):
        # Load the data through the Point object to decouple us from knowledge of the .json format.
        p = Point.from_struct(p_struct)
        _route_point_date.append({'lat':p.lat, 'lng':p.lng, 'yaw':p.yaw})

    # These are a sequence of moves which are legal when created in the listed order starting
    # from a brand new user state. These are expected to hold lat, lng and yaw values a dict.
    FIRST_MOVE           = _route_point_date[0]
    SECOND_MOVE          = _route_point_date[1]
    THIRD_MOVE           = _route_point_date[2]
    FOURTH_MOVE          = _route_point_date[3]
    FIFTH_MOVE           = _route_point_date[4]
    SIXTH_MOVE           = _route_point_date[5]
    SEVENTH_MOVE         = _route_point_date[6]

    # It is expected this move would exceed constraints on the maximum distance for the first move.
    MOVE_TOO_FAR         = {"lat":6.241265656544851, "lng":-109.4136196374893,"yaw":0.1}
    # It is expected this move would go outside of the island/water boundary region for the second move.
    MOVE_OUTSIDE_ISLAND  = {"lat":6.241060350530318, "lng":-109.41425532102585,"yaw":0.1}
    # It is expected this move would go inside of the lander padding region on the first move, violating the region.
    MOVE_INSIDE_LANDER   = {"lat":6.240617742485049, "lng":-109.41446989774704,"yaw":0.1}
    # It is expected this move not be close enough to the lander to satisfy the TUT01a first move requirement.
    MOVE_TOO_SHORT       = {"lat":6.240396549986026,"lng":-109.41427410164516,"yaw":0.1}

    @classmethod
    def by_index(cls, index):
        return cls._route_point_date[index]

# Test user tiles
TEST_TILES = [{'zoom':17, 'x':123, 'y':456}, {'zoom':17, 'x':121, 'y':456}]
TILE_KEY = maptile.make_tile_key(TEST_TILES[1]['zoom'], TEST_TILES[1]['x'], TEST_TILES[1]['y'],)

# List the S1 and ALL passes and vouchers.
PRODUCT_KEY_S1 = 'SKU_S1_PASS'
VOUCHER_KEY_S1 = 'VCH_S1_PASS'
PRODUCT_KEY_ALL = 'SKU_ALL_PASS'
VOUCHER_KEY_ALL = 'VCH_ALL_PASS'
PRODUCT_KEY_S1_GIFT = 'SKU_S1_PASS_GIFT'
VOUCHER_KEY_S1_GIFT = 'VCH_S1_PASS'
PRODUCT_KEY_ALL_GIFT = 'SKU_ALL_PASS_GIFT'
VOUCHER_KEY_ALL_GIFT = 'VCH_ALL_PASS'

# Constants used when testing invites, especially to capture any truncation that is performed during signup.
INVITE_EMAIL      = "testrecipient@example.com"
INVITE_FIRST_NAME = "Recipientfirst"
# Modify the last name so that the length is longer than MAX_LEN_FIRST to verify it is truncated.
INVITE_LAST_NAME  = "Recipientlast".ljust(Constants.MAX_LEN_LAST + 10, 'F')
INVITE_LAST_NAME_TRUNCATED = INVITE_LAST_NAME[:Constants.MAX_LEN_LAST]

# This species key refers to a species which has delayed data (hidden from the gamestate on first discovery).
DELAYED_SPECIES_KEY = "SPC_PLANT006"

class TestCase(unittest.TestCase):
    # Optionally override what Paste app/configuration is being used.
    # e.g. #compiled_javascript
    PASTE_CONFIG = ''

    def setUp(self):
        self.app = webtest.TestApp('config:test.ini' + self.PASTE_CONFIG,
                                   relative_to=BASEDIR)
        # Used as ctx so create a new one per test.
        self.conf = read_config('test')
        # Track all ctx's created by the load user helpers.
        self._tracked_contexts = []
        # If a user is signup up or logged in during this test, this will story the UUID of the
        # last logged on user. This is cleared if the user logs off.
        self._logged_in_user_id = None
        # Store the renderer auth token.
        self.auth_token = self.conf['renderer_auth_token']
        # From our configuration file, copy data needed to access our Facebook app and find a test user.
        self.fb_application_id = self.conf['template.fb_application_id']
        self.fb_application_secret = self.conf['fb.application_secret']
        self.fb_test_user_id = self.conf['fb.test_user_id']
        # Freeze time to now.
        gametime.set_now(gametime.now())

        # Initialize the last_seen_chip_time for fetch_chips emulation.
        self._last_seen_chip_time = utils.usec_js_from_dt(gametime.now())

        # A list of (email_to, email_from, subject, bodyHtml) tuples for any sent email
        # messages in a test.
        self._sent_messages = []

        # A boolean we can set to True to force our mock email_ses delivery function to fail to send an email.
        self._fail_email_delivery = False

        # A counter to emulate a client generating CIDs for new models.
        self._cid_counter = -1

        # Inform the email delivery system that the unit test object will act as the capturing dispatcher
        # for all emails sent during the tests.
        email_module.set_capture_dispatcher(self)
        # And do the same for the email_ses module.
        email_ses._suppress_email_delivery(self._mock_deliver_email_to_ses)

        # Track testing only callback classes which were added to callback modules.
        # Tuples of (callback_module, callback_class)
        self._injected_test_callbacks = []

        # Track testing on msg_types which were added with send_mock_message_now.
        self._injected_test_msg_types = []

        # Track capabilities which were switched to being unlimited for this single test.
        self._injected_test_capabilities = {}

        # Track the active ExpectedLogFilter. At the end of the test, this list should be empty
        # otherwise it means an expected log message was not seen.
        self._expected_logs = []
        # Track any unexpected logs for this test with a single UnexpectedLogFilter instance.
        self._unexpected_log = UnexpectedLogFilter()
        logging.getLogger().handlers[0].addFilter(self._unexpected_log)

    def tearDown(self):
        # Shutdown all the open ctxes
        for ctx in self._tracked_contexts:
            db.commit(ctx)
            db.close_all_connections(ctx)

        # Clear the database tables after every test instead of dropping the entire database.
        db.clear_database(self.conf)
        for key in ('cache_dir',):
            d = self.conf[key]
            shutil.rmtree(d, ignore_errors=True)
        # Unfreeze time
        gametime.unset_now()

        # Verify all the ExpectedLogFilter filters saw their expected pattern.
        if len(self._expected_logs) > 0:
            self.fail("Expected log filters did not fire: %s" % self._expected_logs)

        # Verify no unexpected logs were seen by the UnexpectedLogFilter.
        if len(self._unexpected_log) > 0:
            self.fail("Unexpected log messages:\n%s" % self._unexpected_log)

        # Remove the UnexpectedLogFilter from the filter chain.
        logging.getLogger().handlers[0].removeFilter(self._unexpected_log)

        # Remove any injected testing only callbacks.
        for callback_module, class_name in self._injected_test_callbacks:
            del callback_module.__dict__[class_name]

        # Remove any injected testing only msg_types.
        for msg_type in self._injected_test_msg_types:
            del message._get_all_message_types()[msg_type]

        # Restore any injectect testing capability data to the original values.
        for cap_key, values in self._injected_test_capabilities.iteritems():
            capability_def = capability_module.get_capability_definition(cap_key)
            capability_def.update(values)

    ## Client emulating helpers. These methods for the most part perform actions that
    #   are either implemented in Javascript or perform requests of the backend in the same
    #   manner as the real client.

    # The default move is a safe initial move that places the rover far enough from the lander so as
    # to not trigger a mission done event.
    def create_target(self, create_target_url=None,
                      lat=points.FIRST_MOVE['lat'],
                      lng=points.FIRST_MOVE['lng'],
                      yaw=points.FIRST_MOVE['yaw'],
                      pitch=0.0, arrival_delta=SIX_HOURS, metadata=None, status=None):
        """
        Create a new target.
        :param arrival_delta: int, time in future in seconds.
        """
        if create_target_url is None:
            # Avoid loading the entire gamestate in this situation just to determine the active rover and get the 
            # create_target_url and instead pull it off of the user object itself as this should significantly
            # speed up this commonly called method to create a target.
            rovers = self.get_logged_in_user().rovers.active()
            self.assertEqual(len(rovers), 1)
            create_target_url = rovers[0].url_target_create
        if metadata is None:
            metadata = {}
        payload = {'cid':self.get_next_cid(), 'lat':lat, 'lng':lng, 'yaw':yaw, 'pitch':pitch,
                   'arrival_delta':arrival_delta, 'metadata':metadata}
        return self.json_post(create_target_url, payload, status=status)

    def create_target_and_move(self, create_target_url=None,
                               lat=points.FIRST_MOVE['lat'],
                               lng=points.FIRST_MOVE['lng'],
                               yaw=points.FIRST_MOVE['yaw'],
                               arrival_delta=SIX_HOURS, metadata=None):
        """
        Create a new target with standard location, advance time 6 hours, and render the target image.
        """
        chips_result = self.create_target(create_target_url, lat=lat, lng=lng, yaw=yaw, arrival_delta=arrival_delta, metadata=metadata)
        # Render the target.
        self.render_next_target(assert_only_one=True)
        # Advance the game to the target's arrival time, running any deferred actions along the way.
        self.advance_game(seconds=arrival_delta)
        return chips_result

    def check_species(self, check_species_url, check_rects, status=None):
        """
        Perform a check_species on the supplied rects list.
        :params check_rects: list, of the form [{xmin=0.5, ymin=0.5, xmax=0.6, ymax=0.6}, ...]
        """
        payload = {'rects': check_rects}
        return self.json_post(check_species_url, payload, status=status)

    def create_client_progress_key(self, create_progress_url, key, value=None, status=None):
        """
        Set the given client progress key (and optional value).
        :params create_progress_url: The URL from the gamestate used to create a client progress key.
        """
        if value is None:
            value = {}
        payload = {'key': key, 'value': value}
        return self.json_post(create_progress_url, payload, status=status)

    def shop_stripe_purchase_products(self, product_keys, product_specifics_list=[], save_card=None, gamestate=None, status=None, charge=None):
        """
        Purchase the supplied product_keys using the stripe_purchase_product resource. The state of
            user.shop.stripe_has_saved_card will be used to determine whether a Stripe token is required to perform
            the purchase, just as it is used on the actual client.
        :params product_keys: list, of the form ['SKU_PRODUCT1', ...]
        :params product_specifics_list: list, of the form [{'key':'value'}, {}, ...]
        :params save_card: bool, whether to save the credit card details.
        :params gamestate: dict, optionally pass in an already loaded gamestate for slightly faster test.
        :params charge: StripeCharge, optionally pass through a StripeCharge instance (see the Mock* versions in
            mock_stripe module) which will bypass calling the real Stripe API and instead perform all purchasing
            steps locally using the supplied Charge object.
        NOTE: If charge is not supplied, this method WILL call the Stripe API.
        """
        # If an optional testing/mock StripeCharge instance was provided, then use that object when
        # creating the charge object on the backend and replace the real StripeGateway with a mock object
        # which does not trigger the live Stripe API.
        if charge is not None:
            mock_stripe.mock_gateway_with_charge(charge)

        try:
            if gamestate is None:
                gamestate = self.get_gamestate()

            payload = {'product_keys': product_keys, 'product_specifics_list': product_specifics_list}
            # If the shop does not have a saved Stripe card, generate a one time Stripe token.
            if gamestate['user']['shop']['stripe_has_saved_card'] == 0:
                token = stripe_gateway._create_fake_stripe_token(
                    card_number=FAKE_CARD_NUMBER,
                    exp_month=FAKE_CARD_EXP_MONTH,
                    exp_year=FAKE_CARD_EXP_YEAR,
                    name=FAKE_CARD_NAME)
                payload['stripe_token_id'] = token.id

                # Also, determine if the card should be saved for future purchases or not.
                assert save_card is not None
                payload['stripe_save_card'] = save_card

            purchase_products_url = str(gamestate['user']['shop']['urls']['stripe_purchase_products'])
            response = self.json_post(purchase_products_url, payload, status=status)

        finally:
            # If the charge creation code was overriden, restore the original functionality.
            if charge is not None:
                mock_stripe.unmock_gateway()

        return response

    def purchase_gift(self, gift_product_key, recipient_email=INVITE_EMAIL,
                       recipient_first_name=INVITE_FIRST_NAME, recipient_last_name=INVITE_LAST_NAME,
                       recipient_message="Hello my friend.", status=None):
        """ A convenience method to purchase a given gift product and send it via an invitation. """
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        product_specifics = self.gift_product_specifics(gift_product_key, recipient_email=recipient_email,
                            recipient_first_name=recipient_first_name, recipient_last_name=recipient_last_name,
                            recipient_message=recipient_message)
        response = self.shop_stripe_purchase_products(product_keys=[gift_product_key],
                                              product_specifics_list=[product_specifics],
                                              save_card=False, charge=charge, status=status)
        return response

    def gift_product_specifics(self, gift_product_key, recipient_email=INVITE_EMAIL,
                              recipient_first_name=INVITE_FIRST_NAME, recipient_last_name=INVITE_LAST_NAME,
                              recipient_message="Hello my friend."):
        """ A convenience method to create a product_specifics to purchase the given gift product. """
        product_specifics = {'send_invite': True}
        if recipient_email is not None:      product_specifics['recipient_email'] = recipient_email
        if recipient_first_name is not None: product_specifics['recipient_first_name'] = recipient_first_name
        if recipient_last_name is not None:  product_specifics['recipient_last_name'] = recipient_last_name
        if recipient_message is not None:    product_specifics['recipient_message'] = recipient_message
        return product_specifics

    def signup_user(self, email, password, first_name='TestFirst', last_name='TestLast', redirect_to='/', campaign_name=None):
        """
        Attempt to signup a new user using the provided fields (email, password, first_name, last_name).
        :param redirect_to: An optional URL to emulate the redirect following signup.
        :param campaign_name: The optional campaign_name (marketing) user metadata key.
        """
        req_url = urls.auth_signup()
        if redirect_to is not None:
            req_url = urls.add_original_url_param(req_url, redirect_to)
        if campaign_name is not None:
            req_url = urls.add_campaign_name_url_param(req_url, campaign_name)
        response = self.app.get(req_url)
        # Fill and submit the signup form.
        form = response.forms['form_signup']
        form['signup_email']      = email
        form['signup_password']   = password
        form['first_name'] = first_name
        form['last_name']  = last_name
        response2 = form.submit()
        # Now that the user is logged in, store their UUID
        self._logged_in_user_id = user_module.user_id_from_request(response2.request)

        # If no redirect was requested, then return the response.
        if redirect_to is None:
            return response2
        # Otherwise follow the redirect and return that response object.
        self.assertEqual(response2.headers.get('location'), redirect_to, response2)
        return response2.follow()

    def login_user(self, email, password, redirect_to='/', req_url=urls.auth_login(), status=303):
        if redirect_to is not None:
            req_url += "?o=" + redirect_to
        form = self.app.get(req_url).forms['form_login']
        form['login_email']    = email
        form['login_password'] = password
        response2 = form.submit(status=status)
        # Now that the user is logged in, store their UUID
        self._logged_in_user_id = user_module.user_id_from_request(response2.request)

        if redirect_to is None:
            return response2
        self.assertEqual(response2.headers.get('location'), redirect_to)
        return response2.follow()

    def get_facebook_token(self):
        """
        Get a valid Facebook access token from our list of test users. You can then login as follows:
        self.login_user_facebook(access_token=facebook_token)
        """
        # Using our Facebook app ID and secret key, get our list of test users.
        app_token = facebook.get_app_access_token(self.fb_application_id, self.fb_application_secret)
        graph = facebook.GraphAPI(app_token)
        test_users = graph.get_object('/%s/accounts/test-users' % (self.fb_application_id))

        # We're looking for a particular test user with a known ID.
        user_tokens = [user['access_token'] for user in test_users['data'] if user['id']==self.fb_test_user_id]
        self.assertEqual(len(user_tokens), 1) 
        return str(user_tokens[0])

    def login_user_facebook(self, access_token, redirect_to='/', req_url=urls.auth_login(), status=303):
        if redirect_to is not None:
            req_url += "?o=" + redirect_to
        form = self.app.get(req_url).forms['form_facebook']
        form['facebook_token'] = access_token
        response2 = form.submit(status=status)
        # Now that the user is logged in, store their UUID
        self._logged_in_user_id = user_module.user_id_from_request(response2.request)

        if redirect_to is None:
            return response2
        self.assertEqual(response2.headers.get('location'), redirect_to)
        return response2.follow()

    def logout_user(self):
        self.app.reset()
        self._logged_in_user_id = None

    ## Gamestate helper methods.
    def get_gamestate(self, skip_validation=True, status=None):
        """ Return the current, full gamestate JSON object as a dict. """
        # Don't use json_get as this request should not send last_seen_chip_time.
        gamestate = xjson.loads(self.app.get(urls.gamestate(), headers=[xjson.accept], status=status).body)
        # If a non-standard status is supplied, return the gamestate unvalidated (as the response
        # might contain just error information).
        if status is not None:
            return gamestate
        # Validate the gamestate object if requested.
        if not skip_validation:
            validate_struct(gamestate, schemas.GAMESTATE)
        return gamestate

    def get_active_rover(self, gamestate):
        rovers = [r for r in gamestate['user']['rovers'].values() if r['active'] == 1]
        assert len(rovers) <= 1
        if len(rovers) == 1:
            return rovers[0]
        return None

    # Since targets do not have their rover_id in the gamestate, need a helper.
    def get_rover_for_target_id(self, target_id, gamestate=None):
        if gamestate is None:
            gamestate = self.get_gamestate()
        for rover in gamestate['user']['rovers'].itervalues():
            if target_id in rover['targets']:
                return rover
        return None

    def get_target_from_gamestate(self, target_id, gamestate=None):
        if gamestate is None:
            gamestate = self.get_gamestate()
        rover = self.get_rover_for_target_id(target_id, gamestate)
        if rover is None:
            return None
        else:
            return rover['targets'][target_id]

    def get_most_recent_target_from_gamestate(self, gamestate=None):
        if gamestate is None:
            gamestate = self.get_gamestate()
        return self.get_targets_from_gamestate(gamestate)[-1]

    def get_most_recent_processed_target_from_gamestate(self, gamestate=None):
        # Note: The processed flag is always scrubbed from the gamestate (set to 0) prior
        # to arrival_time, so this is equivalent to getting the last arrived-at target.
        if gamestate is None:
            gamestate = self.get_gamestate()
        sorted_targets = self.get_targets_from_gamestate(gamestate)
        # Iterate over the sorted targets in reverse, looking for the last processed one.
        for i in range(1, len(sorted_targets)):
            if sorted_targets[-i]['processed'] == 1:
                return sorted_targets[-i]
        return None

    def get_targets_from_gamestate(self, gamestate=None):
        if gamestate is None:
            gamestate = self.get_gamestate()
        # Merge the targets from all rovers into a single list and sort by arrival_time.
        all_targets = {}
        for r in gamestate['user']['rovers'].values():
            all_targets = dict(list(all_targets.items()) + list(r['targets'].items()))
        return sorted(all_targets.values(), key=lambda m: m['arrival_time'])

    def get_mission_from_gamestate(self, mission_definition, gamestate=None):
        """ Returns None if there is no mission for this mission_definition. """
        if gamestate is None:
            gamestate = self.get_gamestate()
        # Since there can technically be more than one mission per mission_definition assert that there
        # is only 1 when using this method.
        missions = [m for m in gamestate['user']['missions'].values() if mission_definition == m['mission_definition']]
        assert(len(missions) <= 1)
        if len(missions) == 0:
            return None
        else:
            return missions[0]

    def fetch_chips(self, seconds_ago=None, status=None):
        """
        Returns the results of the fetch chips calls, which should be a dict with a 'chips' key, and
        possibly chips data within that key. This method is the most similar to the real client version
        in that it stores the last_seen_chip_time and updates it to the most recent chip.time value
        after every call.
        :param seconds_ago: int Grab this number of seconds ago worth of chips, setting the stored value
        of last_seen_chip_time to be this value.
        """
        if seconds_ago is not None:
            self._last_seen_chip_time = utils.usec_js_from_dt(gametime.now() - timedelta(seconds=seconds_ago))

        response = self.json_get(urls.fetch_chips(), status=status, _last_seen_chip_time=self._last_seen_chip_time)
        if 'chips' in response and len(response['chips']) > 0:
            self._last_seen_chip_time = response['chips'][-1]['time']
        return response

    def recent_chips_struct(self, seconds_ago=1):
        """
        Returns the result of the fetch chips call, which should be a dict with a 'chips' key, and
        possibly chips data within that key.
        :param seconds_ago: int Grab this number of seconds ago worth of chips.
        """
        last_seen_chip_time = utils.usec_js_from_dt(gametime.now() - timedelta(seconds=seconds_ago))
        return self.json_get(urls.fetch_chips(), _last_seen_chip_time=last_seen_chip_time)

    def chips_for_path(self, path, struct=None, seconds_ago=1):
        """
        Returns the chip structs of all chips in the given response matching the
         supplied chip path. Returns empty list if there was no match or no chips.
         The chips will be sorted most recent chip last.
        :param path: list The chips path to look for. This is in the format ['root', 'element'] etc. May
         contain an "*" which will act as a wildcard for that chip path component.
         :param struct: dict The deserialized JSON response. Expected to have a "chips" element. If not
         provided, a fetch_chips request will be performed for the last seconds_ago worth of chips.
         :param seconds_ago: int Grab this number of seconds ago worth of chips.
        """
        if struct == None:
            struct = self.recent_chips_struct(seconds_ago=seconds_ago)

        # If there were no chips returned, return None.
        if 'chips' not in struct:
            return []

        # Search the chips list in reverse as last element is most recent.
        found = []
        for chip in struct['chips']:
            for i, part in enumerate(chip['path']):
                # If the search patch element is not a wildcard and not a match, move to
                # the next chip.
                if path[i] != "*" and path[i] != part:
                    break

                # If the search path is exhausted.
                if len(path) == i + 1:
                    # If all elements matched, return the match.
                    if len(path) == len(chip['path']):
                        found.append(chip)
                    # And move onto the next chip.
                    break

                # Otherwise, check the next element in the search path.
        return found

    def chip_values_for_path(self, path, struct=None, seconds_ago=1):
        """
        Same as chips_for_path but returns the 'value' component of matching chips.
        """
        chips = self.chips_for_path(path, struct=struct, seconds_ago=seconds_ago)
        values = []
        for c in chips:
            values.append(c['value'])
        return values

    def last_chip_for_path(self, path, struct=None, seconds_ago=1):
        """
        Returns the chip struct of the last/most recent chip in the given response matching the
         supplied chip path. Returns None if there was no match or no chips.
        :param path: list The chips path to look for. This is in the format ['root', 'element'] etc. May
         contain an "*" which will act as a wildcard for that chip path component.
         :param struct: dict The deserialized JSON response. Expected to have a "chips" element. If not
         provided, a fetch_chips request will be performed for the last seconds_ago worth of chips.
         :param seconds_ago: int Grab this number of seconds ago worth of chips.
        """
        found_chips = self.chips_for_path(path, struct=struct, seconds_ago=seconds_ago)

        # If not chips were found, return None.
        if len(found_chips) == 0:
            return None
        # Return the last chip as it is most recent.
        else:
            return found_chips[-1]

    def last_chip_value_for_path(self, path, struct=None, seconds_ago=1):
        """
        Same as last_chip_for_path but returns the 'value' component of the last/most recent chip that
        matches the path.
        """
        chip = self.last_chip_for_path(path, struct=struct, seconds_ago=seconds_ago)
        if chip == None:
            return None
        else:
            return chip['value']

    ## JSON request helper methods.
    def json_get(self, get_url, status=None, _last_seen_chip_time=None):
        """
        Mirrors the client side json_get function, which always sends the last_seen_chip_time
        with every request. Returns the deserialized JSON dict response body.
        :param status: Optionally pass an int for the expected non-200 HTTP status result.
        """
        response = xjson.loads(self.app.get(get_url,
                                            params=self._last_seen_chip_param(_last_seen_chip_time),
                                            headers=[xjson.accept], status=status).body)
        return response

    def json_post(self, post_url, payload=None, status=None, _last_seen_chip_time=None):
        """
        Mirrors the client side json_post function, which always sends the last_seen_chip_time
        with every request. Returns the deserialized JSON dict response body.
        :param payload: Optionally provide a payload dict with parameters for the request.
        :param status: Optionally pass an int for the expected non-200 HTTP status result.
        """
        if payload is None:
            payload = {}
        # Add in the last_seen_chip_time parameter to the JSON payload.
        payload.update({'chips': self._last_seen_chip_param(_last_seen_chip_time)})

        response = xjson.loads(self.app.post(post_url,
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload), status=status).body)
        return response

    ## Admin API client emulation methods.
    def admin_api_highlight_add(self, target_id, status=200):
        payload = {'target_id': target_id}
        response = xjson.loads(self.app.post(urls.admin_api_highlight_add(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload), status=status).body)
        return response

    def admin_api_highlight_remove(self, target_id, status=200):
        payload = {'target_id': target_id}
        response = xjson.loads(self.app.post(urls.admin_api_highlight_remove(),
                                             content_type=xjson.mime_type,
                                             params=xjson.dumps(payload), status=status).body)
        return response

    ## Renderer service client emulation methods.
    def renderer_service_next_target(self, auth_token=None):
        """ Perform the renderer service 'next_target' request. """
        if auth_token is None:
            auth_token = self.auth_token
        payload = {'auth':auth_token}
        result = xjson.loads(self.app.post(urls.renderer_next_target(),
                                           content_type=xjson.mime_type,
                                           params=xjson.dumps(payload)).body)
        return result

    def renderer_service_processed_target(self, user_id, rover_id, target_id, arrival_time,
                                          render_scene=scene.TESTING, tiles=TEST_TILES, metadata=None, classified=0):
        """ Perform the renderer service 'processed_target' request. """
        if metadata is None:
            metadata = {}
        payload = {'auth':self.auth_token, 'user_id':user_id, 'rover_id':rover_id, 'target_id':target_id,
                   'arrival_time':arrival_time, 'classified':classified, 'metadata':metadata,
                   'images':render_scene.to_struct(), 'tiles':tiles}
        result = xjson.loads(self.app.post(urls.renderer_processed_target(),
                                           content_type=xjson.mime_type,
                                           params=xjson.dumps(payload)).body)
        return result

    def renderer_decompose_next_target(self, result):
        user_id = result['user_id']
        rover_id = result['rovers'][-1]['rover_id']
        target = result['rovers'][-1]['targets'][-1]
        self.assertEqual(target['picture'], 1)
        self.assertEqual(target['processed'], 0)
        return user_id, rover_id, target['target_id'], target['arrival_time'], target['metadata']

    def render_next_target(self, assert_only_one=False, render_scene=scene.TESTING, classified=0):
        """ Render one target using the renderer webservice and return the JSON results from
            next_target. In addition, an assertion is made that only one photo is pending processing."""
        first_result = self.renderer_service_next_target()
        self.assertEqual(first_result['status'], 'ok')
        # If there were no targets rendered, return the empty status.
        if first_result == {'status': 'ok'}:
            return first_result
        (user_id, rover_id, target_id, arrival_time, metadata) = self.renderer_decompose_next_target(first_result)
        processed_result = self.renderer_service_processed_target(user_id, rover_id, target_id, arrival_time,
                                                                  render_scene=render_scene, classified=classified,
                                                                  metadata=metadata)
        self.assertEqual(processed_result['status'], 'ok')

        # If requested, assert that no more targets need to be rendered. This assures the caller that the one
        # target they expected to be rendered was.
        if assert_only_one:
            second_result = self.renderer_service_next_target()
            self.assertEqual(second_result, {'status': 'ok'})
        return first_result

    ## Testing utility helpers. These methods are useful to the testing environment either
    #  to allow for unit testing of library code without emulating a client or to adjust
    #  the testing environments concept of time.
    def create_user(self, email, password, first_name='TestFirst', last_name='TestLast'):
        """ Create a validated user who has completed the simulator, e.g. a new user ready to make
            their first 'real' move/create their first target.
            NOTE: Any messages/emails sent during validation or simulation completion are sent, even if deferred. """
        self.signup_user(email, password, first_name, last_name)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                self._validate_user_and_flush_email(user)

                # Complete the simulator mission, leaving the player at the moment they can make their first real move.
                for key in Constants.SIMULATOR_PROGRESS_KEYS:
                    progress_module.create_new_client_progress(ctx, user, key)

                # And flush out all the welcome emails and messages.
                processed = self.advance_game_for_user(user, minutes=InitialMessages.ALL_DELAY_MINUTES)
                assert len(processed) == 4
                assert processed[0].subtype == 'MSG_ROVER_INTRO01'
                assert processed[1].subtype == 'EMAIL_WELCOME'
                assert processed[2].subtype == 'MSG_JANE_INTRO'
                assert processed[3].subtype == 'MSG_KTHANKS'
                # Advance time a few seconds to move past any chips (MSG/MIS) sent from flushing the messages.
                self.advance_now(seconds=5)

                # Clear the various signup emails.
                self.clear_sent_emails()

    def create_validated_user(self, email, password, first_name='TestFirst', last_name='TestLast'):
        """ Create a validated user who has NOT completed the simulator.
            NOTE: Any messages/emails sent during validation are sent, even if deferred. """
        self.signup_user(email, password, first_name, last_name)
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                self._validate_user_and_flush_email(user)

                # And flush out the welcome email sent from validation.
                processed = self.advance_game_for_user(user, minutes=InitialMessages.EMAIL_WELCOME_DELAY_MINUTES)
                assert len(processed) == 1
                assert processed[0].subtype == 'EMAIL_WELCOME'

                # Clear the various signup emails.
                self.clear_sent_emails()

    def _validate_user_and_flush_email(self, user):
            # Flush the verify email from the deferred email queue.
            processed = self.advance_game_for_user(user, minutes=InitialMessages.EMAIL_VERIFY_DELAY_MINUTES)
            assert len(processed) == 1
            assert processed[0].subtype == 'EMAIL_VERIFY'
            # And validate the user directly.
            user.validate_with_token(user.validation_token)

    def advance_now(self, **kwargs):
        """ Advance the clock using the same parameters you would pass to timedelta
        e.g., seconds=x, minutes=y, hours=z"""
        debug.advance_now(**kwargs)

    def rewind_now(self, **kwargs):
        """ Rewind the clock using the same parameters you would pass to timedelta
        e.g., seconds=x, minutes=y, hours=z
        NOTE: USE WITH CAUTION."""
        debug.rewind_now(**kwargs)

    def advance_game(self, **kwargs):
        """ Advance the state of the game for the logged in user, incrementing time by the supplied
            amount. kwargs are the same as timedelta (minutes, seconds, hours etc.). """
        # Load a new ctx in a new transaction and run the deferreds.
        # This emulates what happens when the cron job runs in production.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            user = self.get_logged_in_user(ctx=ctx)
            return self.advance_game_for_user(user, **kwargs)

    def advance_game_for_user(self, user, **kwargs):
        """ Advance the state of the game for the given user instance, incrementing time by the supplied
            amount. kwargs are the same as timedelta (minutes, seconds, hours etc.).
            Use this method if you already have a User instance and want it to be updated by any
            code that runs when advancing the game, e.g. deferred actions.
            WARNING: Using this method in a test can cause a deadlock if subsequent parts of the test
            call the deferred system, since this method processes deferreds which locks that table.
            It is only really safe to call this method in a test where there is a commit_or_rollback
            being used directly, usually in lower level, model type tests. If the test issues requests
            on the test.app object (which opens up its own database connection and might also
            send deferreds), calling this method is very likely to cause a deadlock.
            Use advance_game instead in those situations."""
        # run_deferred_since_and_advance_now will set gametime.now to 'until'.
        until = gametime.now() + timedelta(**kwargs)
        processed = debug.run_deferred_and_advance_now_until(user.ctx, user, until=until)
        return processed

    def advance_game_and_activate_chips(self, seconds):
        """ Advance the state of the game for the logged in user by the given number of seconds.
            This is different from the advance_game/advance_game_for_user calls in that
            gametime.now() is restored at the end of this call and chips and deferred actions
            are 'rewound' or 'activated' to a second into the future.
            NOTE: Use the other advance_game calls whenever possible in 'pure' testing code.
            Only use this method if there is another process connecting to the unit test
            process space whose clock cannot be moved forward with gametime, for example when
            running the Javascript functional tests. """
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                return debug.advance_game_for_user_by_seconds(ctx, user, seconds)

    def run_deferred_actions(self, ctx=None, since=None):
        """ Run any deferred actions for the currently in the database. This does not fiddle with gametime.now
            like the advance_game* methods do, more closely emulating the real tool. """
        if ctx is None: ctx = self.get_ctx(needs_close=True)
        if since is None: since = gametime.now()
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                deferred.run_deferred_since(ctx, since)

    def replay_game(self, email, password, story=fastest_game_story, to_point=None):
        """
        Use the replay_game tool to create a new user with the given email and password and
        replay the provided story up until the optional to_point name.
        story defaults to fastest_game_story.
        See the documentation for the replay_game tool for more details.
        """
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                tool = replay_game_tool.ReplayGame(ctx, email, password=password,
                                                   route_structs=story.routes(),
                                                   beats=story.beats(), verbose=False,
                                                   fallback_beat=replay_game_tool.ReplayGameFallbackBeat)
                tool.run(to_point=to_point, no_prompt=True)

    def get_ctx(self, needs_close=False):
        """ Return an object compatible with the db modules 'ctx' object.
            Each call to this method returns a new 'ctx' object, with no opened database
            connections.
            NOTE: It is the callers responsibility to commit/rollback/close this ctx object
            so a commit_or_rollback is a good idea. However, if should_close if set to True
            then the test will commit and close the newly created ctx in the tests tearDown"""
        ctx = dict(self.conf)
        if needs_close:
            self._tracked_contexts.append(ctx)
        return ctx

    def get_user_by_email(self, email, ctx=None):
        """
        Return the User object for the given email address.
        Optionally supply the ctx to load the User object from if a consistent view
        of the database is required. E.g. if a transaction commit will be required
        for changes made to the returned User object.
        The User caches the ctx object for lazy loading which means it lives beyond the
        lifetime of this function if supplied as a parameter.
        """
        if ctx is None: ctx = self.get_ctx(needs_close=True)
        return debug.get_user_by_email(ctx, email)

    def get_logged_in_user(self, ctx=None):
        """ Returns a new User instance if there is a currently logged in user.
            Raises an Exception if there is no currently logged in user. """
        if self._logged_in_user_id is None:
            raise Exception("logged_in_user called when no user is logged in.")
        if ctx is None: ctx = self.get_ctx(needs_close=True)
        return user_module.user_from_context(ctx, self._logged_in_user_id)

    def make_user_admin(self, u, ctx=None):
        if ctx is None: ctx = self.get_ctx(needs_close=True)
        with db.commit_or_rollback(ctx) as ctx:
            with db.conn(ctx) as ctx:
                debug.make_user_admin_by_id(ctx, u.user_id)

    def set_user_invites_left(self, count, u=None):
        if u is None: u = self.get_logged_in_user()
        if u.invites_left == count:
            return
        delta = count - u.invites_left
        with db.commit_or_rollback(u.ctx) as ctx:
            with db.conn(ctx) as ctx:
                if delta > 0:
                    for _ in range(0, delta): u.increment_invites_left()
                else:
                    for _ in range(delta, 0): u.decrement_invites_left()
        assert u.invites_left == count

    def get_sent_emails(self):
        """ Returns a list of EmailMessage objects for an email sent during this test. """
        return self._sent_messages

    def clear_sent_emails(self):
        """ Clear the list of email messages tracked for this test. """
        self._sent_messages = []

    def send_message_now(self, user, msg_type):
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                return message.send_now(ctx, user, msg_type)

    def send_mock_message_now(self, user, msg_type):
        # Clone our known good testing message's details.
        cloned = dict(message._get_all_message_types()['MSG_TEST_SIMPLE'])
        cloned['id'] = msg_type
        # And insert it back into the list of message details.
        message._add_message_type(msg_type, cloned)
        # Record that this msg_type was injected so it can be removed in tearDown
        self._injected_test_msg_types.append(msg_type)

        # Finally send the test message.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                return message.send_now(ctx, user, msg_type)

    def expect_log(self, module_path, message_pattern):
        logging.getLogger(module_path).addFilter(
            ExpectedLogFilter(module_path, message_pattern, self._expected_logs))

    def get_next_cid(self):
        self._cid_counter += 1
        return 'cid%d' % self._cid_counter

    ## Testing only data helpers.
    def inject_callback(self, callback_module, callback_cls):
        callback_module.__dict__[callback_cls.__name__] = callback_cls
        self._injected_test_callbacks.append((callback_module, callback_cls.__name__))

    def enable_capabilities_on_active_rover(self, capability_keys=[], gamestate=None):
        if gamestate is None:
            gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        for cap_key in capability_keys:
            capability_def = capability_module.get_capability_definition(cap_key)
            # Copy the current values.
            current_values = {
                'available_on_rovers': capability_def['available_on_rovers'],
                'always_unlimited': capability_def['always_unlimited']
            }
            if cap_key in self._injected_test_capabilities:
                raise Exception("Cannot call enable_capabilities_on_active_rover more than once for a given capability %s" % cap_key)
            self._injected_test_capabilities[cap_key] = current_values
            # Now force the capability to be available and unlimited for the active rover.
            capability_def['available_on_rovers'] = [rover['rover_chassis']]
            capability_def['always_unlimited'] = 1

    ## Assertion helper methods.
    def assert_assets_equal(self, result, expected):
        """ Given the JSON result of a render_next_target call, verify the given asset names
            were returned from the renderer service."""
        self.assertEqual(set([a['model_name'] for a in result['assets']]), set(expected))

    def assert_equal_seconds(self, dt_a, dt_b):
        """ Given either a datetime object or an int, assert that the two objects have the
            same number of seconds since the epoch. """
        if not type(dt_a) == int: dt_a = utils.to_ts(dt_a)
        if not type(dt_b) == int: dt_b = utils.to_ts(dt_b)
        self.assertEqual(dt_a, dt_b)

    def assert_logged_in(self, response):
        user_id = user_module.user_id_from_request(response.request)
        self.assertIsNotNone(user_id, "used_id SHOULD be in session cookie")
        self.assertRaises(AssertionError, self.assert_not_logged_in, response)
        return user_id

    def assert_not_logged_in(self, response):
        self.assertIsNone(user_module.user_id_from_request(response.request), "used_id should NOT be in session cookie")
        self.assert_(response.status_int > 300 and
                     response.status_int < 400, response)
        self.assert_(response.headers.get('Location'), response.headers)

    ## email_module Dispatcher API to act as a capturing point for all sent emails during the test.
    def send_email_message(self, ctx, email_message):
        self._sent_messages.append(email_message)
    def send_email_alarm(self, email_message):
        self._sent_messages.append(email_message)
    ## email_ses deliver_message API to act as a capturing point for all sent emails during the test.
    def _mock_deliver_email_to_ses(self, email_from, email_to, email_message):
        if self._fail_email_delivery:
            from front.external import amazon_ses
            raise amazon_ses.AmazonError("MyErrorType", "MyErrorCode", "Mock delivery to %s failed." % (email_to))
        self._sent_messages.append(email_module.EmailMessage(email_from, email_to, email_message.subject, email_message.bodyHtml))

    def _last_seen_chip_param(self, last_seen_chip_time=None):
        """ Return the last seen chip time ready to be used as a query parameter. """
        # Use 1 second in the past if time was not provided.
        if last_seen_chip_time is None:
            last_seen_chip_time = utils.usec_js_from_dt(gametime.now() - timedelta(seconds=1))
        return {'last_seen_chip_time': last_seen_chip_time}

class ExpectedLogFilter(logging.Filter):
    def __init__(self, module_path, message_pattern, registry):
        self.module_path = module_path
        self.message_pattern = re.compile(message_pattern)
        registry.append(self)
        self.registry = registry

    def filter(self, record):
        if self.message_pattern.match(record.getMessage()):
            logging.getLogger(self.module_path).removeFilter(self)
            self.registry.remove(self)
            # Hide the message from the logger.
            return False
        return True

    def __repr__(self):
        return "%s:(%s)" % (self.module_path, self.message_pattern.pattern)

class UnexpectedLogFilter(logging.Filter):
    def __init__(self):
        self._unexpected_records = []

    def filter(self, record):
        self._unexpected_records.append(record)
        # Do not hide the message from other loggers.
        return True

    def __len__(self):
        return len(self._unexpected_records)

    def __str__(self):
        return '\n'.join(['[%s:%d] %s' % (r.name, r.lineno, r.getMessage()) for r in self._unexpected_records])
