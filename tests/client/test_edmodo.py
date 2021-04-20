# Copyright (c) 2014 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base

class TestEdmodo(base.TestCase):
    def test_edmodo_install_fail(self):
        # Try to launch with an invalid key and make sure we get an appropriate server response.
        payload={'install':'{"install_key":"BOGUS","user_token":"BOGUS","access_token":"BOGUS","groups":[123,456]}'}
        response = self.app.post('/edmodo/api/install?sandbox=1', payload)
        self.assertTrue('Unauthorized API request: Unknown access token specified.' in response)

    def test_edmodo_launch_fail(self):
        # Try to launch with an invalid key and make sure we get an appropriate server response.
        response = self.app.post('/edmodo/api/launch?launch_key=BOGUS&expiration_time=1234&ln=en', status=400)
        self.assertTrue('Launch key: BOGUS is not recognized' in response)
