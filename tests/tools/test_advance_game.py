# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import timedelta

from front import Constants, InitialMessages
from front.lib import db, utils
from front.backend import deferred
from front.models import chips, message
from front.tools import advance_game
from front.debug import CHIP_ACTIVATION_DELTA, EPOCH_ACTIVATION_DELTA

from front.tests import base
from front.tests.base import points, SIX_HOURS

class TestAdvanceGame(base.TestCase):
    def setUp(self):
        super(TestAdvanceGame, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_advance_game_increment_mode(self):
        self._test_game_mode_one_target('increment', ticks=1, tick_seconds=3600*6)

    def test_advance_game_catchup_mode(self):
        self._test_game_mode_one_target('catchup', ticks=InitialMessages.EMAIL_VERIFY02_DELAY_HOURS, tick_seconds=3600)

    # Test a given advance_game run mode by creating one target and setting the number of ticks
    # to the supplied value. It is expected that the number of ticks will catchup the game to the given
    # target and assertions will run to verify the target has been arrived at and that user.epoch is correct.
    def _test_game_mode_one_target(self, run_mode, ticks, tick_seconds):
        arrival_delta = SIX_HOURS
        last_deferred_delta = arrival_delta
        # One deferred for arrived_at_target
        expected_deferred_runs = 1
        if run_mode is 'catchup':
            # Delay until timer that sends (when needed) second backdoor email.
            last_deferred_delta = utils.in_seconds(hours=InitialMessages.EMAIL_VERIFY02_DELAY_HOURS)
            expected_deferred_runs += 1  # Deferred timer to check if second backdoor email should be sent.
        chips_result = self.create_target(arrival_delta=arrival_delta, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']

        # Advance time past the the create_target ADD chip so assertions will be clear.
        CLEAR_CHIPS_SECONDS = 10
        self.advance_now(seconds=CLEAR_CHIPS_SECONDS)

        user = self.get_logged_in_user()
        epoch_before = user.epoch

        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                advance = advance_game.AdvanceGameTool(ctx, 'testuser@example.com', run_renderer=False,
                                                       tick_seconds=tick_seconds, pause_seconds=0, verbose=False)
                advance.enter_run_mode(run_mode)

        # Advance to the activated chip moment.
        self.advance_now(seconds=CHIP_ACTIVATION_DELTA)

        # 1 target processed with 1 target ADD chip
        self.assertEqual(len(advance.processed_targets), 1)
        # Use _activated_chips_for_path to specifically find the chips expected. Is possible with things like
        # special date based achievements that a chip would appear in this set on certain days when this test is running
        # changing the number of chips in advance.activated_chips
        self.assertEqual(len(self._activated_chips_for_path(['user', 'rovers', '*', 'targets', '*'], advance.activated_chips)), 1)
        self.assertEqual(len(advance.deferreds_run), expected_deferred_runs)
        
        # Verify that the activated target chips are MODs (rendering the target)
        # and that it matches the only target chip we see when we do a fetch_chip 'now'.
        activated_chip = advance.activated_chips[0]
        self.assertEqual(activated_chip['value']['target_id'], first_target_id)
        self.assertEqual(activated_chip['action'], chips.MOD)
        target_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', '*'])
        self.assertEqual(len(target_chips), 1)
        target_chip = target_chips[0]
        self.assertEqual(target_chip['value']['target_id'], first_target_id)
        self.assertEqual(target_chip['action'], chips.MOD)

        # Verify the chip that came in via fetch_chip had its 'time' value rolled back to "now"
        # as compared to the activated_chip value which is the value before the rollback.
        chip_time_dt = utils.usec_dt_from_js(target_chip['time']) - timedelta(seconds=Constants.TARGET_DATA_LEEWAY_SECONDS)
        activated_chip_dt = utils.usec_dt_from_js(activated_chip['time'])
        # Calculate the amount of change to the activated chip.time, factoring in various
        # buffers we have added to isolate the chips.
        # Need to factor in CLEAR_CHIPS_SECONDS since we are rolling back to the time the test started
        # plus those seconds.
        activation_delta = (activated_chip_dt - chip_time_dt) + timedelta(seconds=CLEAR_CHIPS_SECONDS + CHIP_ACTIVATION_DELTA)
        activation_tick_delta = tick_seconds - activation_delta.total_seconds()
        # Given the fact that our chip.time is now accurate to microseconds, the chips are activated to
        # within a 1 second delta relative to our tick time which is only accurate to seconds.
        self.assertTrue(activation_tick_delta < 1.0)

        user = self.get_logged_in_user()
        # Epoch should have been rolled back.
        self.assertEqual(epoch_before - user.epoch, timedelta(seconds=last_deferred_delta))
        # Count the number of user.epoch chips to verify there were the expected number of ticks.
        epoch_chips = self.chips_for_path(['user'])
        for epoch_chip in epoch_chips:
            self.assertTrue('epoch' in epoch_chip['value'])
            # Every user.epoch chip should have a time value that is exactly EPOCH_ACTIVATION_DELTA less
            # than the other activated chips to be sure those epoch chips are applied on the client before
            # any activated chips.
            self.assertEqual(int(epoch_chip['time']) + EPOCH_ACTIVATION_DELTA, int(target_chip['time']))
        self.assertEqual(len(epoch_chips), ticks)

    def test_advance_game_catchup_mode_with_deferreds_two_targets(self):
        arrival_delta = SIX_HOURS
        chips_result = self.create_target(arrival_delta=arrival_delta, **points.FIRST_MOVE)
        first_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        first_target_id = first_target['target_id']
        chips_result = self.create_target(arrival_delta=arrival_delta*2, **points.SECOND_MOVE)
        second_target = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        second_target_id = second_target['target_id']

        # Hours until timer that sends (when needed) second backdoor email.
        TICKS = InitialMessages.EMAIL_VERIFY02_DELAY_HOURS
        tick_seconds = 3600
        user = self.get_logged_in_user()
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            with db.conn(ctx) as ctx:
                # Send a test message in the future which will trigger a deferred.
                message.send_later(ctx, user, 'MSG_TEST_SIMPLE', utils.in_seconds(minutes=30))

                advance = advance_game.AdvanceGameTool(ctx, 'testuser@example.com', run_renderer=False,
                                                       tick_seconds=tick_seconds, pause_seconds=0, verbose=False)
                advance.run_catchup_mode()

        # Advance to the activated chip moment.
        self.advance_now(seconds=CHIP_ACTIVATION_DELTA)

        # 2 targets rendered, with 1 message chip and 4 deferred actions (message + check if second validation email
        # should be sent + one arrived_at_target for each target).
        self.assertEqual(len(advance.processed_targets), 2)
        # Use _activated_chips_for_path to specifically find the chips expected. Is possible with things like
        # special date based achievements that a chip would appear in this set on certain days when this test is running
        # changing the number of chips in advance.activated_chips
        activated_target_chips = self._activated_chips_for_path(['user', 'rovers', '*', 'targets', '*'], advance.activated_chips)
        self.assertEqual(len(activated_target_chips), 2)
        activated_message_chips = self._activated_chips_for_path(['user', 'messages', '*'], advance.activated_chips)
        self.assertEqual(len(activated_message_chips), 1)
        self.assertEqual(len(advance.deferreds_run), 4)

        # Verify there were two chips for the target renderings and 1 for the message.
        self.assertEqual(activated_message_chips[0]['action'], chips.ADD)
        self.assertEqual(activated_message_chips[0]['path'][1], 'messages')
        self.assertEqual(activated_target_chips[0]['action'], chips.MOD)
        self.assertEqual(activated_target_chips[0]['value']['target_id'], first_target_id)
        self.assertEqual(activated_target_chips[1]['action'], chips.MOD)
        self.assertEqual(activated_target_chips[1]['value']['target_id'], second_target_id)

        # Verify that the deferred action was for the expected message.
        self.assertEqual(advance.deferreds_run[0].deferred_type, deferred.types.MESSAGE)
        self.assertEqual(advance.deferreds_run[0].subtype, "MSG_TEST_SIMPLE")

        # Verify we saw the correct number of ticks.
        epoch_chips = self.chip_values_for_path(['user'])
        self.assertEqual(len(epoch_chips), TICKS)

    def _activated_chips_for_path(self, path, activated_chips):
        # Use the base test class chip finding routines to find only the chips for the given path in the result
        # of the advance game tools activated chips.
        return self.chips_for_path(path, {'chips': activated_chips})
