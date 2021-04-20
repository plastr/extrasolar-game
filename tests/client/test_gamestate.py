# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.models import chips
from front.models import species as species_module

from front.tests import base
from front.tests.base import points, rects

class TestGamestate(base.TestCase):
    def setUp(self):
        super(TestGamestate, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_gamestate(self):
        # Load the entire gamestate with validation enabled to make sure the initial user state it looks right.
        gamestate = self.get_gamestate(skip_validation=False)
        self.assertTrue(len(gamestate) > 0)

        # Gamestate (and all other resources under /ops/api) require authentication.
        self.logout_user()
        response = self.get_gamestate(status=400)
        self.assertEqual(response['errors'], ['Unauthorized request.'])

    # If these resources ever become more complicated than just having mark_viewed,
    # move them to their own test modules.
    def test_mission_mark_viewed(self):
        # Assert that a parent mission is not viewed and also its child parts.
        parent = self.get_mission_from_gamestate("MIS_SIMULATOR")
        self.assertEqual(parent['viewed_at'], None)
        child = self.get_mission_from_gamestate("MIS_SIMULATORa")
        self.assertEqual(child['viewed_at'], None)
    
        result = self.json_post(str(parent['urls']['mark_viewed']))
        all_chips = self.chips_for_path(['user', 'missions', '*'], result)
        # One parent and two child missions.
        self.assertEqual(len(all_chips), 3)
        for c in all_chips:
            self.assertTrue(c['path'][-1].startswith('MIS_SIMULATOR'))
            self.assertEqual(c['action'], chips.MOD)
            self.assertTrue(c['value']['viewed_at'] > 0)
        parent = self.get_mission_from_gamestate("MIS_SIMULATOR")
        self.assertTrue(parent['viewed_at'] > 0)
        child = self.get_mission_from_gamestate("MIS_SIMULATORa")
        self.assertTrue(child['viewed_at'] > 0)
    
    def test_species_mark_viewed(self):
        # Identify some species so we have an object to work with.
        self.create_target_and_move(**points.FIRST_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001])        
        species_id = str(species_module.get_id_from_key("SPC_PLANT001"))

        gamestate = self.get_gamestate()
        species = gamestate['user']['species'][species_id]
        self.assertEqual(species['viewed_at'], None)
    
        result = self.json_post(str(species['urls']['mark_viewed']))
        chip = self.last_chip_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['action'], chips.MOD)
        self.assertTrue(chip['value']['viewed_at'] > 0)
        gamestate = self.get_gamestate()
        species = gamestate['user']['species'][species_id]
        self.assertTrue(species['viewed_at'] > 0)

    def test_achievement_mark_viewed(self):
        gamestate = self.get_gamestate()
        achievement = gamestate['user']['achievements']["ACH_GAME_CREATE_USER"]
        self.assertEqual(achievement['viewed_at'], None)

        result = self.json_post(str(achievement['urls']['mark_viewed']))
        chip = self.last_chip_for_path(['user', 'achievements', '*'], result)
        self.assertEqual(chip['action'], chips.MOD)
        self.assertTrue(chip['value']['viewed_at'] > 0)
        gamestate = self.get_gamestate()
        achievement = gamestate['user']['achievements']["ACH_GAME_CREATE_USER"]
        self.assertTrue(achievement['viewed_at'] > 0)

        # Attempt to mark an achievement that has not been achieved as viewed, which is
        # an error.
        gamestate = self.get_gamestate()
        achievement = gamestate['user']['achievements']["ACH_TRAVEL_300M"]
        self.assertEqual(achievement['viewed_at'], None)
        response = self.json_post(str(achievement['urls']['mark_viewed']), status=400)
        self.assertEqual(response['errors'], ['Unachieved achievement can not be marked viewed.'])
