# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import collections
from front.models import chips

from front import Constants, target_image_types
from front.callbacks import target_callbacks
from front.models import target as target_module
from front.lib import utils, db
from front.data import scene

from front.tests import base
from front.tests.base import points, SIX_HOURS

TEN_HOURS = utils.in_seconds(hours=10)
ONE_HOUR = utils.in_seconds(hours=1)
S3_TEST_SCENE = scene.define_scene('3a7671e2-28a3-11e2-9f62-123140007c6e',
                                   scene_url='https://s3-us-west-1.amazonaws.com/images.us-west-1.extrasolar.com/photos/3a/76/')
S3_TEST_SCENE_BUCKET_FIRST = scene.define_scene('3a7671e2-28a3-11e2-9f62-123140007c6e',
                                    scene_url='https://images.us-west-1.extrasolar.com.s3.amazonaws.com/photos/3a/76/')

class TestTargeting(base.TestCase):
    def setUp(self):
        super(TestTargeting, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_create_and_view_target(self):
        # The first rover target should not be a picture and should be marked as not user_created and then
        # the initial target photos should also not be user_created.
        user = self.get_logged_in_user()
        first = user.rovers.active()[0].targets.first()
        last = user.rovers.active()[0].targets.last()
        self.assertEqual(first.user_created, 0)
        self.assertEqual(last.user_created, 0)

        # Pull the active rover_id and create target URL from the gamestate.
        gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        assert rover is not None
        create_target_url = str(rover['urls']['target'])

        result = self.create_target(create_target_url=create_target_url, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['viewed_at'], None)
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['viewed_at'], None)

        # The first user created target should have user_created set to 1
        user = self.get_logged_in_user()
        target_model = user.rovers.find_target_by_id(target['target_id'])
        self.assertEqual(target_model.user_created, 1)

        result = self.json_post(str(chip['value']['urls']['mark_viewed']))
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(chip['action'], chips.MOD)
        self.assertTrue(chip['value']['viewed_at'] > 0)
        target = self.get_most_recent_target_from_gamestate()
        self.assertTrue(target['viewed_at'] > 0)

    def test_create_with_metadata(self):
        metadata = {'TGT_TEST_1': '', 'TGT_TEST_2': 'test_value'}
        result = self.create_target(metadata=metadata, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['viewed_at'], None)
        self.assertEqual(chip['value']['metadata'], metadata)
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['viewed_at'], None)
        self.assertEqual(target['metadata'], metadata)

    def test_target_abort(self):
        result = self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        first_target_id = chip['value']['target_id']
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['path'][-1], first_target_id)
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['target_id'], first_target_id)

        # Cannot abort a target already being moved towards.
        self.expect_log('front.resource.target_node', 'Refusing to abort target')
        result = self.json_post(str(chip['value']['urls']['abort_target']), status=400)
        self.assertTrue("Cannot abort this target" in result['errors'][0])

        # Create the second target using a capability which has limited uses. When it is aborted
        # verify that the number of uses decreased, freeing up another use.
        CAPABILITY_KEY = 'CAP_S1_CAMERA_PANORAMA'
        user = self.get_logged_in_user()
        panorama_cap = user.capabilities[CAPABILITY_KEY]
        self.assertEqual(len(panorama_cap.rover_features), 1)
        metadata_key = panorama_cap.rover_features[0]
        metadata = {metadata_key: ''}
        # Snapshot the number of uses.
        capability = self.get_gamestate()['user']['capabilities'][CAPABILITY_KEY]
        uses_before = capability['uses']
        # But a target that has not been moved towards can be aborted.
        result = self.create_target(arrival_delta=SIX_HOURS * 2, metadata=metadata, **points.SECOND_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        second_target_id = chip['value']['target_id']
        self.assertNotEqual(first_target_id, second_target_id)
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['path'][-1], second_target_id)
        gamestate = self.get_gamestate()
        target = self.get_most_recent_target_from_gamestate(gamestate=gamestate)
        self.assertEqual(target['target_id'], second_target_id)
        # Check that the capability was used.
        capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['uses'], uses_before + 1)

        # Advance to just before the abort deadline.
        self.advance_now(seconds=SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS - 1)

        # Aborting the second target should result in a DEL chip and removal of that target from the gamestate.
        result = self.json_post(str(chip['value']['urls']['abort_target']))
        all_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(len(all_chips), 1)
        chip = all_chips[0]
        self.assertEqual(chip['action'], chips.DELETE)
        self.assertEqual(chip['path'][-1], second_target_id)
        gamestate = self.get_gamestate()
        target = self.get_most_recent_target_from_gamestate(gamestate=gamestate)
        self.assertEqual(target['target_id'], first_target_id)
        # Check that the capability was restored to its uses original number.
        all_chips = self.chips_for_path(['user', 'capabilities', CAPABILITY_KEY], result)
        self.assertEqual(len(all_chips), 1)
        chip = all_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['uses'], uses_before)
        capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['uses'], uses_before)

        # Arrive at the second target.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS + 1)

        # Recreating the second target and then advancing time just after the abort deadline should fail.
        result = self.create_target(arrival_delta=SIX_HOURS, **points.SECOND_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.advance_now(seconds=SIX_HOURS  - Constants.TARGET_DATA_LEEWAY_SECONDS + 1)
        self.expect_log('front.resource.target_node', 'Refusing to abort target')
        result = self.json_post(str(chip['value']['urls']['abort_target']), status=400)
        self.assertTrue("Cannot abort this target" in result['errors'][0])

    def test_target_abort_multiple_targets(self):
        # Enable the capabilities to allow 3 and 4 moves at a time.
        self.enable_capabilities_on_active_rover(['CAP_S1_ROVER_3_MOVES', 'CAP_S1_ROVER_4_MOVES'])

        # Create three targets in a row, keeping track of each targets target_id.
        result = self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        first_target_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)['target_id']
        result = self.create_target(arrival_delta=2*SIX_HOURS, **points.SECOND_MOVE)
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        second_target_id = chip['target_id']
        # Grab the abort_target URL for the second target.
        abort_target_url = str(chip['urls']['abort_target'])
        result = self.create_target(arrival_delta=3*SIX_HOURS, **points.THIRD_MOVE)
        third_target_id = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)['target_id']

        # Advance a bit past the target creations chips.
        self.advance_now(minutes=10)

        # Aborting the second target should result in a DEL chip for that target and the third target.
        result = self.json_post(abort_target_url)
        all_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(len(all_chips), 2)
        self.assertEqual(all_chips[0]['action'], chips.DELETE)
        self.assertEqual(all_chips[0]['path'][-1], third_target_id)
        self.assertEqual(all_chips[1]['action'], chips.DELETE)
        self.assertEqual(all_chips[1]['path'][-1], second_target_id)
        # And both targets should be removed from the gamestate, though the first target should remain.
        gamestate = self.get_gamestate()
        self.assertIsNone(self.get_target_from_gamestate(second_target_id, gamestate=gamestate))
        self.assertIsNone(self.get_target_from_gamestate(third_target_id, gamestate=gamestate))
        self.assertIsNotNone(self.get_target_from_gamestate(first_target_id, gamestate=gamestate))

    def test_download_image(self):
        # Try the download the default testing scene, which is served locally.
        self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        self.render_next_target(assert_only_one=True)
        self.advance_now(seconds=SIX_HOURS)
        target = self.get_most_recent_target_from_gamestate()
        image_url = target['images'][target_image_types.WALLPAPER]
        self.assertIsNotNone(image_url)
        # We should redirect back to the scene URL as this is not an S3 URL.
        response = self.app.get(str(target['urls']['download_image'] + '/' + target_image_types.WALLPAPER), status=303)
        self.assertEqual(image_url, response.location)

        # Now attempt to download an image rendered to look like a real image URL.
        self.create_target(arrival_delta=SIX_HOURS, **points.SECOND_MOVE)
        self.render_next_target(assert_only_one=True, render_scene=S3_TEST_SCENE)
        self.advance_now(seconds=SIX_HOURS)
        target = self.get_most_recent_target_from_gamestate()
        image_url = target['images'][target_image_types.WALLPAPER]
        self.assertIsNotNone(image_url)
        # We should redirect back to the signed S3 URL. The start of the redirected URL should still be the
        # same but there should be additonal query parameters now.
        response = self.app.get(str(target['urls']['download_image'] + '/' + target_image_types.WALLPAPER), status=303)
        self.assertTrue(response.location.startswith(image_url))
        self.assertTrue('attachment' in response.location)
        self.assertTrue('Signature' in response.location)

        # Finally, let's attempt to download an image rendered from a traditional looking S3 URL,
        # with the bucket name as the first part of the hostname. This breaks https if the bucket contains
        # .'s like ours do. This should log a warning and redirect to the image URL unchanged.
        self.create_target(arrival_delta=SIX_HOURS, **points.THIRD_MOVE)
        self.render_next_target(assert_only_one=True, render_scene=S3_TEST_SCENE_BUCKET_FIRST)
        self.advance_now(seconds=SIX_HOURS)
        target = self.get_most_recent_target_from_gamestate()
        image_url = target['images'][target_image_types.WALLPAPER]
        self.assertIsNotNone(image_url)
        # A warning log is written.
        self.expect_log('front.resource.target_node', 'Unable to generate signed download URL from target image')
        # We should redirect back to the original image URL.
        response = self.app.get(str(target['urls']['download_image'] + '/' + target_image_types.WALLPAPER), status=303)
        self.assertEqual(image_url, response.location)
        self.assertTrue('attachment' not in response.location)
        self.assertTrue('Signature' not in response.location)

    def test_rendered_data_hidden_until_arrival(self):
        result = self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        chip_value = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        self.assertEqual(chip_value['processed'], 0)
        self.assertEqual(chip_value['images'], {})

        # Render the target and verify the rendered data is still hidden in the gamestate.
        self.render_next_target(assert_only_one=True)
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['processed'], 0)
        self.assertEqual(target['images'], {})

        # Advance time to the arrival_time of the target and verify the rendered data is no available
        # in the gamestate.
        self.advance_now(seconds=SIX_HOURS)
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['processed'], 1)
        self.assertEqual(len(target['images']), 3)  # PHOTO, THUMB, and WALLPAPER.

    def test_bad_target(self):
        # None or null is an invalid lat value and should result in a 400 error.
        self.create_target(lat=None, lng=1, yaw=-1, status=400)

    def test_multiple_targets_and_en_route_event(self):
        # Map target name to each event seen.
        EVENTS_SEEN = collections.defaultdict(list)
        # The time the test was started in the user's epoch (and when the targets are all created)
        user = self.get_logged_in_user()
        created_epoch_now = user.epoch_now
        # Add a callback which appends each event we are interested in to the EVENTS_SEEN list for
        # that targets name (as defined by the TGT_TST_NAME metadata key value).
        class TARGET_TEST01_Callbacks(target_callbacks.BaseCallbacks):
            @classmethod
            def target_created(cls, ctx, user, target):
                # target_created should always fire 'now', when the targets are created
                self.assertEqual(user.epoch_now, created_epoch_now)
                target_name = target.metadata['TGT_TST_NAME']
                EVENTS_SEEN[target_name].append('target_created')

            @classmethod
            def target_en_route(cls, ctx, user, target):
                # target_en_route should fire at the targets start_time
                self.assertEqual(user.epoch_now, target.start_time)
                target_name = target.metadata['TGT_TST_NAME']
                EVENTS_SEEN[target_name].append('target_en_route')

            @classmethod
            def arrived_at_target(cls, ctx, user, target):
                # arrived_at_target should fire at the targets arrival_time
                self.assertEqual(user.epoch_now, target.arrival_time)
                target_name = target.metadata['TGT_TST_NAME']
                EVENTS_SEEN[target_name].append('arrived_at_target')
        self.inject_callback(target_callbacks, TARGET_TEST01_Callbacks)

        # Enable the capabilities to allow 3 and 4 moves at a time.
        self.enable_capabilities_on_active_rover(['CAP_S1_ROVER_3_MOVES', 'CAP_S1_ROVER_4_MOVES'])        

        # Create four targets in a row, each labeled with a unique metadata key.
        self.create_target(metadata={'TGT_TST_NAME': 'TG1'}, arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        self.create_target(metadata={'TGT_TST_NAME': 'TG2'}, arrival_delta=2*SIX_HOURS, **points.SECOND_MOVE)
        self.create_target(metadata={'TGT_TST_NAME': 'TG3'}, arrival_delta=3*SIX_HOURS, **points.THIRD_MOVE)
        # Move back to second move to avoid lander constraint for TUT01 mission.
        self.create_target(metadata={'TGT_TST_NAME': 'TG4'}, arrival_delta=4*SIX_HOURS, **points.SECOND_MOVE)

        # And now advance the game to the arrival time of the last target.
        self.advance_game(seconds=4*SIX_HOURS)

        # Check that each of the 4 targets fired all 3 expected events in the correct order.
        self.assertEqual(len(EVENTS_SEEN), 4)
        for target_name in sorted(EVENTS_SEEN.keys()):
            events = EVENTS_SEEN[target_name]
            # Assert that we saw all events only once and in the correct order.
            self.assertEqual(events, ['target_created', 'target_en_route', 'arrived_at_target'])

    def test_en_route_event_delayed_deferred(self):
        # Simulate the deferred system being down and then firing back up after the arrived at time for
        # a target which is getting the target_en_route sent via the arrived at target deferred. This will
        # log an error but still dispatch the event, even though the wallclock time is now ahead of arrival_time
        # for the target.

        # Enable the capabilities to allow 3 and 4 moves at a time.
        self.enable_capabilities_on_active_rover(['CAP_S1_ROVER_3_MOVES', 'CAP_S1_ROVER_4_MOVES'])

        # Create three targets in a row.
        self.create_target(metadata={'TGT_TST_NAME': 'TG1'}, arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        self.create_target(metadata={'TGT_TST_NAME': 'TG2'}, arrival_delta=2*SIX_HOURS, **points.SECOND_MOVE)

        # And advance the clock, as if the deferred system had been down for 12 hours and change.
        self.advance_now(seconds=2*SIX_HOURS + 1800)

        # Expect an error log message.
        self.expect_log('front.backend.deferred', 'Dispatching target_en_route event for already arrived target.*')

        # And now run the deferred actions, which will process the events in the deferred system which were
        # delayed by the system being down.
        self.run_deferred_actions()

    def test_multiple_target_times(self):
        # Create two targets in a row
        response = self.create_target(arrival_delta=TEN_HOURS, **points.FIRST_MOVE)
        chip1 = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)
        response = self.create_target(arrival_delta=2*TEN_HOURS, **points.SECOND_MOVE)
        chip2 = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)

        # Make sure that the second target's start_time is >= the first target's arrival_time.
        self.assertTrue(chip1['arrival_time'] <= chip2['start_time'])

    def test_invalid_first_move_mission_validation(self):
        # This test attempts to make an initial move that is not close enough to the lander
        # to satisfy TUT01a which is enforced on the server (and hopefully on the client)
        # and this should result in no target being created.

        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Mission reports target parameters invalid.*')

        before = len(self.get_targets_from_gamestate())
        result = self.create_target(arrival_delta=SIX_HOURS, status=400, **points.MOVE_TOO_SHORT)
        self.assertTrue("Error when creating target" in result['errors'][0])

        # Make sure no targets.
        after = len(self.get_targets_from_gamestate())
        self.assertEqual(after, before)

    def test_server_only_metadata_key_prefix(self):
        # Create a target with a dummy metadata key with the server only metadata key prefix at the start.
        TEST_KEY = target_module.Target.server_only_metadata_key_prefix + "TESTING"
        metadata = {TEST_KEY: ''}
        result = self.create_target(metadata=metadata, **points.FIRST_MOVE)
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'], result)
        # That key should be removed from the gamestate.
        target_id = chip['value']['target_id']
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['metadata'], {})
        target = self.get_most_recent_target_from_gamestate()
        self.assertEqual(target['metadata'], {})
        # The key should still be in the server side model object.
        user = self.get_logged_in_user()
        target = user.rovers.find_target_by_id(target_id)
        self.assertTrue(TEST_KEY in target.metadata)

    def test_min_arrival_time(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Target arrival_time .* too early, modifying')

        # Create a target arriving earlier than the constant (violates our min travel time constraints).
        response = self.create_target(arrival_delta=Constants.MIN_TARGET_SECONDS / 2, **points.FIRST_MOVE)
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)

        # Assert that the travel time of the target (time between start and arrival) is equal to
        # or greater than the minimum duration constant.
        self.assertTrue(chip['arrival_time'] == chip['start_time']+Constants.MIN_TARGET_SECONDS-Constants.TARGET_SECONDS_GRACE)

    def test_max_arrival_time(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Target arrival_time .* too late, modifying')

        # Create a target arriving later than the constant (violates our max travel time constraints).
        response = self.create_target(arrival_delta=Constants.MAX_TARGET_SECONDS + Constants.TARGET_SECONDS_GRACE + 100, **points.FIRST_MOVE)
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)

        # Assert that the travel time of the target (time between start and arrival) is equal to
        # or less than the max travel time constant.
        self.assertTrue(chip['arrival_time'] == chip['start_time']+Constants.MAX_TARGET_SECONDS+Constants.TARGET_SECONDS_GRACE)

    def test_max_distance(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Player exceeded travel limit.*')

        # Create the first known good target to satisfy the TUT01a requirements.
        self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)

        # Create a target known to be too far from the initial location.
        response = self.create_target(arrival_delta=SIX_HOURS*2, **points.MOVE_TOO_FAR)
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)

        # Make sure that the chips lat/lng are different than expected.
        self.assertNotEqual(chip['lat'], points.MOVE_TOO_FAR['lat'])
        self.assertNotEqual(chip['lng'], points.MOVE_TOO_FAR['lng'])

    def test_max_unarrived_at(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Player exceeded max unarrived at targets.*')

        before = len(self.get_targets_from_gamestate())
        # Create too many targets before they have been arrived at.
        self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        self.create_target(arrival_delta=2*SIX_HOURS, **points.SECOND_MOVE)
        result = self.create_target(arrival_delta=3*SIX_HOURS, status=400, **points.THIRD_MOVE)
        self.assertTrue("Error when creating target" in result['errors'][0])

        # Make sure only two targets were created.
        after = len(self.get_targets_from_gamestate())
        self.assertEqual(after, before + 2)

    def test_inside_region(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Target must be inside region.*')

        # Create the first known good target to satisfy the TUT01a requirements.
        self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)

        # Clear out the chips.
        self.advance_now(minutes=10)

        # Create a target known to be outside of the island region.
        before = len(self.get_targets_from_gamestate())
        response = self.create_target(arrival_delta=SIX_HOURS*2, status=400, **points.MOVE_OUTSIDE_ISLAND)
        self.assertTrue("Error when creating target" in response['errors'][0])
        # No target should have been created.
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)
        self.assertIsNone(chip)
        after = len(self.get_targets_from_gamestate())
        self.assertEqual(after, before)

    def test_outside_region(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Target must be outside region.*')

        # Create a target known to be inside the lander region.
        before = len(self.get_targets_from_gamestate())
        response = self.create_target(arrival_delta=SIX_HOURS, status=400, **points.MOVE_INSIDE_LANDER)
        self.assertTrue("Error when creating target" in response['errors'][0])
        # No target should have been created.
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], response)
        self.assertIsNone(chip)
        after = len(self.get_targets_from_gamestate())
        self.assertEqual(after, before)

    def test_fail_create_with_inactive_rover(self):
        # Expect an error log message.
        self.expect_log('front.callbacks.target_callbacks', 'Refusing to create target for inactive rover')

        before = len(self.get_targets_from_gamestate())
        # Pull out the active rover create_target_url.
        gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        rover_id = rover['rover_id']
        self.assertEqual(rover['active'], 1)
        create_target_url = str(rover['urls']['target'])

        # And create a target to make sure everything is working.
        self.create_target(create_target_url=create_target_url, arrival_delta=SIX_HOURS, **points.FIRST_MOVE)

        # Mark the current rover inactive.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                rover = user.rovers[rover_id]
                rover.mark_inactive()

        # Verify it is inactive.
        gamestate = self.get_gamestate()
        rover = gamestate['user']['rovers'][rover_id]
        self.assertEqual(rover['active'], 0)

        # Attempt to create a target with the now inactive rover, which should fail and log an error.
        result = self.create_target(create_target_url=create_target_url, arrival_delta=2*SIX_HOURS, status=400, **points.SECOND_MOVE)
        self.assertTrue("Error when creating target" in result['errors'][0])

        # Make sure only one target was created.
        after = len(self.get_targets_from_gamestate())
        self.assertEqual(after, before + 1)
