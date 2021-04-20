# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import Constants
from front.lib import db
from front.models import chips
from front.models import mission as mission_module
from front.models import region as region_module
from front.callbacks import mission_callbacks
from front.data import audio_regions

from front.tests import base
from front.tests.base import points, rects, SIX_HOURS

class TestMissions(base.TestCase):
    def setUp(self):
        super(TestMissions, self).setUp()
        self.create_user('testuser@example.com', 'pw')
        self._injected_missions = []
        self._injected_regions = []
        self._injected_audio_regions = []

    def tearDown(self):
        super(TestMissions, self).tearDown()
        # Remove any injected mission definitions or regions used for testing.
        current_definitions = mission_module._get_all_mission_definitions()
        for mission_def in self._injected_missions:
            del current_definitions[mission_def]
        current_definitions = region_module._get_all_region_definitions()
        for region_id in self._injected_regions:
            del current_definitions[region_id]
        current_definitions = audio_regions._get_all_regions()
        for region_id in self._injected_audio_regions:
            del current_definitions[region_id]

    def test_target_mission(self):
        class MIS_TEST01_Callbacks(mission_callbacks.BaseCallbacks):
            """ Mission callback which always returns true for any target trigger. """
            @classmethod
            def target_created(self, ctx, user, mission, target):
                return True
        self.inject_callback(mission_callbacks, MIS_TEST01_Callbacks)

        # Add the MIS_TEST01 mission for the current user and verify it is not done.
        self._inject_test_mission(mission_definition='MIS_TEST01',
                                  type="TEST",
                                  title="Test 01 for ${user.first_name}",
                                  summary="This is an example mission summary for ${user.first_name}.",
                                  description="This is an example mission summary for ${user.first_name}.",
                                  done_notice="You finished the mission!",
                                  sort=100,
                                  title_icon="MIS_ICON_TEST1",
                                  description_icon="MIS_ICON_TEST2")
        new_mission = self._add_test_mission('MIS_TEST01')
        self.assertIsNotNone(new_mission)

        # The mission should be not done.
        gamestate = self.get_gamestate()
        mission = self.get_mission_from_gamestate('MIS_TEST01', gamestate=gamestate)
        self.assertEqual(mission['done'], 0)
        self.assertIsNone(mission['done_at'])
        self.assertIsNotNone(mission['title_icon'])
        self.assertIsNotNone(mission['description_icon'])
        # Verify the templating system worked.
        self.assertTrue(gamestate['user']['first_name'] in mission['title'])
        self.assertTrue(gamestate['user']['first_name'] in mission['summary'])
        self.assertTrue(gamestate['user']['first_name'] in mission['description'])

        # The requirements for the MIS_TEST01 mission are to create any target.
        chips_result = self.create_target(**points.FIRST_MOVE)
        chip = self.last_chip_value_for_path(['user', 'missions', '*'], chips_result)
        self.assertTrue(chip['mission_id'].startswith('MIS_TEST01'))
        self.assertEqual(chip['done'], 1)
        self.assertIsNotNone(chip['done_at'])

        # The mission should now be done.
        mission = self.get_mission_from_gamestate('MIS_TEST01')
        self.assertEqual(mission['done'], 1)
        self.assertIsNotNone(mission['done_at'])

        # Attempting to add an existing mission to the user's gamestate should log a warning
        # and return None.
        self.expect_log('front.models.mission', 'Refusing to add exising mission_definition')
        new_mission = self._add_test_mission('MIS_TEST01', allow_done=True)
        self.assertIsNone(new_mission)

    def test_identification_mission(self):
        class MIS_TEST02_Callbacks(mission_callbacks.BaseCallbacks):
            """ Mission callback which always returns true for any species identifcation trigger. """
            @classmethod
            def species_identified(self, ctx, user, mission, target, identified, subspecies):
                return True
        self.inject_callback(mission_callbacks, MIS_TEST02_Callbacks)

        # Add the TEST02 mission for the current user and verify it is not done.
        self._inject_test_mission(mission_definition='MIS_TEST02',
                                  type='TEST',
                                  title="Test 02",
                                  summary="This is another example mission summary.",
                                  sort=100)
        self._add_test_mission('MIS_TEST02')

        self.create_target_and_move(**points.FIRST_MOVE)

        # The mission should be not done.
        gamestate = self.get_gamestate()
        mission = self.get_mission_from_gamestate('MIS_TEST02', gamestate=gamestate)
        self.assertEqual(mission['done'], 0)

        # The requirements for the MIS_TEST02 mission are to attempt to identify any species.
        gamestate = self.get_gamestate()
        target = self.get_most_recent_target_from_gamestate(gamestate=gamestate)
        check_species_url = str(target['urls']['check_species'])
        self.check_species(check_species_url, [rects.SPC_PLANT001])

        # The mission should now be done.
        mission = self.get_mission_from_gamestate('MIS_TEST02')
        self.assertEqual(mission['done'], 1)

    # Test to see that adding a region in region_list_not_done and adding a different region in region_list_done works.
    def test_mission_region_list_different_regions(self):
        class MIS_TEST03_Callbacks(mission_callbacks.BaseCallbacks):
            @classmethod
            def target_created(self, ctx, user, mission, target):
                return True
            # Provide the same region for both the not_done and done state.
            @classmethod
            def region_list_not_done(cls, mission):
                return ['RGN_TEST_01']
            @classmethod
            def region_list_done(cls, mission):
                return ['RGN_TEST_02']
        self.inject_callback(mission_callbacks, MIS_TEST03_Callbacks)

        self._inject_test_region(region_id='RGN_TEST_01', title="Testing region 01.")
        self._inject_test_region(region_id='RGN_TEST_02', title="Testing region 02.")

        self._inject_test_mission(mission_definition='MIS_TEST03',
                                  type='TEST',
                                  title="Test 03",
                                  summary="Testing region_list.",
                                  sort=100)
        self._add_test_mission('MIS_TEST03')

        # The region should be in the gamestate.
        gamestate = self.get_gamestate()
        self.assertIsNotNone(gamestate['user']['regions']['RGN_TEST_01'])
        self.assertTrue('RGN_TEST_02' not in gamestate['user']['regions'])
        mission = self.get_mission_from_gamestate('MIS_TEST03', gamestate=gamestate)
        self.assertEqual(mission['done'], 0)

        # There should have been an ADD chip for the region added by region_list_not_done
        region_chips = self.chips_for_path(['user', 'regions', '*'])
        self.assertEqual(len(region_chips), 1)
        region_chip = region_chips[0]
        self.assertEqual(region_chip['action'], chips.ADD)
        self.assertEqual(region_chip['path'][-1], 'RGN_TEST_01')

        # Move time forward a bit to clear the chips from creating the mission.
        self.advance_now(minutes=10)

        # Create it a target to mark the mission done.
        self.create_target(**points.FIRST_MOVE)

        # There should be a DEL for the first region and an ADD for the second.
        region_chips = self.chips_for_path(['user', 'regions', 'RGN_TEST_01'])
        self.assertEqual(len(region_chips), 1)
        self.assertEqual(region_chips[0]['action'], chips.DELETE)
        self.assertEqual(region_chips[0]['path'][-1], 'RGN_TEST_01')
        region_chips = self.chips_for_path(['user', 'regions', 'RGN_TEST_02'])
        self.assertEqual(len(region_chips), 1)
        self.assertEqual(region_chips[0]['action'], chips.ADD)
        self.assertEqual(region_chips[0]['path'][-1], 'RGN_TEST_02')

        # And the new region should be in the gamestate and the old one should not.
        gamestate = self.get_gamestate()
        self.assertIsNotNone(gamestate['user']['regions']['RGN_TEST_02'])
        self.assertTrue('RGN_TEST_01' not in gamestate['user']['regions'])
        mission = self.get_mission_from_gamestate('MIS_TEST03', gamestate=gamestate)
        self.assertEqual(mission['done'], 1)

    # Test to see that adding the same region in region_list_not_done and region_list_done works (no duplicate chips)
    def test_mission_region_list_same_region(self):
        class MIS_TEST04_Callbacks(mission_callbacks.BaseCallbacks):
            @classmethod
            def target_created(self, ctx, user, mission, target):
                return True
            # Provide the same region for both the not_done and done state.
            @classmethod
            def region_list_not_done(cls, mission):
                return ['RGN_TEST_01']
            @classmethod
            def region_list_done(cls, mission):
                return ['RGN_TEST_01']
        self.inject_callback(mission_callbacks, MIS_TEST04_Callbacks)

        self._inject_test_region(region_id='RGN_TEST_01', title="Testing region 01.")

        self._inject_test_mission(mission_definition='MIS_TEST04',
                                  type='TEST',
                                  title="Test 03",
                                  summary="Testing region_list.",
                                  sort=100)
        self._add_test_mission('MIS_TEST04')

        # The region should still be in the gamestate.
        gamestate = self.get_gamestate()
        self.assertIsNotNone(gamestate['user']['regions']['RGN_TEST_01'])
        mission = self.get_mission_from_gamestate('MIS_TEST04', gamestate=gamestate)
        self.assertEqual(mission['done'], 0)

        # There should have been an ADD chip for the region added by region_list_not_done
        region_chips = self.chips_for_path(['user', 'regions', 'RGN_TEST_01'])
        self.assertEqual(len(region_chips), 1)
        region_chip = region_chips[0]
        self.assertEqual(region_chip['action'], chips.ADD)
        self.assertEqual(region_chip['path'][-1], 'RGN_TEST_01')

        # Move time forward a bit to clear the chips from creating the mission.
        self.advance_now(minutes=10)

        # Create it a target to mark the mission done.
        self.create_target(**points.FIRST_MOVE)

        # There should be no DEL or additional ADD chip.
        region_chips = self.chips_for_path(['user', 'regions', 'RGN_TEST_01'])
        self.assertEqual(len(region_chips), 0)

        # And the region should still be in the gamestate.
        gamestate = self.get_gamestate()
        self.assertIsNotNone(gamestate['user']['regions']['RGN_TEST_01'])
        mission = self.get_mission_from_gamestate('MIS_TEST04', gamestate=gamestate)
        self.assertEqual(mission['done'], 1)

    def test_audio_mission(self):
        class MIS_TEST_AUDIO_01_Callbacks(mission_callbacks.BaseCallbacks):
            """ Mission callback for the audio test mission. """
            @classmethod
            def target_created(self, ctx, user, mission, target):
                # When the target is created, attach a testing detected sound to this target.
                target.detected_sound("SND_TEST_AUDIO")
                return True
        self.inject_callback(mission_callbacks, MIS_TEST_AUDIO_01_Callbacks)

        # Inject the MIS_TEST_AUDIO_01 mission definition which is the mission triggered by the test audio region.
        self._inject_test_mission(mission_definition='MIS_TEST_AUDIO_01',
                                  type="TEST",
                                  title="Test Audio 01",
                                  summary="This is an example audio mission summary.",
                                  sort=100)

        # Create the first known good target to satisfy the TUT01a requirements.
        self.create_target_and_move(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)

        # Locate the audio region center based on the current rover location.
        last_target = self.get_most_recent_target_from_gamestate()
        audio_center = [last_target['lat'] + 0.0001, last_target['lng']]

        # Inject an audio region for unit testing.
        self._inject_test_audio_region(region_id='RGN_AR_TEST_01',
                                       mission_definition='MIS_TEST_AUDIO_01',
                                       center=audio_center,
                                       radius=5.0)

        # Move a short distance that doesn't traverse first and make sure mission is not added.
        self.create_target_and_move(lat=last_target['lat'] + 0.00000001, lng=last_target['lng'])
        self.assertEqual(None, self.get_mission_from_gamestate('MIS_TEST_AUDIO_01'))

        # Move the rover to the center of the audio region which is considered a traversal.
        self.create_target_and_move(lat=audio_center[0], lng=audio_center[1])

        # The audio mission should be added and not done.
        mission = self.get_mission_from_gamestate('MIS_TEST_AUDIO_01')
        self.assertEqual(mission['done'], 0)

        # Create another nearby target which satisfies the mission requirements and adds a detected sound
        # to this target.
        result = self.create_target(arrival_delta=SIX_HOURS, lat=audio_center[0] + 0.00000001, lng=audio_center[1])
        # The sounds collection should be empty in the chip and gamestate even though the sound has been attached
        # to the target so the client can't see the sound file until arrival time.
        chip_value = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(chip_value['sounds'], {})
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['sounds'], {})
        # There should have been no shounds collection chip.
        sound_chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*', 'sounds', '*'])
        self.assertIsNone(sound_chip)

        # Render the target and verify the rendered data is still hidden in the gamestate.
        self.render_next_target(assert_only_one=True)
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['sounds'], {})

        # Advance time to the arrival_time of the target and verify the rendered data is no available
        # in the gamestate.
        self.advance_now(seconds=SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)

        # Now that we have arrived, there should be a chip ADDing the sound.
        sound_chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*', 'sounds', '*'])
        self.assertEqual(sound_chip['action'], chips.ADD)
        self.assertEqual(sound_chip['path'][-1], 'SND_TEST_AUDIO')

        # The sound should also be in the gamestate.
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(len(target['sounds']), 1)
        self.assertIsNotNone(target['sounds']['SND_TEST_AUDIO'])

    ## Tools for injecting test mission definitions and audio regions for unit testing.
    def _inject_test_mission(self, mission_definition, **kwargs):
        mission_module._add_mission_definition(mission_definition, **kwargs)
        self._injected_missions.append(mission_definition)

    def _add_test_mission(self, definition, allow_done=False):
        user = self.get_logged_in_user()
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                new_mission = mission_module.add_mission(ctx, user, definition)
        if not allow_done:
            gamestate_mission = self.get_mission_from_gamestate(definition)
            self.assertEqual(gamestate_mission['done'], 0)
        return new_mission

    def _inject_test_region(self, region_id, title, description="Testing region.", restrict="NONE", style="STYLE_SURVEY",
                                  visible=1, center=[0,0], radius=5.0, shape="CIRCLE", verts=[]):
        region_props = locals().copy()
        del region_props['self']
        region_module._add_region_definition(**region_props)
        self._injected_regions.append(region_id)

    def _inject_test_audio_region(self, region_id, mission_definition, center, radius, shape="CIRCLE", verts=[]):
        region_props = locals().copy()
        del region_props['self']
        current_definitions = audio_regions._get_all_regions()
        current_definitions[region_id] = audio_regions.AudioRegion(**region_props)
        self._injected_audio_regions.append(region_id)
