# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import re

from front.models import chips, progress
from front import Constants, debug, rover_keys, rover_chassis
from front.lib import utils
from front.models import species as species_module
from front.models import achievement as achievement_module
from front.data import scene

from front.tests import base
from front.tests.game import story_case
from front.tests.game.story_case import GameTestBeat

class TestFastestGame(story_case.StoryTestCase):
    ROUTE_FILES = [debug.routes.FASTEST_STORY_ROVER1,
                   debug.routes.FASTEST_STORY_ROVER2,
                   debug.routes.FASTEST_STORY_ROVER3]

    # Ignore all of the special date achievements which are tested in test_special_date_achievements
    ACHIEVEMENTS_IGNORE = achievement_module.get_special_date_achievement_keys()

    # This beat will be run before any beat in the story/route data is run to emulate
    # completing the tutorials before creating any targets and to assert the initial gamestate.
    class COMPLETE_TUTORIALS(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            not_done_missions      = ['MIS_SIMULATOR', 'MIS_SIMULATORa', 'MIS_SIMULATORb']
            done_missions          = []
            present_regions        = ['RGN_ISLAND01', 'RGN_SANDBOX',  'RGN_SANDBAR', 'RGN_NW_CONSTRAINT',
                                      'RGN_NE_CONSTRAINT', 'RGN_NORTH_CONSTRAINT', 'RGN_OBELISK_CONSTRAINT',
                                      'RGN_AUDIO_MYSTERY01_CONSTRAINT']
            messages_new           = ['MSG_WELCOME']
            progress_new           = [progress.names.PRO_USER_CREATED]
            achieved_new           = ['ACH_GAME_CREATE_USER']
            available_capabilities = ['CAP_S1_CAMERA_FLASH', 'CAP_S1_CAMERA_PANORAMA', 'CAP_S1_ROVER_FAST_MOVE', 'CAP_S1_ROVER_3_MOVES', 'CAP_S1_ROVER_4_MOVES']
            # Emulate the user completing the tutorials.
            client_progress        = Constants.SIMULATOR_PROGRESS_KEYS

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # We should start with 5 invitations.
                test.assertEqual(gamestate['user']['invites_left'], 5)

        class LEAVE(GameTestBeat.Move):
            # Verify immediate additional initial gamestate after tutorials are completed.
            messages_new      = ['MSG_SIMULATOR_DONE']
            progress_new      = Constants.SIMULATOR_PROGRESS_KEYS
            done_missions     = ['MIS_SIMULATOR', 'MIS_SIMULATORa', 'MIS_SIMULATORb']
            not_done_missions = ['MIS_TUT01', 'MIS_TUT01a', 'MIS_TUT01b']
            present_regions   = ['RGN_LANDER01_WAYPOINT', 'RGN_TAG_LANDER01_CONSTRAINT']

    START_BEAT = COMPLETE_TUTORIALS

    class AT_LANDER(GameTestBeat):
        class CREATED(GameTestBeat.Move):
            # Creating a target near the lander to finish MIS_TUT01a.
            done_missions     = ['MIS_TUT01a']
            absent_regions    = ['RGN_LANDER01_WAYPOINT']
            # These messages and missions are delayed from completing the tutorials.
            messages_new      = ['MSG_ROVER_INTRO01', 'MSG_JANE_INTRO', 'MSG_KTHANKS']
            not_done_missions = ['MIS_SPECIES_FIND_5']

        # Identify the lander to satisfy MIS_TUT01b.
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_LANDER01']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Assert the active rover has the expected rover key and chassis
                active_rover = test.get_active_rover(gamestate)
                test.assertEqual(active_rover['rover_key'], rover_keys.RVR_S1_INITIAL)
                test.assertEqual(active_rover['rover_chassis'], rover_chassis.RVR_CHASSIS_JRS)

                # The same test map_tiles chips should be sent for every target on arrival, so check
                # the first one and assume the rest are working.
                map_tiles = test.chips_for_path(['user', 'map_tiles', '*'], chips_struct)
                test.assertEqual(len(map_tiles), len(base.TEST_TILES))
                test.assertEqual(map_tiles[0]['action'], chips.ADD)
                test.assertEqual(map_tiles[1]['action'], chips.ADD)
                test.assertEqual(map_tiles[1]['path'], ['user', 'map_tiles', base.TILE_KEY])

        # A message should have been sent and two new missions should have been unlocked.
        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_TUT01', 'MIS_TUT01b']
            absent_regions    = ['RGN_TAG_LANDER01_CONSTRAINT']

    class ID_5_SPECIES(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = debug.rects.PLANTS[0:5]
            not_done_missions = ['MIS_ARTIFACT01']
            present_regions   = ['RGN_ARTIFACT01_WAYPOINT']
            messages_new      = ['MSG_ARTIFACT01a']

    class ID_5_SPECIES_DONE(GameTestBeat):
        # Within the maximum species delay all the species data is fully available and the mission should be done.
        BEAT_ARRIVAL_DELTA = utils.in_seconds(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)

        class ARRIVED(GameTestBeat.Move):
            done_missions     = ['MIS_SPECIES_FIND_5']
            # Identifying 3 unique species in the same target achieves the ACH_SPECIES_TAG_3 achievement.
            messages_new      = ['MSG_ACH_SPECIES_TAG_3']
            achieved_new      = ['ACH_SPECIES_TAG_3']

    story_case.StoryTestCase.after_beat_run_beat(ID_5_SPECIES, ID_5_SPECIES_DONE)

    class RECEIVE_PHOTOSYNTHESIS_MESSAGES(GameTestBeat):
        # The last of the photo synthesis messages arrive after 36 hours. One of the messages also
        # adds the MIS_SPECIES_FIND_10 mission.
        BEAT_ARRIVAL_DELTA = utils.in_seconds(hours=36)

        class ARRIVED(GameTestBeat.Move):
            not_done_missions = ['MIS_SPECIES_FIND_10']
            messages_new      = ['MSG_SCI_PHOTOSYNTHESISa', 'MSG_SCI_PHOTOSYNTHESISb', 'MSG_SCI_GASSES']

    story_case.StoryTestCase.after_beat_run_beat(ID_5_SPECIES_DONE, RECEIVE_PHOTOSYNTHESIS_MESSAGES)

    class AT_ARTIFACT01(GameTestBeat):
        # Identify the artifact, which is the MIS_ARTIFACT01 requirement.
        
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_ARTIFACT01']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_ARTIFACT01']
            present_regions   = ['RGN_ARTIFACT01_ICON']
            absent_regions    = ['RGN_ARTIFACT01_WAYPOINT']

        # By the time we get to the next point, 2 mores messages have been sent.
        class ARRIVED_NEXT(GameTestBeat.Move):
            messages_new      = ['MSG_ARTIFACT01d', 'MSG_ARTIFACT01b', 'MSG_ARTIFACT01c']
            not_done_missions = ['MIS_ARTIFACT01_CLOSEUP']

    class AT_ARTIFACT01_CLOSEUP(GameTestBeat):
        # Identify the artifact a second time to complete this mission.
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_ARTIFACT01']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_ARTIFACT01_CLOSEUP']

        # By the time we get to the next point, the sandbox should have been lifted and a few
        # messages have been sent. Several of these changes happen is the MSG_ARTIFACT01g callback.
        class ARRIVED_NEXT(GameTestBeat.Move):
            not_done_missions = ['MIS_EXPLORE_ISLAND']
            present_regions   = ['RGN_SANDBOX_SAFE01', 'RGN_SANDBOX_SAFE02']
            absent_regions    = ['RGN_SANDBOX']
            progress_new      = [progress.names.PRO_SANDBOX_SAFETY_DISABLED]
            messages_new      = ['MSG_ARTIFACT01e', 'MSG_ARTIFACT01f', 'MSG_ARTIFACT01g']

    class JUST_INSIDE_SANDBOX(GameTestBeat):
        # Add the next two targets inside the previously restricted sandbox which starts the stuck rover sequence.
        # The second target is past the point where the rover gets stuck and will be neutered and then deleted
        # when the rover becomes stuck.
        CREATE_NEXT_TARGETS = 2

        class ARRIVED(GameTestBeat.Move):
            achieved_new           = ['ACH_TRAVEL_300M']
            messages_new           = ['MSG_ACH_TRAVEL_300M']

    class OUTSIDE_SANDBOX(GameTestBeat):
        class CREATED(GameTestBeat.Move):
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Verify special target metadata was set and a MOD chip was issued for this target.
                test.assertEqual(target_struct['metadata'], {'TGT_S1_STUCK_IN_DUNES': ''})
                target_chips = test.chips_for_path(['user', 'rovers', '*', 'targets', target_struct['target_id']], struct=chips_struct)
                test.assertEqual(len(target_chips), 2)
                test.assertEqual(target_chips[0]['action'], chips.ADD)
                test.assertEqual(target_chips[1]['action'], chips.MOD)
                test.assertEqual(target_chips[1]['value']['metadata'], {'TGT_S1_STUCK_IN_DUNES': ''})

        class ARRIVED(GameTestBeat.Move):
            done_missions          = ['MIS_EXPLORE_ISLAND']
            not_done_missions      = ['MIS_FIND_STUCK_ROVER']
            present_regions        = ['RGN_FIND_STUCK_ROVER_WAYPOINT', 'RGN_FIND_STUCK_ROVER_CONSTRAINT']
            absent_regions         = ['RGN_SANDBOX_SAFE01', 'RGN_SANDBOX_SAFE02', 'RGN_SANDBAR']
            progress_new           = [progress.names.PRO_ROVER_STUCK]
            messages_new           = ['MSG_ROVER_WILL_BE_STUCK', 'MSG_ROVER_STUCKa', 'MSG_AUDIO_TUTORIAL01a']
            available_capabilities = ['CAP_S1_CAMERA_INFRARED']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # At this point, we should now have a new rover. Verify that the rover_id for the target
                # that was rendered for this point (the spot where the old rover was stuck) is different
                # from what is currently the active rover (the new rover).
                rendered_rover = test.get_rover_for_target_id(target_struct['target_id'], gamestate)
                active_rover = test.get_active_rover(gamestate)
                test.assertTrue(rendered_rover['rover_id'] != active_rover['rover_id'])

                # Assert the new rover has the expected rover key and chassis
                test.assertEqual(active_rover['rover_key'], rover_keys.RVR_S1_UPGRADE)
                test.assertEqual(active_rover['rover_chassis'], rover_chassis.RVR_CHASSIS_SRK)

                # Verify that the MOD and ADD chips were issued for the old and new rovers.
                rover_chips = test.chips_for_path(['user', 'rovers', '*'], struct=chips_struct)
                test.assertEqual(len(rover_chips), 2)
                test.assertEqual(rover_chips[0]['action'], chips.MOD)
                test.assertEqual(rover_chips[0]['path'], ['user', 'rovers', rendered_rover['rover_id']])
                test.assertEqual(rover_chips[0]['value']['active'], 0)
                test.assertEqual(rover_chips[1]['action'], chips.ADD)
                test.assertEqual(rover_chips[1]['path'], ['user', 'rovers', active_rover['rover_id']])
                test.assertEqual(rover_chips[1]['value']['active'], 1)

                # The first rover should still have the original asset as the last photo it takes is still
                # from its perspective (a shadow)
                test.assert_assets_equal(target_struct['_render_result'], ["LANDER01", "ROVER_SHADOW"])

                # Verify the RGN_FIND_STUCK_ROVER_WAYPOINT region looks correct as its center location is derived
                # from the location where the rover gets stuck.
                struct_rover_waypoint = gamestate['user']['regions']['RGN_FIND_STUCK_ROVER_WAYPOINT']
                stuck_last_target = sorted(rendered_rover['targets'].values(), key=lambda m: m['arrival_time'])[-1]
                test.assertEqual(struct_rover_waypoint['center'][0], stuck_last_target['lat'])
                test.assertEqual(struct_rover_waypoint['center'][1], stuck_last_target['lng'])

                # Verify that the stuck target has the appropriate metadata.
                test.assertEqual(stuck_last_target['metadata'], {'TGT_S1_STUCK_IN_DUNES': ''})

        class ARRIVED_NEXT(GameTestBeat.Move):
            messages_new      = ['MSG_ROVER_INTRO02', 'MSG_ROVER_STUCKb']

    class WAY_OUTSIDE_SANDBOX(GameTestBeat):
        TARGET_WILL_BE_NEUTERED = True

        class CREATED(GameTestBeat.Move):
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Verify that the target that will be neutered and deleted is currently in the gamestate.
                neutered_target_id = target_struct['target_id']
                test.assertTrue(test.get_target_from_gamestate(neutered_target_id, gamestate=gamestate) != None)

        class ARRIVED(GameTestBeat.Move):
            # Though the target is deleted from the gamestate, the Route/Story still move us to this Point
            # in the Route, where we can verify the target has been removed from the gamestate and not
            # rendered.
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # The neutered target should have been deleted when the rover got stuck.
                neutered_target_id = target_struct['target_id']
                test.assertTrue(test.get_target_from_gamestate(neutered_target_id, gamestate=gamestate) == None)
                # And no target should have been rendered (no renderer payload returned).
                test.assertEqual(target_struct['_render_result'], {'status': 'ok'})

    class ID_10_SPECIES(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = debug.rects.PLANTS[5:11]

    class ID_10_SPECIES_DONE(GameTestBeat):
        # Within the maximum species delay all the species data is fully available and the mission should be done.
        BEAT_ARRIVAL_DELTA = utils.in_seconds(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)

        class ARRIVED(GameTestBeat.Move):
            done_missions     = ['MIS_SPECIES_FIND_10']

    story_case.StoryTestCase.after_beat_run_beat(ID_10_SPECIES, ID_10_SPECIES_DONE)

    class AFTER_ID_10_SPECIES(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_FIND_10']
            not_done_missions = ['MIS_SPECIES_FIND_15']

    class AT_STUCK_ROVER(GameTestBeat):
        # Identify the stuck, disassembled rover, which is the MIS_FIND_STUCK_ROVER requirement.
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_ROVER_DISASSEMBLED']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # The first rover should now have the stuck rover asset.
                test.assert_assets_equal(target_struct['_render_result'], ["LANDER01", "ROVER_SHADOW", "ROVER_DISASSEMBLED"])

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_FIND_STUCK_ROVER']
            absent_regions    = ['RGN_FIND_STUCK_ROVER_CONSTRAINT']

    class OUTSIDE_AUDIO_TUTORIAL01_TRIGGER(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Verify no mission changes just outside the trigger region.
            not_done_missions = ['MIS_VISIT_CENTRAL_PLATEAU']
            present_regions   = ['RGN_AUDIO_TUTORIAL01_CARROT']
            messages_new      = ['MSG_FOUND_ROVER01a', 'MSG_FOUND_ROVER01b', 'MSG_INVITATIONSa']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Verify that a MOD chip was sent to increment the user's invitations.
                user_chips = test.chips_for_path(['user'], struct=chips_struct)
                test.assertEqual(len(user_chips), 1)
                test.assertEqual(user_chips[0]['action'], chips.MOD)
                test.assertEqual(user_chips[0]['path'], ['user'])
                test.assertEqual(user_chips[0]['value']['invites_left'], 10)
                
                # Verify that the gamestate has been updated accordingly.
                test.assertEqual(gamestate['user']['invites_left'], 10)

    class INSIDE_AUDIO_TUTORIAL01_TRIGGER(GameTestBeat):
        class CREATED(GameTestBeat.Move):
            # Now create the point inside the audio detection region, which should still not satisfy the
            # AUDIO_TUTORIAL01 requirement as that fires on arrival.
            pass

        # Now move inside the trigger region which should create the second part of the tutorial mission.
        class ARRIVED(GameTestBeat.Move):
            not_done_missions = ['MIS_AUDIO_TUTORIAL01', 'MIS_AUDIO_TUTORIAL01a', 'MIS_AUDIO_TUTORIAL01b']
            present_regions   = ['RGN_AUDIO_TUTORIAL01_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_ORGANIC01']

    class OUTSIDE_AUDIO_TUTORIAL01_ZONE(GameTestBeat):
        # Now move to the just outside the detection zone. Verify no mission changes.
        class ARRIVED(GameTestBeat.Move):
            not_done_missions = ['MIS_SCI_FIND_COMMON', 'MIS_SCI_FIND_COMMONa', 'MIS_SCI_FIND_COMMONb', 'MIS_SCI_FIND_COMMONc']
            messages_new      = ['MSG_SCI_PHOTOSYNTHESISc']

    class INSIDE_AUDIO_TUTORIAL01_ZONE(GameTestBeat):
        # Creating inside the detection zone should not satisfy the mission.
        class CREATED(GameTestBeat.Move):
            pass

        # Now move inside the region, which is the MIS_AUDIO_TUTORIAL01a requirement.
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_ANIMAL001_ZONE']
            done_missions     = ['MIS_AUDIO_TUTORIAL01a']
            present_regions   = ['RGN_AUDIO_TUTORIAL01_PINPOINT']
            absent_regions    = ['RGN_AUDIO_TUTORIAL01_ZONE']

    class AT_AUDIO_TUTORIAL01_PINPOINT(GameTestBeat):
        # Now move to the audio source and identify the audio source species,
        # which is the MIS_AUDIO_TUTORIAL01b requirement.
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_ANIMAL001']
            messages_new      = ['MSG_AUDIO_TUTORIAL01b']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_TUTORIAL01b', 'MIS_AUDIO_TUTORIAL01']
            absent_regions    = ['RGN_AUDIO_TUTORIAL01_PINPOINT']
            present_regions   = ['RGN_AUDIO_TUTORIAL01_ICON', 'RGN_SCI_VARIATION_PINPOINT']
            messages_new      = ['MSG_AUDIO_TUTORIAL01c', 'MSG_SCI_VARIATIONa']
            not_done_missions = ['MIS_SCI_VARIATION']

    class OUTSIDE_AUDIO_MYSTERY06_TRIGGER(GameTestBeat):
        class CREATED(GameTestBeat.Move):
            pass
        class ARRIVED(GameTestBeat.Move):
            pass

    class INSIDE_AUDIO_MYSTERY06_TRIGGER(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # We should have tripped the obelisk 6 audio trigger.
            not_done_missions = ['MIS_AUDIO_MYSTERY06', 'MIS_AUDIO_MYSTERY06a', 'MIS_AUDIO_MYSTERY06b']
            present_regions   = ['RGN_AUDIO_MYSTERY06_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY06']
            # The carrot mission (MIS_VISIT_CENTRAL_PLATEAU), should be completed now.
            done_missions     = ['MIS_VISIT_CENTRAL_PLATEAU']
            absent_regions    = ['RGN_AUDIO_TUTORIAL01_CARROT']
            
    class OUTSIDE_AUDIO_MYSTERY01_TRIGGER(GameTestBeat):
        class CREATED(GameTestBeat.Move):
            pass
        class ARRIVED(GameTestBeat.Move):
            pass

    class INSIDE_AUDIO_MYSTERY01_TRIGGER(GameTestBeat):
        # Now move inside the trigger region which should create the second part of the tutorial mission.
        class ARRIVED(GameTestBeat.Move):
            not_done_missions = ['MIS_AUDIO_MYSTERY01', 'MIS_AUDIO_MYSTERY01a', 'MIS_AUDIO_MYSTERY01b']
            present_regions   = ['RGN_AUDIO_MYSTERY01_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY01']

    class OUTSIDE_AUDIO_MYSTERY01_ZONE(GameTestBeat):
        # Now move to the just outside the detection zone. Verify no mission changes.
        class ARRIVED(GameTestBeat.Move):
            pass

    class INSIDE_AUDIO_MYSTERY01_ZONE(GameTestBeat):
        # Creating inside the detection zone should not satisfy the mission.
        class CREATED(GameTestBeat.Move):
            pass

        # Now move inside the region, which is the MIS_AUDIO_MYSTERY01a requirement.
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_AUDIO_MYSTERY01']
            done_missions     = ['MIS_AUDIO_MYSTERY01a']
            present_regions   = ['RGN_AUDIO_MYSTERY01_PINPOINT']
            absent_regions    = ['RGN_AUDIO_MYSTERY01_ZONE']

    class AT_AUDIO_MYSTERY01_PINPOINT(GameTestBeat):
        # Now move to the audio source and identify the audio source,
        # which is the MIS_AUDIO_MYSTERY01b requirement.
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN02']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # We are fairly far into the game now, attempt to load the user's profile page
                # to make sure nothing is broken.
                response = test.app.get(gamestate['urls']['user_public_profile'])
                test.assertTrue(response)

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_MYSTERY01', 'MIS_AUDIO_MYSTERY01b']
            absent_regions    = ['RGN_AUDIO_MYSTERY01_PINPOINT', 'RGN_AUDIO_MYSTERY01_CONSTRAINT']
            present_regions   = ['RGN_AUDIO_MYSTERY01_ICON']
            progress_new      = [progress.names.PRO_TAGGED_ONE_OBELISK]

        class ARRIVED_NEXT(GameTestBeat.Move):
            not_done_missions = ['MIS_FIND_EM_SOURCE', 'MIS_FIND_GPS_UNIT', 'MIS_FIND_GPS_UNITa', 'MIS_FIND_GPS_UNITb']
            messages_new      = ['MSG_OBELISK01a', 'MSG_MISSION02a', 'MSG_PHONE01a', 'MSG_PHONE01b', 'MSG_GPSa', 'MSG_ENCRYPTION01']
            present_regions   = ['RGN_GPS_ICON', 'RGN_GPS_MISSION_ICON', 'RGN_EM_SOURCE_PINPOINT']
            progress_new      = [progress.names.PRO_SHOW_GPS_REGION]

    class AT_GPS(GameTestBeat):
        # Tagging the GPS unit satisfies MIS_FIND_GPS_UNITa.  The player needs to use the
        # GPS name as a password to satisfy MIS_FIND_GPS_UNITb.
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_MANMADE005']
            messages_unlock   = ['MSG_ENCRYPTION01']

            @classmethod
            def password_to_unlock_message(cls, message, test, gamestate):
                test.assertEqual(message['msg_type'], 'MSG_ENCRYPTION01')
                # Because this beat is both id-ing the species and using that species to unlock
                # the message we need to pull a fresh gamestate to get the species data.
                gamestate = test.get_gamestate()

                species_id = str(species_module.get_id_from_key('SPC_MANMADE005'))
                species_name = gamestate['user']['species'][species_id]['name']
                # The password to the message is the name of the GPS unit, which should now be
                # available in the species catalog.  It's the last word in the species name with
                # all caps and digits.
                password = re.search(r'.* ([A-Z0-9]+)$', species_name).group(1)
                # The keycode should also be in the species description.
                test.assertTrue(password in gamestate['user']['species'][species_id]['description'])
                return password

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_FIND_GPS_UNITa', 'MIS_FIND_GPS_UNITb' , 'MIS_FIND_GPS_UNIT']
            absent_regions    = ['RGN_GPS_MISSION_ICON']

        class ARRIVED_NEXT(GameTestBeat.Move):
            messages_new      = ['MSG_GPSc', 'MSG_ENCRYPTION02']

    class TOWARD_CENTRAL_MONUMENT(GameTestBeat):
        class ARRIVED_NEXT(GameTestBeat.Move):
            # MSG_PHONE03a and MSG_EDNA01 are part of a MessageSequence.
            messages_new      = ['MSG_PHONE03a', 'MSG_EDNA01']

    class AT_CENTRAL_MONUMENT(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN08']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_FIND_EM_SOURCE']
            progress_new      = [progress.names.PRO_ENABLE_NE_REGION]
            absent_regions    = ['RGN_NE_CONSTRAINT', 'RGN_EM_SOURCE_PINPOINT']
            present_regions   = ['RGN_EM_SOURCE_ICON']

        class ARRIVED_NEXT(GameTestBeat.Move):
            # MSG_EDNA02 is part of a MessageSequence.
            messages_new      = ['MSG_MISSION02c', 'MSG_MISSION02d', 'MSG_GO_TO_RUINS', 'MSG_EDNA02']
            not_done_missions = ['MIS_VISIT_RUINS']
            present_regions   = ['RGN_RUINS_PINPOINT']

    class TOWARD_RUINS01(GameTestBeat):
        class ARRIVED_NEXT(GameTestBeat.Move):
            # MSG_EDNA04 is part of a MessageSequence.
            messages_new      = ['MSG_EDNA04']

    class INSIDE_OBELISK02_TRIGGER(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            not_done_missions = ['MIS_AUDIO_MYSTERY02', 'MIS_AUDIO_MYSTERY02a', 'MIS_AUDIO_MYSTERY02b']
            present_regions   = ['RGN_AUDIO_MYSTERY02_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY02']

    class INSIDE_OBELISK02_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_AUDIO_MYSTERY02']
            done_missions     = ['MIS_AUDIO_MYSTERY02a']
            absent_regions    = ['RGN_AUDIO_MYSTERY02_ZONE']
            present_regions   = ['RGN_AUDIO_MYSTERY02_PINPOINT']

    class AT_OBELISK02_PINPOINT(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN02_SUB01']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_MYSTERY02b', 'MIS_AUDIO_MYSTERY02']
            absent_regions    = ['RGN_AUDIO_MYSTERY02_PINPOINT']
            present_regions   = ['RGN_AUDIO_MYSTERY02_ICON']

        class ARRIVED_NEXT(GameTestBeat.Move):
            messages_new      = ['MSG_OBELISK02a', 'MSG_OBELISK02b']

    class AT_RUINS01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN09']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_VISIT_RUINS']
            absent_regions    = ['RGN_RUINS_PINPOINT']
            present_regions   = ['RGN_RUINS_ICON']

    class AT_RUINS02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN09']
            messages_new      = ['MSG_RUINSa', 'MSG_ENKI01a']
            not_done_missions = ['MIS_PHOTOGRAPH_RUINS']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_PHOTOGRAPH_RUINS']
            not_done_missions = ['MIS_PHOTOGRAPH_RUINS02']

    class AT_RUINS03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN09']
            messages_new      = ['MSG_RUINSb', 'MSG_RUINSd', 'MSG_EDNA05']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_PHOTOGRAPH_RUINS02']
            absent_regions    = ['RGN_NORTH_CONSTRAINT']
            progress_new      = [progress.names.PRO_ENABLE_NORTH_REGION]

    class TOWARD_RUINS_SIGNAL01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # En route to target.
            messages_new      = ['MSG_RUINSc', 'MSG_EDNA08']
            not_done_missions = ['MIS_RUINS_SIGNAL_SOURCE']
            present_regions   = ['RGN_RUINS_SIGNAL_PINPOINT']

    class TOWARD_RUINS_SIGNAL02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_ENKI01c']

    class AT_RUINS_SIGNAL(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN10']
            not_done_missions = ['MIS_AUDIO_MYSTERY03', 'MIS_AUDIO_MYSTERY03a', 'MIS_AUDIO_MYSTERY03b']
            present_regions   = ['RGN_AUDIO_MYSTERY03_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY03']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_RUINS_SIGNAL_SOURCE']
            progress_new      = [progress.names.PRO_ENABLE_ALL_OBELISKS]
            absent_regions    = ['RGN_OBELISK_CONSTRAINT', 'RGN_RUINS_SIGNAL_PINPOINT']
            present_regions   = ['RGN_RUINS_SIGNAL_ICON']

    class INSIDE_OBELISK03_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # En route to target.
            messages_new      = ['MSG_RUINSe', 'MSG_RUINSf', 'MSG_LANDMARKS01']
            not_done_missions = ['MIS_EXPLORE_ISLAND02']
            progress_new      = [progress.names.PRO_SHOW_LANDMARKS01]
            
            # Immediately upon target arrival.
            target_sounds     = ['SND_AUDIO_MYSTERY03']
            done_missions     = ['MIS_AUDIO_MYSTERY03a']
            absent_regions    = ['RGN_AUDIO_MYSTERY03_ZONE']
            present_regions   = ['RGN_AUDIO_MYSTERY03_PINPOINT', 'RGN_LANDMARK_N_SUMMIT', 'RGN_LANDMARK_S_SUMMIT', 'RGN_LANDMARK_SW_PENINSULA', 'RGN_LANDMARK01', 'RGN_LANDMARK02']

    class AT_OBELISK03_PINPOINT(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN02_SUB02']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_MYSTERY03b', 'MIS_AUDIO_MYSTERY03']
            absent_regions    = ['RGN_AUDIO_MYSTERY03_PINPOINT', 'RGN_NW_CONSTRAINT']
            present_regions   = ['RGN_AUDIO_MYSTERY03_ICON']
            progress_new      = [progress.names.PRO_ENABLE_NW_REGION]

    class TOWARD_OBELISK04_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # En route to target.
            messages_new      = ['MSG_OBELISK03a', 'MSG_OBELISK03b']

    class TOWARD_OBELISK04_03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Passed into audio trigger en route to target.
            not_done_missions = ['MIS_AUDIO_MYSTERY04', 'MIS_AUDIO_MYSTERY04a', 'MIS_AUDIO_MYSTERY04b']
            present_regions   = ['RGN_AUDIO_MYSTERY04_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY04']

    class INSIDE_OBELISK04_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_AUDIO_MYSTERY04']
            done_missions     = ['MIS_AUDIO_MYSTERY04a']
            absent_regions    = ['RGN_AUDIO_MYSTERY04_ZONE']
            present_regions   = ['RGN_AUDIO_MYSTERY04_PINPOINT']

    class AT_OBELISK04_PINPOINT(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN02_SUB03']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_MYSTERY04b', 'MIS_AUDIO_MYSTERY04']
            absent_regions    = ['RGN_AUDIO_MYSTERY04_PINPOINT']
            present_regions   = ['RGN_AUDIO_MYSTERY04_ICON']

    class TOWARD_CODED_LOC01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # En route to target.
            messages_new      = ['MSG_OBELISK04a', 'MSG_OBELISK04b', 'MSG_OBELISK04c']
            done_missions     = ['MIS_EXPLORE_ISLAND02']
            not_done_missions = ['MIS_2_MORE_OBELISKS', 'MIS_CODED_LOC']
            present_regions   = ['RGN_CODED_LOC_PINPOINT', 'RGN_AUDIO_MYSTERY05_ESTIMATE', 'RGN_AUDIO_MYSTERY06_ESTIMATE']

    class AT_CODED_LOC(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_MANMADE006']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_CODED_LOC']
            absent_regions    = ['RGN_CODED_LOC_PINPOINT']
            present_regions   = ['RGN_CODED_LOC_ICON']

    class TOWARD_TURING_ROVER_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # En route to target.
            messages_new      = ['MSG_CODED_LOCa']

    class TOWARD_TURING_ROVER_02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # En route to target.
            messages_new      = ['MSG_CODED_LOCb']
            not_done_missions = ['MIS_CODED_LOC_PASSWORD']
            messages_unlock   = ['MSG_ENCRYPTION02']

            @classmethod
            def password_to_unlock_message(cls, message, test, gamestate):
                test.assertEqual(message['msg_type'], 'MSG_ENCRYPTION02')

                species_id = str(species_module.get_id_from_key('SPC_MANMADE006'))
                species_name = gamestate['user']['species'][species_id]['name']
                # The password to the message is the name of the GPS unit, which should now be
                # available in the species catalog.  It's the last word in the species name with
                # all caps and digits.
                password = re.search(r'.* ([A-Z0-9]+)$', species_name).group(1)
                # The keycode should also be in the species description.
                test.assertTrue(password in gamestate['user']['species'][species_id]['description'])
                return password

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_CODED_LOC_PASSWORD']

    class TOWARD_TURING_ROVER_03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_CODED_LOCc_v2', 'MSG_RICHARD01a', 'MSG_RICHARD01c']
            # To exercise the default forwarding behavior, forward this message to TURING
            # and expect to see a message (MSG_NO_FORWARDa) from Kryptex saying not to do that.
            messages_forward  = [('MSG_ENCRYPTION02', 'TURING')]

    class TOWARD_TURING_ROVER_04(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_SECURITY', 'MSG_ENKI02a', 'MSG_NO_FORWARDa']
            not_done_missions = ['MIS_SEND_TO_ENKI']
            progress_new      = [progress.names.PRO_ENABLE_FWD_TO_EXOLEAKS]
            messages_forward  = [('MSG_ENCRYPTION02', 'ENKI')]

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_SEND_TO_ENKI']
            
    class TOWARD_TURING_ROVER_05(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_ENKI02b']

    class AT_TURING_ROVER(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_ENKI02d']
            not_done_missions = ['MIS_FIND_TURING_ROVER']
            id_species        = ['SPC_MANMADE007']

        class LEAVE(GameTestBeat.Move):
            messages_unlock   = ['MSG_ENKI02d']

            @classmethod
            def password_to_unlock_message(cls, message, test, gamestate):
                test.assertEqual(message['msg_type'], 'MSG_ENKI02d')

                species_id = str(species_module.get_id_from_key('SPC_MANMADE007'))
                species_name = gamestate['user']['species'][species_id]['name']
                # The password to the message is the name of Turing's rover, which should now be
                # available in the species catalog.  It's the last word in the species name with
                # all caps and digits.
                password = re.search(r'.* ([A-Z0-9]+)$', species_name).group(1)
                # The keycode should also be in the species description.
                test.assertTrue(password in gamestate['user']['species'][species_id]['description'])
                return password

    class TOWARD_OBELISK05_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_BACKa_v1']
            done_missions     = ['MIS_FIND_TURING_ROVER']

    class TOWARD_OBELISK05_02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_BACKb']
            messages_unlock   = ['MSG_BACKb']

            @classmethod
            def password_to_unlock_message(cls, message, test, gamestate):
                test.assertEqual(message['msg_type'], 'MSG_BACKb')

                # The password to the message is embedded as a data field in the locked body text.
                body_url = str(message['urls']['message_content'])
                response = test.json_get(body_url)
                password = re.search(r'data-key=\"([A-Z0-9]+)\"', response['content_html']).group(1)
                return password

        class LEAVE(GameTestBeat.Move):
            not_done_missions = ['MIS_MONUMENT_PLAYBACK', 'MIS_MONUMENT_PLAYBACKa', 'MIS_MONUMENT_PLAYBACKb']

    class TOWARD_OBELISK05_03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Audio trigger plus message MSG_BACKc from MessageSequence.
            not_done_missions = ['MIS_AUDIO_MYSTERY05', 'MIS_AUDIO_MYSTERY05a', 'MIS_AUDIO_MYSTERY05b']
            present_regions   = ['RGN_AUDIO_MYSTERY05_ZONE']
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY05', 'MSG_BACKc']
            # Note: We're testing an atypical sequence here: Tagging the obelisk before we enter the zone.
            # This should retroactively attach the obelisk's sound to the tagged target and trigger the
            # completion of MIS_AUDIO_MYSTERY05.
            id_species        = ['SPC_UNKNOWN_ORIGIN02_SUB04']

        class LEAVE(GameTestBeat.Move):
            target_sounds     = ['SND_AUDIO_MYSTERY05']  # Note the comments above.
            done_missions     = ['MIS_AUDIO_MYSTERY05a', 'MIS_AUDIO_MYSTERY05b', 'MIS_AUDIO_MYSTERY05', 'MIS_2_MORE_OBELISKS']
            not_done_missions = ['MIS_1_MORE_OBELISK']
            absent_regions    = ['RGN_AUDIO_MYSTERY05_ZONE', 'RGN_AUDIO_MYSTERY05_ESTIMATE']
            present_regions   = ['RGN_AUDIO_MYSTERY05_ICON']

    class IN_OBELISK05_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_OBELISK05a', 'MSG_OBELISK05b', 'MSG_OBELISK05c', 'MSG_OBELISK05d', 'MSG_OBELISK05e', 'MSG_OBELISK05f']

    class TOWARD_OBELISK06_03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            pass

    class IN_OBELISK06_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_AUDIO_MYSTERY06']
            done_missions     = ['MIS_AUDIO_MYSTERY06a']
            absent_regions    = ['RGN_AUDIO_MYSTERY06_ZONE']
            present_regions   = ['RGN_AUDIO_MYSTERY06_PINPOINT']

    class AT_OBELISK06_PINPOINT(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_UNKNOWN_ORIGIN02_SUB05']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_MYSTERY06b', 'MIS_AUDIO_MYSTERY06', 'MIS_1_MORE_OBELISK', 'MIS_MONUMENT_PLAYBACKa']
            absent_regions    = ['RGN_AUDIO_MYSTERY06_PINPOINT', 'RGN_AUDIO_MYSTERY06_ESTIMATE']
            present_regions   = ['RGN_AUDIO_MYSTERY06_ICON', 'RGN_EM_SOURCE_PLAYBACK_ZONE']

    class TOWARD_CENTRAL_MONUMENT_PLAYBACK01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_OBELISK06a', 'MSG_OBELISK06b']

    class TOWARD_CENTRAL_MONUMENT_PLAYBACK02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_unlock   = ['MSG_OBELISK06b']

            @classmethod
            def password_to_unlock_message(cls, message, test, gamestate):
                test.assertEqual(message['msg_type'], 'MSG_OBELISK06b')

                # The password to the message is embedded as a data field in the locked body text.
                body_url = str(message['urls']['message_content'])
                response = test.json_get(body_url)
                password = re.search(r'data-key=\"([A-Z0-9]+)\"', response['content_html']).group(1)
                return password

    class TOWARD_CENTRAL_MONUMENT_PLAYBACK03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_OBELISK06d', 'MSG_MISSION04a']

    class AT_CENTRAL_MONUMENT_PLAYBACK(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_MONUMENT_PLAYBACK']
            messages_new      = ['MSG_LASTTHINGa']
            done_missions     = ['MIS_MONUMENT_PLAYBACK', 'MIS_MONUMENT_PLAYBACKb']
            absent_regions    = ['RGN_EM_SOURCE_PLAYBACK_ZONE']

    class TOWARD_MISSING_ROVER01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_MISSION04b', 'MSG_MISSION04c', 'MSG_LASTTHINGb']
            not_done_missions = ['MIS_FIND_LOST_ROVER']
            present_regions   = ['RGN_MISSING_ROVER_ICON']

    class TOWARD_MISSING_ROVER02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # MessageSequence
            messages_new      = ['MSG_LASTTHINGc']

    class TOWARD_MISSING_ROVER03(GameTestBeat):
        # The next target will be inside of the trigger zone.  Create it, plus one more, so that we can tests
        # that extra targets are properly neutered when our rover goes missing.
        CREATE_NEXT_TARGETS = 2

        class ARRIVED(GameTestBeat.Move):
            # Required so that this GameTestBeat is registered as having been visited.
            pass

    class AT_MISSING_ROVER(GameTestBeat):
        class CREATED(GameTestBeat.Move):
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Verify special target metadata was set and a MOD chip was issued for this target.
                test.assertEqual(target_struct['metadata'], {'TGT_S1_FALL_OFF_CLIFFS': ''})
                target_chips = test.chips_for_path(['user', 'rovers', '*', 'targets', target_struct['target_id']], struct=chips_struct)
                test.assertEqual(len(target_chips), 2)
                test.assertEqual(target_chips[0]['action'], chips.ADD)
                test.assertEqual(target_chips[1]['action'], chips.MOD)
                test.assertEqual(target_chips[1]['value']['metadata'], {'TGT_S1_FALL_OFF_CLIFFS': ''})

        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_LASTTHINGd']
            done_missions     = ['MIS_FIND_LOST_ROVER']
            absent_regions    = ['RGN_MISSING_ROVER_ICON']
            not_done_missions = ['MIS_UNLOCK_LAST_DOC']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # At this point, there should be no active rovers.
                rendered_rover = test.get_rover_for_target_id(target_struct['target_id'], gamestate)
                active_rover = test.get_active_rover(gamestate)
                assert active_rover is None

                # Verify that the MOD chip was issued for the old rover.
                rover_chips = test.chips_for_path(['user', 'rovers', '*'], struct=chips_struct)
                test.assertEqual(len(rover_chips), 1)
                test.assertEqual(rover_chips[0]['action'], chips.MOD)
                test.assertEqual(rover_chips[0]['path'], ['user', 'rovers', rendered_rover['rover_id']])
                test.assertEqual(rover_chips[0]['value']['active'], 0)

                # The first rover should still have the original asset as the last photo it takes is still
                # from its perspective (a shadow)
                test.assert_assets_equal(target_struct['_render_result'], ["LANDER01", "ROVER_DISASSEMBLED", "ROVER_SHADOW"])

    class AFTER_MISSING_ROVER01(GameTestBeat):
        TARGET_WILL_BE_NEUTERED = True

        class CREATED(GameTestBeat.Move):
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Verify that the target that will be neutered and deleted is currently in the gamestate.
                neutered_target_id = target_struct['target_id']
                test.assertTrue(test.get_target_from_gamestate(neutered_target_id, gamestate=gamestate) != None)

        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_LASTTHINGe', 'MSG_LASTTHINGf']

            # Though the target is deleted from the gamestate, the Route/Story still move us to this Point
            # in the Route, where we can verify the target has been removed from the gamestate and not
            # rendered.
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # The neutered target should have been deleted when the rover got stuck.
                neutered_target_id = target_struct['target_id']
                test.assertTrue(test.get_target_from_gamestate(neutered_target_id, gamestate=gamestate) == None)

                # Even though the initial target was neutered, it should have been replaced by a new
                # target out in the ocean.  Make sure that target was properly created by verifying
                # its prerendered image files and the attached sound file.
                rendered_target = test.get_most_recent_processed_target_from_gamestate(gamestate=gamestate)
                test.assertEqual(set(rendered_target['sounds'].keys()), set(['SND_DISTRESS01']))
                test.assertEqual(rendered_target['images']['PHOTO'], scene.DISTRESS01.photo)
                test.assertEqual(rendered_target['classified'], 1)

                # Check for the correct metadata in the second-to-last target for the swimming rover.
                swimming_rover = test.get_rover_for_target_id(rendered_target['target_id'])
                pre_swim_target = sorted(swimming_rover['targets'].values(), key=lambda m: m['arrival_time'])[-2]
                test.assertEqual(pre_swim_target['metadata'], {'TGT_S1_FALL_OFF_CLIFFS': ''})

                # There should be a MOD chip for the special distress scene target images/processed/classified flags.
                target_chips = test.chips_for_path(['user', 'rovers', '*', 'targets', rendered_target['target_id']], struct=chips_struct)
                test.assertEqual(len(target_chips), 1)
                target_distress = target_chips[0]
                test.assertEqual(target_distress['action'], chips.MOD)
                test.assertEqual(target_distress['value']['processed'], 1)
                test.assertEqual(target_distress['value']['classified'], 1)
                test.assertEqual(target_distress['value']['images']['PHOTO'], scene.DISTRESS01.photo)

                # To schedule the final photo from island 2, we create an inactive rover outside of the map bounds.
                # So there should also be a more recent unprocessed target.
                last_target = test.get_most_recent_target_from_gamestate(gamestate=gamestate)
                test.assertTrue(rendered_target != last_target)
                # Make sure we now have a 3rd rover with exactly 1 target.
                test.assertEqual(len(gamestate['user']['rovers']), 3)
                latest_rover = test.get_rover_for_target_id(last_target['target_id'])
                test.assertEqual(len(latest_rover['targets']), 1)
                # Assert the new, inactive rover has the expected rover key and chassis
                test.assertEqual(latest_rover['rover_key'], rover_keys.RVR_S1_NEW_ISLAND)
                test.assertEqual(latest_rover['rover_chassis'], rover_chassis.RVR_CHASSIS_SRK)

                # An ADD chip should have been issued for this new, inactive rover.
                rover_chips = test.chips_for_path(['user', 'rovers', '*'], struct=chips_struct)
                test.assertEqual(len(rover_chips), 1)
                test.assertEqual(rover_chips[0]['action'], chips.ADD)
                test.assertEqual(rover_chips[0]['path'], ['user', 'rovers', latest_rover['rover_id']])
                test.assertEqual(rover_chips[0]['value']['active'], 0)

    class AFTER_MISSING_ROVER02(GameTestBeat):
        # 23 hours later, we get the last image from our rover, now on island 2.
        BEAT_ARRIVAL_DELTA = 90000
        RENDER_ADHOC_TARGET = True
        # The real renderer would mark this image as classified.
        TARGET_MARK_CLASSIFIED = True

        class ARRIVED(GameTestBeat.Move):
            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # Even though we player didn't have an active rover, a special target should have
                # been created automatically -- outside the map bounds with an image from the new island.
                # Make sure that target was properly created by verifying its metadata keys.
                rendered_target = test.get_most_recent_processed_target_from_gamestate(gamestate=gamestate)
                test.assertEqual(set(rendered_target['metadata'].keys()), set(['TGT_S1_STRANDED_ROVER']))
                test.assertEqual(rendered_target['classified'], 1)

    story_case.StoryTestCase.after_beat_run_beat(AFTER_MISSING_ROVER01, AFTER_MISSING_ROVER02)

    class AFTER_MISSING_ROVER03(GameTestBeat):
        # After we arrive at the above beat, we get a couple more messages.  We now have what we
        # need to unlock MSG_LASTTHINGa.
        BEAT_ARRIVAL_DELTA = 600
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_LASTTHINGg', 'MSG_LASTTHINGh']
            messages_unlock   = ['MSG_LASTTHINGa']

            @classmethod
            def password_to_unlock_message(cls, message, test, gamestate):
                # TODO: Eventually, this password will be in an image rather than the message body, so we'll
                # need to find it in a different way.
                test.assertEqual(message['msg_type'], 'MSG_LASTTHINGa')

                # The password to the message is in the body of message MSG_LASTTHINGg
                all_messages = gamestate['user']['messages']
                found = [m for m in all_messages.itervalues() if m['msg_type'] == 'MSG_LASTTHINGg']
                assert(len(found) == 1)
                body_url = found[0]['urls']['message_content']
                response = test.json_get(body_url)

                # The password to MSG_LASTTHINGa should appear in a comment in MSG_LASTTHINGg as all caps and digits.
                password = re.search(r'Rover ID: ([A-Z0-9]+)', response['content_html']).group(1)
                return password
            
        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_UNLOCK_LAST_DOC']

    story_case.StoryTestCase.after_beat_run_beat(AFTER_MISSING_ROVER02, AFTER_MISSING_ROVER03)

    class AFTER_MISSING_ROVER04(GameTestBeat):
        BEAT_ARRIVAL_DELTA = 691200
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT65535']
            messages_new      = ['MSG_RICHARD02b', 'MSG_END', 'MSG_S1_CREDITS', 'MSG_AUDIO_TEASE']

            @classmethod
            def assertions(cls, test, target_struct, gamestate, chips_struct):
                # At this point, we should now have a new rover.
                active_rover = test.get_active_rover(gamestate)
                assert active_rover is not None

                # Assert the new rover has the expected rover key and chassis
                test.assertEqual(active_rover['rover_key'], rover_keys.RVR_S1_FINAL)
                test.assertEqual(active_rover['rover_chassis'], rover_chassis.RVR_CHASSIS_SRK)

                # Verify that the ADD chip was issued for the new rover.
                rover_chips = test.chips_for_path(['user', 'rovers', '*'], struct=chips_struct)
                test.assertEqual(len(rover_chips), 1)
                test.assertEqual(rover_chips[0]['action'], chips.ADD)
                test.assertEqual(rover_chips[0]['path'], ['user', 'rovers', active_rover['rover_id']])
                test.assertEqual(rover_chips[0]['value']['active'], 1)

                # Available invites should have been incremented.
                test.assertEqual(gamestate['user']['invites_left'], 15)

    story_case.StoryTestCase.after_beat_run_beat(AFTER_MISSING_ROVER03, AFTER_MISSING_ROVER04)

    class SCI_FIND_COMMON_FIRST_TAGS(GameTestBeat):
        # Tag the first instance of the 2 species we seek for MIS_SCI_FIND_COMMON.
        class ARRIVED(GameTestBeat.Move):
            # Note that SPC_ANIMAL65535 is the aquatic in a previous image, but since that image
            # was created in an adhoc beat, this trigger for MSG_JANE_SWIMMING_ROVER is easier to test here. 
            id_species        = ['SPC_PLANT021_SUB04', 'SPC_PLANT024_SUB04', 'SPC_ANIMAL65535']
            messages_new      = ['MSG_JANE_S1_ISLAND2']

    # Note that we used to require 3 tags. Now we only need 2. Do nothing here.
    #class SCI_FIND_COMMON_SECOND_TAGS(GameTestBeat):
        
    class SCI_FIND_COMMONb(GameTestBeat):
        # Tag the species needed to complete submission MIS_SCI_FIND_COMMONb. (Deliberately out of order)
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT024_SUB04']
            messages_new      = ['MSG_JANE_AQUATIC_ANIMAL']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_SCI_FIND_COMMONb']
            messages_new      = ['MSG_SCI_PHOTOSYNTHESISf', 'MSG_SCI_PHOTOSYNTHESISg']

    class SCI_FIND_COMMONa(GameTestBeat):
        # Tag the species needed to complete submission MIS_SCI_FIND_COMMONa. (Deliberately out of order)
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT021_SUB04']
            
        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_SCI_FIND_COMMONa', 'MIS_SCI_FIND_COMMONc', 'MIS_SCI_FIND_COMMON']
            messages_new      = ['MSG_SCI_PHOTOSYNTHESISd', 'MSG_SCI_PHOTOSYNTHESISe', 'MSG_SCI_PHOTOSYNTHESISh']

    class ID_15_SPECIES(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT012']

    class ID_15_SPECIES_DONE(GameTestBeat):
        # Within the maximum species delay all the species data is fully available and the mission should be done.
        BEAT_ARRIVAL_DELTA = utils.in_seconds(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)

        class ARRIVED(GameTestBeat.Move):
            done_missions     = ['MIS_SPECIES_FIND_15']

    story_case.StoryTestCase.after_beat_run_beat(ID_15_SPECIES, ID_15_SPECIES_DONE)

    class ID_GORDY_TREE_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT032']
            messages_new      = ['MSG_FIND_15']

    class ID_GORDY_TREE_02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT032']
            messages_new      = ['MSG_SCI_CELLULARa']
            not_done_missions = ['MIS_SCI_CELLULARa']

    class ID_GORDY_TREE_03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT032']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_SCI_CELLULARa']
            messages_new      = ['MSG_SCI_CELLULARc', 'MSG_SCI_CELLULARb']
            not_done_missions = ['MIS_SCI_LIFECYCLE']

    class ID_GORDY_TREE_YOUNG(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT032_SUB01']

    class ID_GORDY_TREE_DEAD(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT032_SUB02']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_SCI_LIFECYCLE']
            
    class ID_BRISTLETONGUE_VARIANT(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag the bristletongue variant to trigger completion of MIS_SCI_VARIATION.
            id_species        = ['SPC_ANIMAL006']
            messages_new      = ['MSG_SCI_CELLULARd']

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_SCI_VARIATION']
            absent_regions    = ['RGN_SCI_VARIATION_PINPOINT']

    class ID_THIRD_CNIDERIA(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag a second and third species with cnideria to trigger MSG_SCI_VARIATIONc.
            id_species        = ['SPC_PLANT033', 'SPC_PLANT034']
            messages_new      = ['MSG_SCI_VARIATIONb']

    class ID_STARSPORE_OPEN_CLOSED_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag the starspore in both the open and closed variations.
            id_species        = ['SPC_PLANT028', 'SPC_PLANT028_SUB03']
            messages_new      = ['MSG_SCI_VARIATIONc']

    class ID_STARSPORE_OPEN_CLOSED_02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag the starspore again in both the open and closed variations.
            id_species        = ['SPC_PLANT028', 'SPC_PLANT028_SUB03']
            not_done_missions = ['MIS_SCI_FLOWERS']
            messages_new      = ['MSG_SCI_FLOWERSa']

    class ID_BIOLUMINESCENCE_DAY(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tagging the bioluminescent species in the daytime should not trigger the mission.
            id_species        = ['SPC_PLANT015', 'SPC_PLANT022', 'SPC_PLANT031']
            done_missions     = ['MIS_SCI_FLOWERS']
            messages_new      = ['MSG_SCI_FLOWERSb']

    class ID_BIOLUMINESCENCE_NIGHT_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag all 3 bioluminescent species at night.
            id_species        = ['SPC_PLANT015_SUB05', 'SPC_PLANT022_SUB05', 'SPC_PLANT031_SUB05']

    class ID_BIOLUMINESCENCE_NIGHT_02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag all 3 bioluminescent species again at night.
            id_species        = ['SPC_PLANT015_SUB05', 'SPC_PLANT022_SUB05', 'SPC_PLANT031_SUB05']
            not_done_missions = ['MIS_SCI_BIOLUMINESCENCE']
            messages_new      = ['MSG_SCI_BIOLUMINESCENCEa']
            
    class ID_SAIL_FLYER_01(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tag the sail flyer to kick off the flight mission.
            id_species        = ['SPC_ANIMAL004']
            done_missions     = ['MIS_SCI_BIOLUMINESCENCE']
            messages_new      = ['MSG_SCI_BIOLUMINESCENCEb']

    class ID_SAIL_FLYER_02(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_ANIMAL004']
            not_done_missions = ['MIS_SCI_FLIGHT']
            messages_new      = ['MSG_SCI_FLIGHTa']
            present_regions   = ['RGN_SCI_FLIGHT01', 'RGN_SCI_FLIGHT02', 'RGN_SCI_FLIGHT03']

    class ID_SAIL_FLYER_03(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_ANIMAL004']

    class OUTSIDE_AUDIO_MYSTERY07_TRIGGER(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            done_missions     = ['MIS_SCI_FLIGHT']
            messages_new      = ['MSG_SCI_FLIGHTb']
            absent_regions    = ['RGN_SCI_FLIGHT01', 'RGN_SCI_FLIGHT02', 'RGN_SCI_FLIGHT03']

    class INSIDE_AUDIO_MYSTERY07_TRIGGER(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_ROVERAUDIO_MYSTERY07']
            not_done_missions = ['MIS_AUDIO_MYSTERY07', 'MIS_AUDIO_MYSTERY07a', 'MIS_AUDIO_MYSTERY07b']
            present_regions   = ['RGN_AUDIO_MYSTERY07_ZONE']

    class OUTSIDE_AUDIO_MYSTERY07_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            # Tagging the vampire gourd should NOT complete MIS_AUDIO_MYSTERY07b until MIS_AUDIO_MYSTERY07a is done.
            id_species        = ['SPC_PLANT014_SUB04']

    class INSIDE_AUDIO_MYSTERY07_ZONE(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            target_sounds     = ['SND_AUDIO_MYSTERY07']
            done_missions     = ['MIS_AUDIO_MYSTERY07a']
            absent_regions    = ['RGN_AUDIO_MYSTERY07_ZONE']
            present_regions   = ['RGN_AUDIO_MYSTERY07_PINPOINT01', 'RGN_AUDIO_MYSTERY07_PINPOINT02', 'RGN_AUDIO_MYSTERY07_PINPOINT03',
                                 'RGN_AUDIO_MYSTERY07_PINPOINT04', 'RGN_AUDIO_MYSTERY07_PINPOINT05', 'RGN_AUDIO_MYSTERY07_PINPOINT06']

    class AT_AUDIO_MYSTERY07(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            id_species        = ['SPC_PLANT014_SUB04']
            messages_new      = ['MSG_SCI_AUDIO_MYSTERY07b'] # Jane: What's with all the pinpoints?!

        class LEAVE(GameTestBeat.Move):
            done_missions     = ['MIS_AUDIO_MYSTERY07', 'MIS_AUDIO_MYSTERY07b']
            absent_regions    = ['RGN_AUDIO_MYSTERY07_PINPOINT01', 'RGN_AUDIO_MYSTERY07_PINPOINT02', 'RGN_AUDIO_MYSTERY07_PINPOINT03',
                                 'RGN_AUDIO_MYSTERY07_PINPOINT04', 'RGN_AUDIO_MYSTERY07_PINPOINT05', 'RGN_AUDIO_MYSTERY07_PINPOINT06']

    class THE_END(GameTestBeat):
        class ARRIVED(GameTestBeat.Move):
            messages_new      = ['MSG_SCI_AUDIO_MYSTERY07c']
