# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import datetime

from front import Constants
from front.lib import gametime, utils
from front.callbacks import get_callback_class, ACHIEVEMENT_CB
from front.models import achievement

from front.tests import base
from front.tests.base import SIX_HOURS, points, rects
from front.tests.base import INVITE_EMAIL, INVITE_FIRST_NAME, INVITE_LAST_NAME

class TestAchievements(base.TestCase):
    def setUp(self):
        super(TestAchievements, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    # Test that when you take your first panorama or infrared photo, you get an achievement.
    def test_pano_achievement(self):
        # Starting rover might not have panorama and infrared capabilities so force them to be available and unlimited.
        self.enable_capabilities_on_active_rover(['CAP_S1_CAMERA_PANORAMA', 'CAP_S1_CAMERA_INFRARED'])

        # Take a panorama photo and move to that target, achieving the panorama achievement.
        self.assertFalse(self.get_logged_in_user().achievements['ACH_PHOTO_PANO'].was_achieved())
        self.create_target_and_move(metadata={'TGT_FEATURE_PANORAMA':''}, **points.FIRST_MOVE)
        self.assertTrue(self.get_logged_in_user().achievements['ACH_PHOTO_PANO'].was_achieved())

        # Take an infrared photo and move to that target, achieving the infrared achievement.
        self.assertFalse(self.get_logged_in_user().achievements['ACH_PHOTO_IR'].was_achieved())
        self.create_target_and_move(metadata={'TGT_FEATURE_INFRARED':''}, **points.SECOND_MOVE)
        self.assertTrue(self.get_logged_in_user().achievements['ACH_PHOTO_IR'].was_achieved())

    # Test achieving the highlighted photo achievement for a target that has not been arrived at, meaning the
    # achievement and a MSG will be delivered upon target arrival.
    def test_highlight_achievement_delayed(self):
        self.make_user_admin(self.get_logged_in_user())
        # Need a new target as the initial system created photos are now filtered out of highlights.
        # Do not move the gametime to that target's arrival_time so it has not been arrived at.
        self.create_target(arrival_delta=SIX_HOURS, **points.FIRST_MOVE)
        self.render_next_target()

        # The achievement should not have been achieved (and no message yet).
        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_PHOTO_HIGHLIGHT'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_PHOTO_HIGHLIGHT'))
        # Grab the new target and use the admin API to mark it highlighted.
        target_id = self.get_most_recent_target_from_gamestate()['target_id']
        self.admin_api_highlight_add(target_id)
        # The achievement should still not have been achieved (and no message yet).
        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_PHOTO_HIGHLIGHT'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_PHOTO_HIGHLIGHT'))

        # Now advance the game to the targets arrival time plus a few minutes and the achievement should
        # be achieved and the message delivered.
        self.advance_game(seconds=SIX_HOURS + utils.in_seconds(minutes=1))
        user = self.get_logged_in_user()
        self.assertTrue(user.achievements['ACH_PHOTO_HIGHLIGHT'].was_achieved())
        self.assertIsNotNone(user.messages.by_type('MSG_ACH_PHOTO_HIGHLIGHT'))

    # Test achieving the highlighted photo achievement for a target that has been arrived at, meaning the
    # achievement and a MSG will be delivered immediatly.
    def test_highlight_achievement_immediate(self):
        self.make_user_admin(self.get_logged_in_user())
        # Need a new target as the initial system created photos are now filtered out of highlights.
        # Move the gametime to that target's arrival_time and render it so it has been arrived at.
        self.create_target_and_move(**points.FIRST_MOVE)

        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_PHOTO_HIGHLIGHT'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_PHOTO_HIGHLIGHT'))
        # Grab the new target and use the admin API to mark it highlighted.
        target_id = self.get_most_recent_target_from_gamestate()['target_id']
        self.admin_api_highlight_add(target_id)
        user = self.get_logged_in_user()
        self.assertTrue(user.achievements['ACH_PHOTO_HIGHLIGHT'].was_achieved())
        self.assertIsNotNone(user.messages.by_type('MSG_ACH_PHOTO_HIGHLIGHT'))

    def test_invitation_achievement(self):
        # Be sure the user has an invitation.
        self.set_user_invites_left(1)
        self.assertFalse(self.get_logged_in_user().achievements['ACH_SOCIAL_INVITE'].was_achieved())

        # Send an invitation which should achieve the achievement.
        create_invite_url = str(self.get_gamestate()['urls']['create_invite'])
        payload = {
            'recipient_email': INVITE_EMAIL,
            'recipient_first_name': INVITE_FIRST_NAME,
            'recipient_last_name': INVITE_LAST_NAME,
            'recipient_message': 'Hello my friend, you should play this game!'
        }
        response = self.json_post(create_invite_url, payload)
        found_chips = self.chips_for_path(['user', 'invitations', '*'], response)
        self.assertEqual(len(found_chips), 1)
        # The achievement should now be achieved.
        self.assertTrue(self.get_logged_in_user().achievements['ACH_SOCIAL_INVITE'].was_achieved())

    # Test achieving the 3 different species same target achievement when some of the species identified
    # have delayed species data.
    def test_three_different_species_same_target_achievement_delayed(self):
        self.create_target_and_move(**points.FIRST_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])

        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_SPECIES_TAG_3'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_SPECIES_TAG_3'))
        # Tag 3 unique species in the same target.
        self.check_species(check_species_url, [rects.SPC_PLANT001, rects.SPC_PLANT002, rects.SPC_PLANT003])
        # The achievement is still not achieved because some of the species data was delayed for first identification.
        self.assertFalse(self.get_logged_in_user().achievements['ACH_SPECIES_TAG_3'].was_achieved())

        # Advance the game so that all species data is now fully available, which should also achieve the badge and
        # deliver the message.
        self.advance_game(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)
        user = self.get_logged_in_user()
        self.assertTrue(user.achievements['ACH_SPECIES_TAG_3'].was_achieved())
        self.assertIsNotNone(user.messages.by_type('MSG_ACH_SPECIES_TAG_3'))

    # Test achieving the 3 different species same target achievement when all of the species identified
    # have fully available species data.
    def test_three_different_species_same_target_achievement_immediate(self):
        # Identify the 3 species that will be identified together in separate targets so that their species data
        # can be fully available when identified together.
        self.create_target_and_move(**points.FIRST_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        # Use a TOO_FAR species to execise/reproduce a bug in the early version of this code which wasn't looking
        # up all the species in user.species first and causing a key error.
        self.check_species(check_species_url, [rects.SPC_PLANT001, rects.SPC_PLANT002, rects.SPC_PLANT_TOO_FAR])
        self.create_target_and_move(**points.SECOND_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.check_species(check_species_url, [rects.SPC_PLANT003])
        # Advance the game to be sure that all species data is now fully available.
        self.advance_game(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)

        # The achievement and message should not be achieved or sent.
        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_SPECIES_TAG_3'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_SPECIES_TAG_3'))
        # Now identify the same 3 species together in the same photo.
        self.create_target_and_move(**points.THIRD_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        # Tag 3 unique species in the same target.
        self.check_species(check_species_url, [rects.SPC_PLANT001, rects.SPC_PLANT002, rects.SPC_PLANT003])

        # The achievement and message should be achieved and delivered immediately.
        user = self.get_logged_in_user()
        self.assertTrue(user.achievements['ACH_SPECIES_TAG_3'].was_achieved())
        self.assertIsNotNone(user.messages.by_type('MSG_ACH_SPECIES_TAG_3'))

    # Test achieving the 5 total animals achievement, only when some of the species identified have delayed
    # species data as this is realistically the only likely situation (even though the code handles immediately
    # available species data as well).
    def test_five_distinct_animals_achievement(self):
        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_SPECIES_ANIMAL_5'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_SPECIES_ANIMAL_5'))

        animal_rects = [rects.for_species_key(s_key) for s_key in rects.ANIMALS[0:5]]
        # Tag 3 animals in the first target.
        self.create_target_and_move(**points.FIRST_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.check_species(check_species_url, animal_rects[0:3])

        # And two more in the second target.
        self.create_target_and_move(**points.SECOND_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.check_species(check_species_url, animal_rects[3:5])

        # The achievement is still not achieved because some of the species data was delayed for first identification.
        user = self.get_logged_in_user()
        self.assertFalse(user.achievements['ACH_SPECIES_ANIMAL_5'].was_achieved())
        self.assertIsNone(user.messages.by_type('MSG_ACH_SPECIES_ANIMAL_5'))

        # Advance the game so that all species data is now fully available, which should also achieve the badge and
        # deliver the message.
        self.advance_game(minutes=Constants.MAX_SPECIES_DELAY_MINUTES)
        user = self.get_logged_in_user()
        self.assertTrue(user.achievements['ACH_SPECIES_ANIMAL_5'].was_achieved())
        self.assertIsNotNone(user.messages.by_type('MSG_ACH_SPECIES_ANIMAL_5'))

    # Test that creating a target during all of the special date achievement days results in an acheivement
    # being created.
    def test_special_date_achievements(self):
        # Set the time to be January 1st of whatever next year is and then iterate through each special date achievement
        # setting the wallclock to be the start of the special date month and day.
        start_date = datetime(gametime.now().year + 1, 1, 1, 0, 0, 0)
        gametime.set_now(start_date)

        for index, achievement_key in enumerate(achievement.get_special_date_achievement_keys()):
            point = points.by_index(index)
            callback_class = get_callback_class(ACHIEVEMENT_CB, achievement_key)

            # Set the gametime to be the start of the special date window in the current year.
            special_date = datetime(gametime.now().year, callback_class.MONTH, callback_class.DAY_OF_MONTH, 0, 0, 0)
            # Assert that we are only moving time forward.
            self.assertTrue(special_date >= gametime.now())
            gametime.set_now(special_date)

            # Assert the given achievement is not yet achieved.
            self.assertFalse(self.get_logged_in_user().achievements[achievement_key].was_achieved())

            # Now create and arrive at a target during the special date day, which should achieve the achievement.
            self.create_target_and_move(**point)
            self.assertTrue(self.get_logged_in_user().achievements[achievement_key].was_achieved())

            if index == 0:
                # After the first target, tag the lander to remove RGN_TAG_LANDER01_CONSTRAINT.
                target = self.get_most_recent_target_from_gamestate()
                check_species_url = str(target['urls']['check_species'])
                self.check_species(check_species_url, [rects.SPC_LANDER01])
