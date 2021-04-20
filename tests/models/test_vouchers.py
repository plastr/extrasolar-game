# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import db
from front.models import chips
from front.models import voucher as voucher_module

from front.tests import base
from front.tests.base import VOUCHER_KEY_S1

class TestVouchers(base.TestCase):
    def setUp(self):
        super(TestVouchers, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_vouchers(self):
        CAPABILITY_KEY = 'CAP_S1_CAMERA_INFRARED'
        VOUCHER_KEY = VOUCHER_KEY_S1
        VOUCHER_MSG = "MSG_DELIVER_VCH_S1_PASS"
        self.assertTrue(voucher_module.is_known_voucher_key(VOUCHER_KEY))

        # Verify the chosen capability is not unlimited initially.
        capability = self.get_gamestate()['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['unlimited'], 0)

        # Deliver the voucher to the user.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            u = self.get_logged_in_user(ctx=ctx)
            with db.conn(ctx) as ctx:
                voucher_module.deliver_new_voucher(ctx, u, VOUCHER_KEY)

        # Make sure a message was delivered.
        chip = self.last_chip_for_path(['user', 'messages', '*'])
        self.assertEqual(chip['value']['msg_type'], VOUCHER_MSG)

        chip = self.last_chip_for_path(['user', 'vouchers', '*'])
        self.assertEqual(chip['action'], chips.ADD)
        self.assertEqual(chip['value']['voucher_key'], VOUCHER_KEY)
        self.assertIsNotNone(chip['value']['delivered_at'])
        gamestate = self.get_gamestate()
        voucher = gamestate['user']['vouchers'][VOUCHER_KEY]
        self.assertEqual(voucher['voucher_key'], VOUCHER_KEY)
        self.assertIsNotNone(voucher['delivered_at'])

        # Capability should now be unlimited.
        chip = self.last_chip_for_path(['user', 'capabilities', CAPABILITY_KEY])
        self.assertEqual(chip['action'], chips.MOD)
        self.assertEqual(chip['value']['unlimited'], 1)
        capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['unlimited'], 1)

    def test_voucher_which_changes_rover_fields(self):
        CAPABILITY_KEY = 'CAP_S1_ROVER_FAST_MOVE'
        VOUCHER_KEY = VOUCHER_KEY_S1
        self.assertTrue(voucher_module.is_known_voucher_key(VOUCHER_KEY))

        # Verify the chosen capability is not unlimited initially.
        gamestate = self.get_gamestate()
        capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['unlimited'], 0)
        rover = self.get_active_rover(gamestate)
        min_target_seconds_before = rover['min_target_seconds']
        max_unarrived_targets_before = rover['max_unarrived_targets']

        # Deliver the voucher to the user.
        with db.commit_or_rollback(self.get_ctx()) as ctx:
            u = self.get_logged_in_user(ctx=ctx)
            with db.conn(ctx) as ctx:
                voucher_module.deliver_new_voucher(ctx, u, VOUCHER_KEY)

        # Capability should now be unlimited.
        gamestate = self.get_gamestate()
        capability = gamestate['user']['capabilities'][CAPABILITY_KEY]
        self.assertEqual(capability['unlimited'], 1)

        found_chips = self.chips_for_path(['user', 'rovers', '*'])
        self.assertEqual(len(found_chips), 2)

        # This voucher should have enabled the fast move capability which should have changed
        # the rover's min_target_seconds value.
        chip = found_chips[0]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertTrue(chip['value']['min_target_seconds'] < min_target_seconds_before)
        rover = self.get_active_rover(gamestate)
        self.assertTrue(rover['min_target_seconds'] < min_target_seconds_before)

        # This voucher should have also changed the number of targets that can be scheduled.
        chip = found_chips[1]
        self.assertEqual(chip['action'], chips.MOD)
        self.assertTrue(chip['value']['max_unarrived_targets'] > max_unarrived_targets_before)
        rover = self.get_active_rover(gamestate)
        self.assertTrue(rover['max_unarrived_targets'] > max_unarrived_targets_before)
        