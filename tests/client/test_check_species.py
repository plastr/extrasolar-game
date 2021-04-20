# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os
from collections import Counter

from front import subspecies_types
from front.backend import check_species
from front.data import scene
from front.models import chips, species

from front.tests import base
from front.tests.base import rects, points

# These are the subspecies_id for these subspecies.
SPC_PLANT001_SUB01_ID = subspecies_types.plant.YOUNG
SPC_PLANT001_SUB02_ID = subspecies_types.plant.DEAD

class TestCheckSpecies(base.TestCase):
    def setUp(self):
        super(TestCheckSpecies, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    def test_check_species_multiple_selections(self):
        ## Identify a species followed by another at the same target to test adding selections.
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Verify the species have not been identified.
        found_species = self.get_gamestate()['user']['species']
        self.assertEqual(len(found_species), 0)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT001"])

        # Verify the species chips.
        species_id_one = species.get_id_from_key("SPC_PLANT001")
        chip = self.last_chip_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['action'], chips.ADD)
        chip_value = chip['value']
        self.assertEqual(chip_value['species_id'], species_id_one)
        self.assertEqual(len(chip_value['target_ids']), 1)
        # And check the species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)
        self.assertIsNotNone(found_species[str(species_id_one)])

        # Now identify another species at the same target location.
        result = self.check_species(check_species_url, [rects.SPC_PLANT004])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT001", "SPC_PLANT004"])

        # Verify the species chips.
        species_id_two = species.get_id_from_key("SPC_PLANT004")
        chip = self.last_chip_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['action'], chips.ADD)
        chip_value = chip['value']
        self.assertEqual(chip_value['species_id'], species_id_two)
        self.assertEqual(len(chip_value['target_ids']), 1)
        # And check the species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 2)
        self.assertIsNotNone(found_species[str(species_id_two)])

    def test_check_species_same_species(self):
        ## Identify a the same species more than once at the same target.
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001, rects.SPC_PLANT001])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT001", "SPC_PLANT001"])

    def test_check_species_with_subspecies(self):
        ## Identify a species that has subspecies data and check the results.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001_SUB01])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT001"], [SPC_PLANT001_SUB01_ID])

        # Verify the species chips.
        species_id = species.get_id_from_key("SPC_PLANT001")
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        # The name and description should not yet be available to the user.
        self.assertTrue("Pending" in chip['name'])
        self.assertEqual(len(chip['target_ids']), 1)
        # The subspecies collection should have an initial entry in the species ADD chip.
        # There will not be a seperate ADD chip for the subspecies collection.
        self.assertEqual(len(chip['subspecies']), 1)
        self.assertTrue(len(chip['subspecies'][str(SPC_PLANT001_SUB01_ID)]['name']) > 0)

        # And check the species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)
        found = found_species[str(species_id)]
        # The name and description should not yet be available to the user.
        self.assertTrue("Pending" in found['name'])
        self.assertEqual(len(found['subspecies']), 1)
        self.assertTrue(len(found['subspecies'][str(SPC_PLANT001_SUB01_ID)]['name']) > 0)

    def test_check_species_then_subspecies(self):
        ## Identify a species that has no subspecies data and then identify that same species,
        #  this time with subspecies data and check the results.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001])

        # Check the non subspecies version of the species.
        self._assert_image_rects(result, ["SPC_PLANT001"])
        species_id = species.get_id_from_key("SPC_PLANT001")
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)

        # Now create a new target and at this target identify the same species, this time
        # with subspecies data.
        self.create_target_and_move(**points.SECOND_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001_SUB01])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT001"], [SPC_PLANT001_SUB01_ID])

        # Verify the species chips.
        species_id = species.get_id_from_key("SPC_PLANT001")
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        self.assertEqual(len(chip['target_ids']), 2)
        # And there should be an ADD chip for the subspecies collection.
        chip = self.last_chip_value_for_path(['user', 'species', species_id, 'subspecies', '*'], result)
        self.assertEqual(chip['subspecies_id'], SPC_PLANT001_SUB01_ID)
        self.assertTrue(len(chip['name']) > 0)

        # And check the species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)
        found = found_species[str(species_id)]
        # The name and description should not yet be available to the user.
        self.assertTrue("Pending" not in found['name'])
        # The subspecies should now be in the species.subspecies collection.
        self.assertEqual(len(found['subspecies']), 1)
        self.assertTrue(len(found['subspecies'][str(SPC_PLANT001_SUB01_ID)]['name']) > 0)

    def test_check_species_with_multiple_subspecies(self):
        ## Identify a species that has multiple subspecies and check the results.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001_SUB01, rects.SPC_PLANT001_SUB02])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT001", "SPC_PLANT001"], [SPC_PLANT001_SUB01_ID, SPC_PLANT001_SUB02_ID])

        # Verify the species chips.
        species_id = species.get_id_from_key("SPC_PLANT001")
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        self.assertEqual(len(chip['subspecies']), 2)
        self.assertTrue(len(chip['subspecies'][str(SPC_PLANT001_SUB01_ID)]['name']) > 0)
        self.assertTrue(len(chip['subspecies'][str(SPC_PLANT001_SUB02_ID)]['name']) > 0)
        
        # And check the species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)
        found = found_species[str(species_id)]
        self.assertEqual(len(found['subspecies']), 2)
        self.assertTrue(len(found['subspecies'][str(SPC_PLANT001_SUB01_ID)]['name']) > 0)
        self.assertTrue(len(found['subspecies'][str(SPC_PLANT001_SUB02_ID)]['name']) > 0)

    def test_check_species_plant_delayed_data(self):
        ## New organic species description data should be delayed in the client gamestate.
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Verify the lander has not been identified.
        found_species = self.get_gamestate()['user']['species']
        self.assertEqual(len(found_species), 0)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT006])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT006"])

        # Verify the species chips.
        species_id = species.get_id_from_key("SPC_PLANT006")
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        self.assertEqual(len(chip['target_ids']), 1)
        self.assertEqual(len(chip['subspecies']), 0)
        # The name and description should not yet be available to the user.
        self.assertTrue("Pending" in chip['name'])
        self.assertIsNone(chip['science_name'])
        self.assertTrue("PENDING" in chip['icon'])
        # And check the species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)
        found = found_species[str(species_id)]
        # The name and description should not yet be available to the user.
        self.assertTrue("Pending" in found['name'])
        self.assertIsNone(found['science_name'])
        self.assertTrue("PENDING" in found['icon'])
        self.assertEqual(len(found['target_ids']), 1)
        self.assertEqual(len(found['subspecies']), 0)

        # After a short duration, the real name and description should now be available to the user.
        self.advance_now(minutes=30)
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        found = found_species[str(species_id)]
        self.assertTrue("Purple" in found['name'])
        self.assertTrue("Pseudoyucca" in found['science_name'])
        self.assertTrue("PENDING" not in found['icon'])

        # Should also have been a MOD chip passing in the real name and description.
        chip = self.last_chip_for_path(['user', 'species', '*'])
        self.assertEqual(chip['value']['species_id'], species_id)
        self.assertEqual(chip['action'], chips.MOD)
        self.assertTrue("Purple" in chip['value']['name'])
        self.assertTrue("Pseudoyucca" in chip['value']['science_name'])
        self.assertTrue("PENDING" not in chip['value']['icon'])

        # Identify the same species at a new target and verify that the user species chip mod looks correct.
        self.create_target_and_move(**points.SECOND_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])

        result = self.check_species(check_species_url, [rects.SPC_PLANT006])
        chip = self.last_chip_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['action'], chips.MOD)
        chip_value = chip['value']
        self.assertEqual(chip_value['species_id'], species_id)
        # Verify that detecting the same species on different targets creates a new target_ids listing.
        self.assertEqual(len(chip_value['target_ids']), 2)
        self.assertNotEqual(chip_value['target_ids'][0], chip_value['target_ids'][1])

    def test_check_species_manmade(self):
        ## Manmade species description data should be available immediately.
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_LANDER01])

        # Verify there was a chip sent for the user species list.
        species_id = species.get_id_from_key("SPC_LANDER01")
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertEqual(chip['species_id'], species_id)
        self.assertEqual(len(chip['target_ids']), 1)
        # The name and description should be available immediately to the user for manmade objects.
        self.assertTrue("Lander" in chip['name'])

        # Validate the post check_species gamestate.
        gamestate = self.get_gamestate()
        found_species = gamestate['user']['species']
        self.assertEqual(len(found_species), 1)
        found = found_species[str(species_id)]
        # The name and description should be available immediately to the user for manmade objects.
        self.assertTrue("Lander" in found['name'])

        # Since the description is available immediately, there should not have been a MOD chip
        # passing in the real name and description.
        self.advance_now(minutes=30)
        chip = self.last_chip_for_path(['user', 'species', '*'])
        self.assertIsNone(chip)

    def test_checkspecies_too_far(self):
        ## Species that are too far away to be identified should still create an image_rect entry
        ## but no species should be added to user.species collection.
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT_TOO_FAR])

        # Verify there was NO chip sent for the user species list and its not in the gamestate.
        chip = self.last_chip_value_for_path(['user', 'species', '*'], result)
        self.assertIsNone(chip)
        found_species = self.get_gamestate()['user']['species']
        self.assertEqual(len(found_species), 0)
        # Verify the image_rects chips.
        found_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', '*', 'image_rects', '*'], result)
        self.assertEqual(len(found_chips), 1)
        self.assertTrue(species.is_too_far_for_id(found_chips[0]['value']['species_id']))
        # Verify the image_rects gamestate.
        target = self.get_most_recent_target_from_gamestate()
        image_rects = target['image_rects']
        self.assertEqual(len(image_rects), 1)
        self.assertTrue(species.is_too_far_for_id(image_rects['0']['species_id']))

    def test_check_species_no_species(self):
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])

        # Identify a region of the image that contains no valid species.
        result = self.check_species(check_species_url, [rects.NO_SPECIES])
        chip = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*', 'image_rects', 0], result)
        self.assertIsNone(chip['species_id'])
        self.assertIsNone(chip['subspecies_id'])
        self.assertIsNone(chip['density'])

    def test_check_species_multiple_rects(self):
        self.create_target_and_move(**points.FIRST_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        # Check a rectangle that includes more of one plant than the other and make sure the plant
        # with the greater density wins.
        result = self.check_species(check_species_url, [rects.TWO_PLANTS])
        self._assert_image_rects(result, ["SPC_PLANT001"])

        # Check a rectangle that includes less manmade object than animal, where weighting should have the
        # manmade object win.
        result = self.check_species(check_species_url, [rects.ANIMAL_AND_SOME_MANMADE])
        self._assert_image_rects(result, ["SPC_PLANT001", "SPC_LANDER01"])

        # Perform at least one checkspecies call with multiple rects.
        self.create_target_and_move(**points.SECOND_MOVE)
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT001, rects.SPC_PLANT003])
        self._assert_image_rects(result, ["SPC_PLANT001", "SPC_PLANT003"])

    def test_check_species_bad_values(self):
        # Add a new target and render the photo for it.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Send malformed rects to the checkspecies library.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.expect_log('front.resource.target_node', 'Failed to identify species. \[Failed to score image region.*')
        result = self.check_species(check_species_url,
                                    [{"xmin": 0.0, "ymin": 0.0, "xmax": 0.0, "ymax": 0.0}], status=400)
        self.assertEqual(result['errors'], ["Error in species identification."])

        self.create_target(arrival_delta=base.SIX_HOURS, **points.SECOND_MOVE)
        self.advance_now(seconds=base.SIX_HOURS)
        # Render a bad scene location so checkspecies cannot load the image data.
        bogus_scene = scene.define_scene("this_is_a_bogus_scene")
        self.render_next_target(render_scene=bogus_scene)

        # Checkspecies should not be able to load the bogus scene from disk.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.expect_log('front.resource.target_node', 'Failed to identify species. \[Failed loading image.*')
        result = self.check_species(check_species_url, [rects.SPC_PLANT001], status=400)
        self.assertEqual(result['errors'], ["Error in species identification."])

        self.create_target(**points.THIRD_MOVE)
        # Render a bad scene location so checkspecies cannot load the image data. This will
        # execise the cURL code path.
        bogus_url = "http://localhost/no_such_image_unit_testing"
        bogus_scene = scene.Scene(bogus_url, bogus_url, bogus_url, bogus_url, bogus_url, bogus_url)
        self.render_next_target(render_scene=bogus_scene)

        # Checkspecies should not be able to load the bogus image from the web.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        self.expect_log('front.resource.target_node', 'Failed to identify species. \[Failed fetching image.*')
        result = self.check_species(check_species_url, [rects.SPC_PLANT001], status=400)
        self.assertEqual(result['errors'], ["Error in species identification."])

    def test_check_species_panorama_wrap(self):
        # Identify a species with a selection region that wraps around the seam of a 360-degree panorama.
        self.create_target_and_move(**points.FIRST_MOVE)

        # Get the check_species URL for this target and perform the species identification.
        target = self.get_most_recent_target_from_gamestate()
        check_species_url = str(target['urls']['check_species'])
        result = self.check_species(check_species_url, [rects.SPC_PLANT008_WRAP])

        # Verify the image_rects chips and gamestate.
        self._assert_image_rects(result, ["SPC_PLANT008"])

    def _assert_image_rects(self, chips_result, expected_species=[], expected_subspecies=[]):
        # Verify there were the expected chips for the image_rects.
        found_chips = self.chips_for_path(['user', 'rovers', '*', 'targets', '*', 'image_rects', '*'], chips_result)
        self.assertEqual(len(found_chips), len(expected_species))
        # And the gamestate looks correct.
        target = self.get_most_recent_target_from_gamestate()
        image_rects = target['image_rects']
        self.assertEqual(len(image_rects), len(expected_species))

        for seq, species_key in enumerate(expected_species):
            species_id = species.get_id_from_key(species_key)
            if len(expected_subspecies) >= seq + 1:
                subspecies_id = expected_subspecies[seq]
            else:
                subspecies_id = 0

            # There should be an ADD chip.
            chip = found_chips[seq]
            self.assertTrue(chip['action'], chips.ADD)
            chip_value = chip['value']
            self.assertEqual(chip_value['seq'], seq)
            self.assertEqual(chip_value['species_id'], species_id)
            self.assertEqual(chip_value['subspecies_id'], subspecies_id)
            self.assertTrue(chip_value['density'] > 0.0)

            # And an image_rect in the gamestate.
            image_rect = image_rects[str(seq)]
            self.assertEqual(image_rect['seq'], seq)
            self.assertEqual(image_rect['species_id'], species_id)
            self.assertEqual(image_rect['subspecies_id'], subspecies_id)
            self.assertTrue(image_rect['density'] > 0.0)

        return (found_chips, image_rects)

class TestCheckSpeciesScenes(base.TestCase):
    # The density value differs between platforms (linux v. mac at the very least) so allow for some wiggle.
    DENSITY_DELTA = 0.01
    EXPECTED_SCORES = [
        ("scene1.png", [
           [{"xmin": 0.57375, "ymin": 0.4216666666666667, "xmax": 0.7, "ymax": 0.625}, "SPC_PLANT003", 0.12199557572603226],
            [{"xmin": 0.76, "ymin": 0.43833333333333335, "xmax": 0.86, "ymax": 0.61}, "SPC_PLANT003", 0.09342355281114578]
        ])
    ]

    def test_all_check_species_scenes(self):
        expected_scores = [TestCheckSpeciesScenes.ExpectedScores(*scores) for scores in self.EXPECTED_SCORES]
        for expected in expected_scores:
            (rect_scores, error_msg) = check_species._check_species(expected.image_path, expected.rects)
            self.assertIsNone(error_msg)
            self.assertEqual(len(expected.scoring), len(rect_scores))

            detected_species = set()
            for i, rect_score in enumerate(rect_scores):
                # NOTE: Currently target_species_count and all_species_count are empty but they could be populated
                # by data from EXPECTED_SCORES as well.
                rect_score.score_and_select_species(Counter(), Counter())
                detected_species.update(rect_score.detected_species())

                self.assertEqual(rect_score.species_id, expected.scoring[i]['species'][0])
                expected_score = expected.scoring[i]['densities'][0]
                within_delta = abs(rect_score.density - expected_score) < self.DENSITY_DELTA
                self.assertTrue(within_delta, "Expected density not within delta %f. [%f][%f]" % (self.DENSITY_DELTA, expected_score, rect_score.density))

            # Leave this incase we ever go back to having more than one species per rect.
            self.assertEqual(set(expected.expected_species_ids), detected_species)

    class ExpectedScores(object):
        BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
        TEST_SCENES = os.path.join(BASEDIR, "..", "data", "scenes")

        def __init__(self, image_name, rect_scores):
            self.image_path = os.path.join(self.TEST_SCENES, image_name)
            self.rects = []
            self.scoring = []
            self.expected_species_ids = set()
            for i, rect_score in enumerate(rect_scores):
                rect = rect_score[0]
                # Assign a seq number to each rectangle.
                rect['seq'] = i
                self.rects.append(rect)
                # Continue to support under the hood the list of expected species_ids being a list,
                # even though we are moving to a world where there will only be one species per rect.
                species_keys = rect_score[1]
                if not isinstance(species_keys, list):
                    species_keys = [rect_score[1]]
                densities = rect_score[2]
                if not isinstance(densities, list):
                    densities = [rect_score[2]]
                species_ids = [species.get_id_from_key(species_id) for species_id in species_keys]
                self.scoring.append({'species':species_ids, 'densities':densities})
                self.expected_species_ids.update(species_ids)
