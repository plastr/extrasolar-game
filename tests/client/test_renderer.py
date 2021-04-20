# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
# Emulate the calls that the renderer would make to the Web Services module.
from front import Constants
from front.lib import db, utils
from front.data import scene
from front.models import chips

from front.tests import base
from front.tests.base import points

class TestRenderer(base.TestCase):
    def setUp(self):
        super(TestRenderer, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_next_target_and_processed_target(self):
        # Create two unprocessed targets, six hours apart.
        gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        create_target_url = str(rover['urls']['target'])
        chips_result = self.create_target(
            create_target_url, arrival_delta=base.SIX_HOURS, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']

        chips_result = self.create_target(
            create_target_url, arrival_delta=base.SIX_HOURS*2, **points.SECOND_MOVE)
        second_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        second_target_id = second_target['target_id']
        second_target_arrival = second_target['arrival_time']

        # Both targets should be unprocessed and unlocked.
        self._assert_target_id_processed_locked(
            rover['rover_id'], first_target_id, processed=0, locked=False)
        self._assert_target_id_processed_locked(
            rover['rover_id'], second_target_id, processed=0, locked=False)

        ## Test processing the first target. Get the target info by making a next target request,
        # verify it matches the expect target (the older target), then process the target.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, first_target_id)
        # Verify the asset list looks correct.
        self.assert_assets_equal(result, ["LANDER01", "ROVER_SHADOW"])

        # There should be no more work to do, even though there is another unrendered target, because
        # the render_at time has not arrived for that target.
        result = self.renderer_service_next_target()
        self.assertEqual(result, {'status': 'ok'})

        # Verify the target starts unprocessed, with no target images and becomes processed and
        # has the expected target images.
        self._assert_target_id_processed_locked(rover_id, target_id, processed=0, locked=True)
        self._assert_target_id_images(rover_id, target_id, images={})
        # Emulate the renderer informing the web service that the target was processed.
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, first_target_arrival)
        self.assertEqual(result, {'status': 'ok'})
        # The target should now be processed and have images in the database.
        self._assert_target_id_processed_locked(rover_id, target_id, processed=1, locked=False)
        self._assert_target_id_images(rover_id, target_id, images=scene.TESTING.to_struct())
        gamestate_target = self.get_targets_from_gamestate(self.get_gamestate())[-2]
        # The processed flag and images should be hidden in the gamestate.
        self.assertEqual(gamestate_target['target_id'], target_id)
        self.assertEqual(gamestate_target['processed'], 0)
        self.assertEqual(gamestate_target['images'], {})
        # There should be custom map tiles available yet.
        self.assertEqual(len(self.get_gamestate()['user']['map_tiles']), 0)
        # Advance time to the chip arrival time.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the target changes should have been issued into the future.
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['target_id'], target_id)
        self.assertEqual(chip['value']['processed'], 1)
        # Species ID images are hidden from the client gamestate and should not be in chip.
        self.assertEqual(chip['value']['images'], scene.TESTING.to_struct_for_client())
        # A chip for the map tile changes should also have been issued into the future.
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], first_target_arrival)

        # The map tile should now be available and not expired.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, first_target_arrival, None)
        # There should be custom map tiles in the gamestate.
        self.assertEqual(len(self.get_gamestate()['user']['map_tiles']), 2)
        # The target in the gamestate should be processed now and have images.
        gamestate_target = self.get_targets_from_gamestate(self.get_gamestate())[-2]
        self.assertEqual(gamestate_target['target_id'], target_id)
        self.assertEqual(gamestate_target['processed'], 1)
        # Species ID images are hidden from the client gamestate.
        self.assertEqual(gamestate_target['images'], scene.TESTING.to_struct_for_client())

        # There should still be no more work to do as we advanced to within TARGET_DATA_LEEWAY_SECONDS, but not
        # all the way to the render_at time of the second target.
        result = self.renderer_service_next_target()
        self.assertEqual(result, {'status': 'ok'})

        # Now advance to the render_at time of the second target.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)

        ## Test processing a second target. First lock it, and try to get additional work
        # which should return nothing and then move gametime forward 30 minutes and try
        # again which should have expired the lock.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, second_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, second_target_id)

        # Breaking the lock generates a warning log message.
        self.expect_log('front.models.target', 'Breaking lock on Target.*')

        # The last unprocessed target is locked so should be no more work.
        result = self.renderer_service_next_target()
        self.assertEqual(result, {'status': 'ok'})

        # Advance time past the lock.
        self.advance_now(minutes=30)
        result = self.renderer_service_next_target()
        # The lock should have expired so there should be the same work item again.
        self.assertTrue(len(result) > 0)
        (user_id, rover_id, target_id, second_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, second_target_id)

        self._assert_target_id_processed_locked(rover_id, target_id, processed=0, locked=True)
        self._assert_target_id_images(rover_id, target_id, images={})
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, second_target_arrival)
        self.assertEqual(result, {'status': 'ok'})
        self._assert_target_id_processed_locked(rover_id, target_id, processed=1, locked=False)
        self._assert_target_id_images(rover_id, target_id, images=scene.TESTING.to_struct())
        # The old map tile should still be available and set to expire.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, first_target_arrival, second_target_arrival)
        # Advance time to the chip arrival time. (factoring in the time above to break the lock.)
        self.advance_now(seconds=utils.in_seconds(hours=5, minutes=30))
        # A chip for the map tile changes should also have been issued into the future.
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'], seconds_ago=utils.in_seconds(minutes=31))
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], second_target_arrival)

        # The new map tile should still be available and set to not expire.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, second_target_arrival, None)
        # There should be custom map tiles in the gamestate.
        self.assertEqual(len(self.get_gamestate()['user']['map_tiles']), 2)

        # There should be no more targets to process.
        result = self.renderer_service_next_target()
        self.assertEqual(result, {'status': 'ok'})

        # Let some time go by before reprocessing
        self.advance_now(minutes=30)

        # Create one more target in the future and render it, but do not 'arrive' at its time yet so
        # that there are future map tiles in the database.
        chips_result = self.create_target(create_target_url, arrival_delta=base.SIX_HOURS, **points.THIRD_MOVE)
        third_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        third_target_id = third_target['target_id']
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, third_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, third_target_id)
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, third_target_arrival)
        self.assertEqual(result, {'status': 'ok'})
        # The tiles in the gamestate should still be the ones from the second render.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, second_target_arrival, third_target_arrival)

        ## Set the second target as unprocessed to emulate the developers requesting that it needs
        # to be rerendered.  We need to make sure that if we try to process a target twice, the
        # target_images and user_map_tiles get properly updated when a duplicate key is detected.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                user = self.get_logged_in_user(ctx=ctx)
                reprocess_target = user.rovers.find_target_by_id(second_target_id)
                reprocess_target.mark_for_rerender()

        # Reprocess the second target.  Make sure we got the expected target_id.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, redo_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, second_target_id)
        # There should have been no ADD or MOD chip.
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertIsNone(chip)

        # Verify the target is unprocessed and locked
        self._assert_target_id_processed_locked(rover_id, target_id, processed=0, locked=True)

        # Emulate the renderer informing the web service that the target was processed.
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, redo_target_arrival)
        self.assertEqual(result, {'status': 'ok'})

        # The target should now again be processed.
        self._assert_target_id_processed_locked(rover_id, target_id, processed=1, locked=False)

        # The old map tile should still be available and set to expire.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, second_target_arrival, third_target_arrival)

        # Advance time to the third targets tile chip arrival time.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the map tile changes should also have been issued into the future.
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], third_target_arrival)

        # The new map tile should still be available and set to not expire.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, third_target_arrival, None)
        # There should be custom map tiles in the gamestate.
        self.assertEqual(len(self.get_gamestate()['user']['map_tiles']), 2)

        # There should be no more targets to process.
        result = self.renderer_service_next_target()
        self.assertEqual(result, {'status': 'ok'})

    ## The following two map tile out_of_order tests assert that the code in maptile creation handles targets
    # being rendered out of order (not in the order they were created). This should never happen in the new renderer
    # scheme where only the users next target is every rendered (filtering on render_at) but using rewind_now these
    # two tests emulate the old render queue to make sure the maptile code continues to work should we ever go back
    # to that queuing system.
    def test_processed_target_out_of_order_first_map_tiles(self):
        ## Test that if the first targets to touch a tile area are processed out of order (which might happen with
        ## multiple rendering instances running) that the map tiles end up looking correct.
        gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        create_target_url = str(rover['urls']['target'])

        # Create two first targets.
        chips_result = self.create_target(create_target_url, arrival_delta=base.SIX_HOURS, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']
        chips_result = self.create_target(create_target_url, arrival_delta=base.SIX_HOURS*2, **points.SECOND_MOVE)
        second_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        second_target_id = second_target['target_id']
        # And advance to the render_at time of the last target (as if the renderer was severely backed up) so
        # that they can be both processed at the same time, as the renderer used to work before render_at was added.
        self.advance_now(seconds=base.SIX_HOURS)

        # And process them 'out of order' to test the code in the map tile creation.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, first_target_id)
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, second_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, second_target_id)
        # Now return the processed results out of order.
        result = self.renderer_service_processed_target(user_id, rover_id, second_target_id, second_target_arrival)
        self.assertEqual(result, {'status': 'ok'})
        result = self.renderer_service_processed_target(user_id, rover_id, first_target_id, first_target_arrival)
        self.assertEqual(result, {'status': 'ok'})

        # Now rewind back to the start time of the first target, thus emulating how the renderer used to work,
        # before render_at was added.
        self.rewind_now(seconds=base.SIX_HOURS)

        # There should be no visible map_tiles yet.
        self.assertEqual(len(self.get_gamestate()['user']['map_tiles']), 0)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertIsNone(chip)

        # Now advance to the leeway time before the first target.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the map tile changes should also have been issued into the future.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, first_target_arrival, second_target_arrival)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], first_target_arrival)
        # Consume the leeway seconds.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)

        # Now advance to the leeway time before the second target.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the map tile changes should also have been issued into the future.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, second_target_arrival, None)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        # Crucially, this should also be an ADD.
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], second_target_arrival)
        # Consume the leeway seconds.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)

    def test_processed_target_out_of_order_later_map_tiles(self):
        ## Test that if later targets are processed out of order (which might happen with multiple rendering instances
        ## running) that the map tiles end up looking correct.
        gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        create_target_url = str(rover['urls']['target'])
        # Render one target so that there are existing tiles for the test tile location (so that the targets being
        # tested next are not the first tiles).
        chips_result = self.create_target(create_target_url, arrival_delta=base.SIX_HOURS, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, first_target_id)
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, first_target_arrival)
        self.assertEqual(result, {'status': 'ok'})
        # There should be no visible map_tiles yet.
        self.assertEqual(len(self.get_gamestate()['user']['map_tiles']), 0)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertIsNone(chip)
        # Advance to the leeway time just before arriving at the first target.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # Just arrived at the first target, so check that tile is active and there is an ADD chip.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, first_target_arrival, None)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], first_target_arrival)
        # Consume the leeway seconds.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)

        # Now create two targets.
        chips_result = self.create_target(create_target_url, arrival_delta=base.SIX_HOURS, **points.SECOND_MOVE)
        second_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        second_target_id = second_target['target_id']
        chips_result = self.create_target(create_target_url, arrival_delta=base.SIX_HOURS*2, **points.THIRD_MOVE)
        third_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        third_target_id = third_target['target_id']
        # And advance to the render_at time of the last target (as if the renderer was severely backed up) so
        # that they can be both processed at the same time, as the renderer used to work before render_at was added.
        self.advance_now(seconds=base.SIX_HOURS)

        # And process them 'out of order' to test the code in the map tile creation.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, second_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, second_target_id)
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, third_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, third_target_id)
        # Now return the processed results out of order.
        result = self.renderer_service_processed_target(user_id, rover_id, third_target_id, third_target_arrival)
        self.assertEqual(result, {'status': 'ok'})
        result = self.renderer_service_processed_target(user_id, rover_id, second_target_id, second_target_arrival)
        self.assertEqual(result, {'status': 'ok'})

        # Now rewind back to the start time of the first target, thus emulating how the renderer used to work,
        # before render_at was added.
        self.rewind_now(seconds=base.SIX_HOURS)

        # Now move forward in time to each target's arrival time (minus the leeway) and make sure the tiles
        # look correct.
        # Now that there are more targets, the first targets tiles should now have an expiry_time.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, first_target_arrival, second_target_arrival)

        # Now advance to the leeway time before the second target.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the map tile changes should also have been issued into the future.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, second_target_arrival, third_target_arrival)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], second_target_arrival)
        # Consume the leeway seconds.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)

        # Now advance to the leeway time before the third target.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the map tile changes should also have been issued into the future.
        self._assert_map_tile_arrival_and_expire(base.TILE_KEY, third_target_arrival, None)
        chip = self.last_chip_for_path(['user', 'map_tiles', '*'])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['tile_key'], base.TILE_KEY)
        self.assertEqual(chip['value']['arrival_time'], third_target_arrival)
        # Consume the leeway seconds.
        self.advance_now(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)

    def test_renderer_service_classified(self):
        # Create one unprocessed target, arriving in 6 hours.
        gamestate = self.get_gamestate()
        rover = self.get_active_rover(gamestate)
        create_target_url = str(rover['urls']['target'])
        chips_result = self.create_target(
            create_target_url, arrival_delta=base.SIX_HOURS, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']

        # Both targets should be unprocessed and unlocked and unclassified.
        self._assert_target_id_processed_locked(
            rover['rover_id'], first_target_id, processed=0, classified=0, locked=False)

        ## Test processing the first target. Get the target info by making a next target request,
        # verify it matches the expect target (the older target), then process the target.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, first_target_id)

        # Verify the target starts unprocessed, with no target images and becomes processed and
        # has the expected target images.
        self._assert_target_id_processed_locked(rover_id, target_id, processed=0, classified=0, locked=True)
        self._assert_target_id_images(rover_id, target_id, images={})
        # Emulate the renderer informing the web service that the target was processed and is classified.
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, first_target_arrival, classified=1)
        self.assertEqual(result, {'status': 'ok'})
        # The target should now be processed and have images in the database.
        self._assert_target_id_processed_locked(rover_id, target_id, processed=1, classified=1, locked=False)
        self._assert_target_id_images(rover_id, target_id, images=scene.TESTING.to_struct())
        gamestate_target = self.get_targets_from_gamestate(self.get_gamestate())[-1]
        # The processed and classified flags and images should be hidden in the gamestate.
        self.assertEqual(gamestate_target['target_id'], target_id)
        self.assertEqual(gamestate_target['processed'], 0)
        self.assertEqual(gamestate_target['classified'], 0)
        self.assertEqual(gamestate_target['images'], {})
        # Advance time to chip arrival time.
        self.advance_now(seconds=base.SIX_HOURS - Constants.TARGET_DATA_LEEWAY_SECONDS)
        # A chip for the target changes should have been issued into the future.
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['target_id'], target_id)
        self.assertEqual(chip['value']['processed'], 1)
        self.assertEqual(chip['value']['classified'], 1)
        # The target in the gamestate should be processed now and have images.
        gamestate_target = self.get_targets_from_gamestate(self.get_gamestate())[-1]
        self.assertEqual(gamestate_target['target_id'], target_id)
        self.assertEqual(gamestate_target['processed'], 1)
        self.assertEqual(chip['value']['classified'], 1)

    def test_renderer_service_target_metadata(self):
        # The RENDERER_METADATA values represent values which will be merged on top of the CLIENT_METADATA
        # emulating the renderer performing a similar change.
        CLIENT_METADATA           = {'TGT_TEST_1': '', 'TGT_TEST_2': 'test_value', 'TGT_TEST_3': ''}
        RENDERER_METADATA_CHANGES = {'TGT_TEST_3': 'value_set', 'TGT_TEST_4': 'new_value', 'TGT_TEST_5': ''}

        # Create an unprocessed target.
        chips_result = self.create_target(metadata=CLIENT_METADATA, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']
        self.assertEqual(first_target['metadata'], CLIENT_METADATA)

        # Verify the next target data looks correct.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertEqual(target_id, first_target_id)
        self.assertEqual(metadata, CLIENT_METADATA)

        # Emulate the renderer informing the web service that the target was processed and
        # also merging the metadata changes it wants to make with the original values supplied.
        RENDERER_METADATA = CLIENT_METADATA.copy()
        RENDERER_METADATA.update(RENDERER_METADATA_CHANGES)

        # But first, emulate the renderer attempting to delete a metadata key, which is not allowed.
        DELETED_RENDERER_METADATA = RENDERER_METADATA.copy()
        del DELETED_RENDERER_METADATA['TGT_TEST_1']
        self.assertRaises(AssertionError, self.renderer_service_processed_target, user_id, rover_id,
                                          target_id, first_target_arrival, metadata=DELETED_RENDERER_METADATA)

        # And now render with the proper merged metadata.
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, first_target_arrival, metadata=RENDERER_METADATA)
        self.assertEqual(result, {'status': 'ok'})
        # The target should now be processed and have images in the database.
        self._assert_target_id_processed_locked(rover_id, target_id, processed=1, locked=False)
        self._assert_target_id_images(rover_id, target_id, images=scene.TESTING.to_struct())
        gamestate_target = self.get_targets_from_gamestate(self.get_gamestate())[-1]
        # The processed and classified flags and images should be hidden in the gamestate.
        self.assertEqual(gamestate_target['target_id'], target_id)
        self.assertEqual(gamestate_target['processed'], 0)
        self.assertEqual(gamestate_target['images'], {})
        # The metadata should now match the data returned by the renderer
        self.assertEqual(gamestate_target['metadata'], RENDERER_METADATA)
        # A MOD chip should have been sent immediately for the metadata field.
        chip = self.last_chip_for_path(['user', 'rovers', '*', 'targets', '*'])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['target_id'], target_id)
        self.assertEqual(chip['value']['metadata'], RENDERER_METADATA)

    def test_renderer_service_infrared(self):
        # Starting rover might not have infrared capabilities so force it to be available and unlimited.
        self.enable_capabilities_on_active_rover(['CAP_S1_CAMERA_INFRARED'])

        # Schedule an infrared photo.
        METADATA = {'TGT_FEATURE_INFRARED': ''}
        self.create_target(metadata=METADATA, **points.FIRST_MOVE)

        # Render the next target.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertTrue('TGT_FEATURE_INFRARED' in metadata)
        
        # Emulate the renderer informing the web service that the target was processed.
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, first_target_arrival,
            render_scene=scene.TESTING_INFRARED, metadata=METADATA)
        self.assertEqual(result, {'status': 'ok'})

        # Make sure the returned scene looks correct.
        self._assert_target_id_images(rover_id, target_id, images=scene.TESTING_INFRARED.to_struct())

    def test_renderer_service_panorama(self):
        # Starting rover might not have panorama capabilities so force it to be available and unlimited.
        self.enable_capabilities_on_active_rover(['CAP_S1_CAMERA_PANORAMA'])

        # Schedule a panorama.
        METADATA = {'TGT_FEATURE_PANORAMA': ''}
        self.create_target(metadata=METADATA, **points.FIRST_MOVE)

        # Render the next target.
        result = self.renderer_service_next_target()
        (user_id, rover_id, target_id, first_target_arrival, metadata) = self.renderer_decompose_next_target(result)
        self.assertTrue('TGT_FEATURE_PANORAMA' in metadata)

        # Emulate the renderer informing the web service that the target was processed.
        result = self.renderer_service_processed_target(user_id, rover_id, target_id, first_target_arrival,
            render_scene=scene.TESTING_PANORAMA, metadata=METADATA)
        self.assertEqual(result, {'status': 'ok'})

        # Make sure the returned scene looks correct.
        self._assert_target_id_images(rover_id, target_id, images=scene.TESTING_PANORAMA.to_struct())

    def test_renderer_service_no_auth(self):
        self.assertRaises(AssertionError, self.renderer_service_next_target, auth_token="bogus_token")

    # Verify the given target_id has the given processed value in the database.
    def _assert_target_id_processed_locked(self, rover_id, target_id, processed, locked, classified=0):
        user = self.get_logged_in_user()
        target = user.rovers[rover_id].targets[target_id]
        self.assertEqual(target.processed, processed)
        self.assertEqual(target.classified, classified)
        self.assertEqual(target.is_locked(), locked)

    def _assert_target_id_images(self, rover_id, target_id, images):
        user = self.get_logged_in_user()
        target = user.rovers[rover_id].targets[target_id]
        self.assertEqual(target.images, images)

    def _assert_map_tile_arrival_and_expire(self, tile_key, arrival_time, expiry_time):
        user = self.get_logged_in_user()
        tile = user.map_tiles[tile_key]
        self.assertEqual(arrival_time, tile.arrival_time)
        if expiry_time is None:
            self.assertEqual(tile.expiry_time, None)
        else:
            expiry_time_date = user.after_epoch_as_datetime(expiry_time)
            self.assertEqual(tile.expiry_time, expiry_time_date)
