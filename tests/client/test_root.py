# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import timedelta

from front.tests import base
from front.tests.base import rects, points

from front import target_image_types

class TestRoot(base.TestCase):
    def test_get(self):
        response = self.app.get('/')
        self.assertTrue("Welcome to Extrasolar!" in response)

    def test_profile(self):
        self.create_user('testuser@example.com', 'password')
        gamestate = self.get_gamestate()
        response = self.app.get(gamestate['urls']['user_public_profile'])
        self.assertTrue(response)

    def test_public_photo(self):
        self.create_user('testuser@example.com', 'password')

        # Create a target and verify we cannot see that photo yet.
        result = self.create_target(**points.FIRST_MOVE)
        target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        response = self.app.get(target['urls']['public_photo'])
        self.assertTrue('not available' in response)

        # Now render the photo.
        self.render_next_target(assert_only_one=True)
        response = self.app.get(target['urls']['public_photo'])
        self.assertTrue('not available' in response)

        # And advance the game to the arrival time.
        travel_time = target['arrival_time'] - target['start_time']
        self.advance_now(seconds=travel_time)
        # Should now be able to see the photo.
        target = self.get_most_recent_target_from_gamestate()
        response = self.app.get(target['urls']['public_photo'])
        self.assertTrue(target['images'][target_image_types.PHOTO] in response)

        # Now render a classified photo and verify that is not displayed on the page.
        result = self.create_target(**points.SECOND_MOVE)
        target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        response = self.app.get(target['urls']['public_photo'])
        self.assertTrue('not available' in response)

        # Now render the photo as classified. Should still be listed as not available.
        self.render_next_target(assert_only_one=True, classified=1)
        response = self.app.get(target['urls']['public_photo'])
        self.assertTrue('not available' in response)

        # And advance the game to the arrival time. Should now be listed as classified.
        travel_time = target['arrival_time'] - target['start_time']
        self.advance_now(seconds=travel_time)
        target = self.get_most_recent_target_from_gamestate()
        response = self.app.get(target['urls']['public_photo'])
        self.assertTrue('is classified' in response)
        self.assertTrue(target['images'][target_image_types.PHOTO] not in response)

    def test_photo_bad_uuid(self):
        # Pass a bad encoded UUID to the photo page. This also acts as a test for the decode_base62_uuid wrapped.
        self.create_user('testuser@example.com', 'password')
        target = self.get_most_recent_target_from_gamestate()
        self.expect_log('front.resource', 'Bad encoded UUID URL parameter.*')
        self.app.get(target['urls']['public_photo'] + '%5B/spoiler%5D', status=400)

    def test_last_accessed(self):
        self.create_user('testuser@example.com', 'password')
        user = self.get_logged_in_user()
        # last_accessed should have an initial value (the time the user was created == user.epoch)
        self.assertIsNotNone(user.last_accessed)

        # Now load the gamestate for the first time.
        self.get_gamestate()
        user = self.get_logged_in_user()
        first_load = user.last_accessed
        self.advance_now(minutes=10)
        # And load it again a few minutes later.
        self.get_gamestate()

        # last_accessed should have advanced the same amount.
        user = self.get_logged_in_user()
        second_load = user.last_accessed
        self.assertTrue(second_load > first_load)
        self.assertEqual(second_load - first_load, timedelta(minutes=10))

        # Creating a target should advance last_accessed as well
        self.advance_now(minutes=10)
        self.create_target(**points.FIRST_MOVE)        
        self.render_next_target()
        user = self.get_logged_in_user()
        third_load = user.last_accessed
        self.assertTrue(third_load > second_load)
        self.assertEqual(third_load - second_load, timedelta(minutes=10))

        # As should identifying a species.
        self.advance_now(minutes=10)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.check_species(check_species_url, [rects.SPC_PLANT001])
        user = self.get_logged_in_user()
        fourth_load = user.last_accessed
        self.assertTrue(fourth_load > third_load)
        self.assertEqual(fourth_load - third_load, timedelta(minutes=10))
