# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base
from front.tests.base import points, SIX_HOURS

from front import target_image_types
from front.lib import urls, xjson

class TestPublicAPI(base.TestCase):
    def test_photo_highlights(self):
        # Now make this user an admin.
        self.create_user('testuser@example.com', 'password')
        self.make_user_admin(self.get_logged_in_user())

        # Add two normal targets.
        chip_result = self.create_target_and_move(**points.FIRST_MOVE)
        target1_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)['target_id']
        chip_result = self.create_target_and_move(**points.SECOND_MOVE)
        target2_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)['target_id']
        # Add a third target which has not been arrived at, but has been rendered
        chip_result = self.create_target(arrival_delta=SIX_HOURS, **points.THIRD_MOVE)
        self.render_next_target(assert_only_one=True)
        target3_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chip_result)['target_id']

        # Highlight in the opposite order so the oldest target is highlighted last meaning
        # it should be the first highlighted target returned (since it is sorted by highlight time)
        # Add 5 seconds between each highlight since MySQL datetimes only have second resolution.
        self.admin_api_highlight_add(target3_id)
        self.advance_now(seconds=5)
        self.admin_api_highlight_add(target2_id)
        self.advance_now(seconds=5)
        self.admin_api_highlight_add(target1_id)

        # Get fresh gamestate versions of the target data after they have been highlighted and rendered.
        gamestate = self.get_gamestate()
        target1 = self.get_target_from_gamestate(target1_id, gamestate=gamestate)
        target2 = self.get_target_from_gamestate(target2_id, gamestate=gamestate)
        self.get_target_from_gamestate(target3_id, gamestate=gamestate)

        # Logout the user to make sure this public API is indeed public.
        self.logout_user()

        # Test the CORS version of the API
        headers = [('Origin', 'http://www.example.com'), xjson.accept]
        response = self.app.get(urls.api_public_photo_highlights(), headers=headers)
        # Pull te absolute base URL for the testing app 'server' out of the request for later use.
        absolute_root = response.request.application_url
        targets = xjson.loads(response.body)['targets']
        self.assertEqual(len(targets), 2)
        self.assertEqual(response.headers['Access-Control-Allow-Origin'], '*')

        # Test the JSONP version of the API
        response = self.app.get(urls.api_public_photo_highlights_jsonp('test_callback'), headers=[xjson.accept])
        self.assertTrue('test_callback' in response)
        self.assertTrue('targets' in response)
        self.assertTrue(target1_id in response)
        self.assertTrue(target2_id in response)
        self.assertTrue(target3_id not in response)

        # Now test the simple JSON, same domain, version of the API and assert more about the results.
        payload = {'count':20}
        response = xjson.loads(self.app.get(urls.api_public_photo_highlights(),
                                            params=payload,
                                            headers=[xjson.accept]).body)
        targets = response['targets']
        self.assertEqual(len(targets), 2)
        r_target1 = targets[0]
        # Only expecting this many bits of data per target.
        self.assertEqual(len(r_target1), 5)
        # The last highlighted targets should be first.
        self.assertTrue(r_target1['target_id'], target1['target_id'])
        # Verify the expected URLs exist and that they are all absolute.
        self.assertTrue(target1['images'][target_image_types.PHOTO] in r_target1['url_photo'])
        self.assertTrue(absolute_root in r_target1['url_photo'])
        self.assertTrue(target1['images'][target_image_types.THUMB] in r_target1['url_thumbnail'])
        self.assertTrue(absolute_root in r_target1['url_thumbnail'])
        # The large thumbnail URL is only available on panoramas, but the key should still be present.
        self.assertIsNone(r_target1['url_thumbnail_large'])
        self.assertTrue(target1['urls']['public_photo'] in r_target1['url_public_photo'])
        self.assertTrue(absolute_root in r_target1['url_public_photo'])
        # And make sure the second target looks right.
        r_target2 = targets[1]
        self.assertTrue(r_target2['target_id'], target2['target_id'])
