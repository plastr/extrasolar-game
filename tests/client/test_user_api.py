# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import json
from front import activity_alert_types
from front.lib import urls, xjson
from front.models import chips
from front.models import user as user_module
from front.tests import base

def current_app_version():
    return "1.0"

class TestUserAPI(base.TestCase):
    def setUp(self):
        super(TestUserAPI, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_update_viewed_alerts_at(self):
        gamestate = self.get_gamestate()
        update_viewed_alerts_at_url = str(gamestate['user']['urls']['update_viewed_alerts_at'])
        # Check the default value for a new user's frequency setting.
        self.assertEqual(gamestate['user']['viewed_alerts_at'], None)

        payload = {}
        response = self.json_post(update_viewed_alerts_at_url, payload)

        # Verify there were chips and gamestate changes
        found = self.chips_for_path(['user'], response)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['action'], chips.MOD)
        self.assertTrue(found[0]['value']['viewed_alerts_at'] > 0)
        gamestate = self.get_gamestate()
        self.assertTrue(gamestate['user']['viewed_alerts_at'] > 0)

    def test_change_user_notifications(self):
        gamestate = self.get_gamestate()
        user_settings_notifications_url = str(gamestate['user']['urls']['settings_notifications'])
        # Check the default value for a new user's frequency setting.
        self.assertEqual(gamestate['user']['activity_alert_frequency'], activity_alert_types.DEFAULT)

        payload = {'activity_alert_frequency': activity_alert_types.LONG}
        response = self.json_post(user_settings_notifications_url, payload)

        # Verify there were chips and gamestate changes
        found = self.chips_for_path(['user'], response)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['action'], chips.MOD)
        self.assertEqual(found[0]['value']['activity_alert_frequency'], activity_alert_types.LONG)
        gamestate = self.get_gamestate()
        self.assertEqual(gamestate['user']['activity_alert_frequency'], activity_alert_types.LONG)

    def test_api_user_authenticate(self):
        # Make sure our user is logged out to start.
        self.logout_user()

        # Note that we're using an HTTP post instead of a json_post because HTTP allows us to set
        # the session cookie on a successful login.
        # Test the login API with a bad password.
        payload={'login_email':'testuser@example.com', 'login_password':'bad_pass', 'form_type':'login', 'version':current_app_version()}
        response = self.app.post(urls.api_user_login_ajax(), payload, status=401)
        self.assertTrue('Incorrect email or password' in str(response))
        self.assertFalse('extrasolar_test_session' in str(response))
        
        # Make sure that if we use the check_session API, it indicates no valid session
        response = self.app.get(urls.api_check_session(current_app_version()), status=401)
        json_response = json.loads(response.body)
        self.assertTrue('No valid session.' in str(response))

        # Test with the correct password. We should get a success response and a session cookie.
        payload={'login_email':'testuser@example.com', 'login_password':'pw', 'form_type':'login', 'version':current_app_version()}
        response = self.app.post(urls.api_user_login_ajax(), payload, status=200)
        # We expect the body to be valid json.
        json_response = json.loads(response.body)
        self.assertTrue(json_response['status'] == 'ok')
        self.assertTrue(json_response['valid'] == 1)
        
        # Use the check_session API to see if we have a valid session.
        response = self.app.get(urls.api_check_session(current_app_version()), status=200)
        json_response = json.loads(response.body)
        self.assertTrue(json_response['status'] == 'ok')
        self.assertTrue(json_response['valid'] == 1)

    def test_api_signup_user_and_validate(self):
        # Make sure our user is logged out to start. We'll create a new user from scratch.
        self.logout_user()

        # Test the login API with a bad password.
        payload={'signup_email':'newuser@example.com', 'signup_password':'pass', 'form_type':'signup',
            'first_name':'Testy', 'last_name':'McTesterson', 'version':current_app_version()}
        response = self.app.post(urls.api_user_signup_ajax(), payload)
        json_response = json.loads(response.body)
        self.assertTrue(json_response['status'] == 'ok')
        self.assertTrue(json_response['valid'] == 0)
        self.assertTrue(json_response['first_name'] == 'Testy')
        url_validate = json_response['url_validate']

        # Now that the user is logged in, store their UUID
        self._logged_in_user_id = user_module.user_id_from_request(response.request)

        user = self.get_logged_in_user()
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertEqual(user.first_name, 'Testy')
        self.assertEqual(user.last_name, 'McTesterson')
        self.assertFalse(user.valid)

        # Load a bogus validation token and verify we get an error.
        bogus_backdoor_url = urls.api_validate('bogus')
        self.expect_log('front.models.user', 'Invalid token when attempting user validation.*')
        response = self.app.get(bogus_backdoor_url, status=401)
        json_response = json.loads(response.body)
        self.assertTrue(json_response['status'] == 'error')

        # Follow the real backdoor link. The user should now be validated.
        response = self.app.get(url_validate)
        json_response = json.loads(response.body)
        self.assertTrue(json_response['status'] == 'ok')
        self.assertTrue(json_response['valid'] == 1)
        user = self.get_logged_in_user()
        self.assertTrue(user.valid)

        # Load the backdoor URL again and verify that we get the same result.
        response = self.app.get(url_validate)
        json_response = json.loads(response.body)
        self.assertTrue(json_response['status'] == 'ok')
