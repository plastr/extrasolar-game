# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.models import chips

from front.tests import base
from front.tests.base import points, rects

class TestCapabilities(base.TestCase):
    def setUp(self):
        super(TestCapabilities, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_capability(self):
        CAPABILITY_KEY = 'CAP_S1_CAMERA_PANORAMA'
        user = self.get_logged_in_user()
        panorama_cap = user.capabilities[CAPABILITY_KEY]
        self.assertEqual(len(panorama_cap.rover_features), 1)
        metadata_key = panorama_cap.rover_features[0]
        metadata = {metadata_key: ''}
        # Repeatedly use the first point to keep the rover in the sandbox.
        point_in_sandbox = points.by_index(0)

        for index in range(panorama_cap.free_uses):
            result = self.create_target_and_move(metadata=metadata, **point_in_sandbox)
            chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
            self.assertEqual(chip['action'], chips.ADD)
            self.assertEqual(chip['value']['metadata'], metadata)
            gamestate = self.get_gamestate()
            target = self.get_most_recent_target_from_gamestate(gamestate=gamestate)
            self.assertEqual(target['metadata'], metadata)
            if index == 0:
                # After the first target, tag the lander to remove RGN_TAG_LANDER01_CONSTRAINT.
                check_species_url = str(target['urls']['check_species'])
                self.check_species(check_species_url, [rects.SPC_LANDER01])

            chip = self.last_chip_for_path(['user', 'capabilities', '*'], result)
            self.assertEqual(chip['action'], chips.MOD)
            self.assertEqual(chip['value']['uses'], index + 1)
            capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
            self.assertEqual(capability['uses'], index + 1)

        # Snapshot the number of uses.
        capability = self.get_gamestate()['user']['capabilities'][CAPABILITY_KEY]
        uses_before = capability['uses']

        # Attempt to create one more target with the rover feature past its free_uses and verify that an
        # error is logged and the rover feature is disabled because all free uses have been used and this
        # indicates either a client bug or intentional attempted abuse by a player.
        self.expect_log('front.callbacks.target_callbacks', 'Rover feature .* requires capability which has no uses left or is not available, disabling')
        result = self.create_target_and_move(metadata=metadata, **point_in_sandbox)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        # The rover feature metadata key should have been disabled/removed.
        self.assertEqual(chip['value']['metadata'], {})
        # And the uses count should not have changed/no chip should have been sent.
        capability = self.get_gamestate()['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['uses'], uses_before)
        chip = self.last_chip_for_path(['user', 'capabilities', '*'], result)
        self.assertIsNone(chip)

    def test_always_unlimited_capability(self):
        CAPABILITY_KEY = 'CAP_S1_CAMERA_FLASH'
        user = self.get_logged_in_user()
        flash_cap = user.capabilities[CAPABILITY_KEY]
        self.assertEqual(len(flash_cap.rover_features), 1)
        # The flash capability should be always unlimited from the start of the game.
        self.assertEqual(flash_cap.unlimited, 1)
        metadata_key = flash_cap.rover_features[0]
        metadata = {metadata_key: ''}

        # Make sure we can use this capability more than once.
        for index in range(3):
            point = points.by_index(index)
            result = self.create_target_and_move(metadata=metadata, **point)
            chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
            self.assertEqual(chip['action'], chips.ADD)
            self.assertEqual(chip['value']['metadata'], metadata)
            gamestate = self.get_gamestate()
            target = self.get_most_recent_target_from_gamestate(gamestate=gamestate)
            self.assertEqual(target['metadata'], metadata)

            chip = self.last_chip_for_path(['user', 'capabilities', '*'], result)
            self.assertEqual(chip['action'], chips.MOD)
            self.assertEqual(chip['value']['uses'], index + 1)
            capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
            self.assertEqual(capability['uses'], index + 1)

    def test_mutually_exclusive_capabilities(self):
        # Starting rover might not have panorama and infrared capabilities so force them to be available and unlimited.
        self.enable_capabilities_on_active_rover(['CAP_S1_CAMERA_PANORAMA', 'CAP_S1_CAMERA_INFRARED'])

        # Attempting to create a target with both panorama and infrared is not allowed and will result
        # in an log warning and infrared being disabled.
        self.expect_log('front.callbacks.target_callbacks', 'Panorama and infrared features set together')

        metadata =  {'TGT_FEATURE_PANORAMA': '', 'TGT_FEATURE_INFRARED': ''}
        result = self.create_target(metadata=metadata, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['metadata'], {'TGT_FEATURE_PANORAMA': ''})