# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import inspect
import os, sys, termstyle

from front.models import chips
from front.lib import gametime
from front import debug
from front.debug import story

from front.tests import base

class GameTestBeat(story.StoryBeatInterface):
    # Override this to create the next N targets past this beat after it has been moved to.
    # Note that this is a 'relative' value, it factors in the previous beats values. So if beat
    # A sets this to 2 and the next beat, beat B, sets this to 2, then B and B+1 will be created
    # when the story moves to A, but when it moves to B, only B+2 will be created, since B+1 was
    # already created.
    CREATE_NEXT_TARGETS = 0

    # For adhoc Beats, define how much time is spent before moving to that Beat (how long to wait at
    # the previous Beat) and how long it takes to arrive at that Beat.
    # (how much the game should be advanced before LEAVE and ARRIVED)
    BEAT_START_DELAY = None
    BEAT_ARRIVAL_DELTA = None

    # For adhoc Beats, if that given point in the story creates a target directly (not from user input) then
    # this flag will inform the system to render that server created target
    RENDER_ADHOC_TARGET = False

    # Set this to True to signal to the system that the target that is created at this beat will be
    # neutered by the engine. E.g. it will not be rendered and eventually deleted by a later process.
    TARGET_WILL_BE_NEUTERED = False

    # Set this to True to signal to the system that the target that is created at this beat will be
    # marked classified by the real renderer and thus should be mark classified in the tests.
    TARGET_MARK_CLASSIFIED = False

    # A flag to mark a beat subclass as adhoc. Set by the system, not by the user.
    _is_adhoc_beat = False

    # These are the valid moments in time when a GameTestBeat.Move can make assertions about
    # the gamestate. Add a GameTestBeat.Move subclass within the GameTestBeat named after the
    # Point.name to make assertions for that moment in time.
    # e.g.
    #
    # class POINT_NAME(GameTestBeat):
    #     class ARRIVED(GameTestBeat.Move):
    #         @classmethod
    #         def assertions(cls, test, target_struct):
    #             test.assert...
    class moves(object):
        CREATED      = "CREATED"
        ARRIVED      = "ARRIVED"
        LEAVE        = "LEAVE"
        ARRIVED_NEXT = "ARRIVED_NEXT"
        ALL = set([CREATED, ARRIVED, LEAVE, ARRIVED_NEXT])

    class Move(object):
        # These list user actions to perform at the moment in time described by this
        # GameTestBeat.Move subclass.
        # List of species ids to identify at this Move.
        id_species        = []
        # List of msg_types to unlock at this Move.
        messages_unlock   = []
        # List of client side progress keys to achieve at this Move.
        client_progress   = []

        # Define these to validate properties of the gamestate at the moment in time described
        # by this GameTestBeat.Move subclass.
        target_sounds     = []
        not_done_missions = []
        done_missions     = []
        present_regions   = []
        absent_regions    = []
        messages_new      = []
        messages_forward  = []
        progress_new      = []
        achieved_new      = []
        available_capabilities = []

        @classmethod
        def species_was_identified(cls, test, target_struct, result):
            """ Called after a species identification request is performed, if id_species was non-empty. """
            pass

        @classmethod
        def assertions(cls, test, target_struct, gamestate, chips_struct):
            """ Define this method to perform any custom assertions at the moment in time this
                GameTestBeat.Move defined. """
            pass

        @classmethod
        def password_to_unlock_message(cls, message, test, gamestate):
            """ Define this method to return the password required to unlock the provided message gamestate
                object, as triggered by defining a value in messages_unlock. """
            return ""

        ## Internal methods, which consume the gamestate class variables above (e.g. done_missions). Not
        # intented to be overridden.
        @classmethod
        def validate_gamestate(cls, test, target_struct, gamestate, chips_struct):
            # Refresh the target information from the gamestate as the data attached to the
            # Point might have gotten stale.
            t = test.get_target_from_gamestate(target_struct['target_id'], gamestate)
            if t is not None:
                if '_render_result' in target_struct:
                    t['_render_result'] = target_struct['_render_result']
                target_struct = t

            # Peform the gamestate assertions using the loaded gamestate data.
            test.assert_target_sounds(detected=cls.target_sounds, target_struct=target_struct, chips_struct=chips_struct)
            test.assert_mission_status(not_done=cls.not_done_missions,
                                       done=cls.done_missions, gamestate=gamestate, chips_struct=chips_struct)
            test.assert_region_list(present=cls.present_regions,
                                    absent=cls.absent_regions, gamestate=gamestate, chips_struct=chips_struct)
            test.assert_message_list(present=cls.messages_new, gamestate=gamestate, chips_struct=chips_struct)
            test.assert_progress_list(present=cls.progress_new, gamestate=gamestate, chips_struct=chips_struct)
            test.assert_achievements_list(achieved=cls.achieved_new, ignore=test.ACHIEVEMENTS_IGNORE, gamestate=gamestate, chips_struct=chips_struct)
            test.assert_capabilities_list(available=cls.available_capabilities, gamestate=gamestate, chips_struct=chips_struct)

        @classmethod
        def identify_species(cls, test, target_struct):
            if cls.id_species != []:
                # Perform the species identification if any were requested, then capture and verify
                # the chips result.
                check_species_url = str(target_struct['urls']['check_species'])
                rects = [base.rects.for_species_key(species_key) for species_key in cls.id_species]
                result = test.check_species(check_species_url, rects)
                species_chips = test.chips_for_path(['user', 'species', '*'], result)
                # NOTE: These chips can either be ADDs or MODs. Consider adding more assertions later.
                # Could track all species seen, and when new expect ADD and existing expect MOD and
                # changes (known target_struct.target_id) to the target_ids mapping?
                species_keys = set([c['value']['key'] for c in species_chips if c['action'] == chips.ADD])
                # The id_species list contains rectangle keys, which map to a species key unless they
                # include a _SUB* suffix in which case they refer to a subspeciess. Remove any _SUB* suffix
                # so that species keys are compared with species keys (ignoring subspecies)
                id_species_keys = set([key.partition('_SUB')[0] for key in cls.id_species])
                if len(species_keys) > 0:
                    test.assertTrue(species_keys.issubset(id_species_keys),
                        "Unexpected newly detected species. [%s]" % species_keys.difference(id_species_keys))

                # Inform the callback so that this Move may optionally perform additional assertions.
                cls.species_was_identified(test, target_struct, result)

        @classmethod
        def mark_new_messages_read(cls, test, gamestate):
            for msg_type in cls.messages_new:
                # Currently we are assuming there is only one message per msg_type in the gamestate, however
                # this code will attempt to read every message that matches the msg_type in messages_new.
                for message in gamestate['user']['messages'].itervalues():
                    if message['msg_type'] == msg_type:
                        body_url = str(message['urls']['message_content'])
                        response = test.json_get(body_url)
                        # Some content_html should have been returned.
                        test.assertTrue(len(response['content_html']) > 0)

                        # The message should have been marked read and had a MOD chip.
                        message_chips = test.chips_for_path(['user', 'messages', message['message_id']], response)
                        # The ADD chip might have been caught up in this.
                        test.assertTrue(len(message_chips) > 0)
                        read_chip = message_chips[-1]
                        test.assertEqual(read_chip['action'], chips.MOD)
                        test.assertIsNotNone(read_chip['value']['read_at'])

        @classmethod
        def mark_messages_unlocked(cls, test, gamestate):
            for msg_type in cls.messages_unlock:
                # Currently we are assuming there is only one message per msg_type in the gamestate, however
                # this code will attempt to read every message that matches the msg_type in messages_unlock.
                for message in gamestate['user']['messages'].itervalues():
                    if message['msg_type'] == msg_type:
                        unlock_url = str(message['urls']['message_unlock'])
                        password = cls.password_to_unlock_message(message, test, gamestate)
                        payload = {'password':password}
                        response = test.json_post(unlock_url, payload)
                        test.assertTrue(response['was_unlocked'], "Failed to unlock message %s with password %s" % (msg_type, password))

                        # content_html should have been returned.
                        test.assertTrue(len(response['content_html']) > 0)
                        # The message should have been marked unlocked and had a MOD chip.
                        message_chips = test.chips_for_path(['user', 'messages', message['message_id']], response)
                        # The ADD chip might have been caught up in this.
                        test.assertTrue(len(message_chips) > 0)
                        unlock_chip = message_chips[-1]
                        test.assertEqual(unlock_chip['action'], chips.MOD)
                        test.assertEqual(unlock_chip['value']['locked'], 0)

        @classmethod
        def forward_messages(cls, test, gamestate):
            for msg_type, recipient in cls.messages_forward:
                # Currently we are assuming there is only one message per msg_type in the gamestate, however
                # this code will attempt to read every message that matches the msg_type in messages_forward.
                for message in gamestate['user']['messages'].itervalues():
                    if message['msg_type'] == msg_type:
                        forward_url = str(message['urls']['message_forward'])
                        payload = {'recipient':recipient}
                        response = test.json_post(forward_url, payload)
                        test.assertIsNotNone(response)

        @classmethod
        def achieve_client_progress(cls, test, gamestate):
            for progress_key in cls.client_progress:
                test.create_client_progress_key(str(gamestate['urls']['create_progress']), progress_key)

    ## story.StoryBeatInterface callback implementations to dispatch the callback event
    # to the correct GameTestBeat.Move inner class, if defined.
    @classmethod
    def create_next_targets(cls, test, target_struct, point):
        return cls.CREATE_NEXT_TARGETS

    @classmethod
    def created_target(cls, test, target_struct, point):
        # If this beat is signaling that this target is going to be neutered, then insert that
        # information into the target_struct so that the target rendering assertions know that
        # this target is not going to be rendered.
        if cls.TARGET_WILL_BE_NEUTERED:
            target_struct['_target_will_be_neutered'] = True
        # If this beat is signaling that this target would be marked classifed by real renderer, then insert that
        # information into the target_struct so that the test target rendering system knows to mark
        # this target as classified.
        if cls.TARGET_MARK_CLASSIFIED:
            target_struct['_target_mark_classified'] = True

        cls._run_move_actions(cls.moves.CREATED, test, target_struct)

    @classmethod
    def moving_to_target(cls, test, target_struct, point):
        # If there is an adhoc beat to run before this current beat, run it now.
        beat = test._adhoc_beats_before.get(cls)
        if beat is not None:
            cls._run_adhoc_beat(beat, test, target_struct, point)

    @classmethod
    def leaving_target(cls, test, target_struct, point):
        cls._run_move_actions(cls.moves.LEAVE, test, target_struct)

        # If there is an adhoc beat to run after this current beat, run it now.
        beat = test._adhoc_beats_after.get(cls)
        if beat is not None:
            cls._run_adhoc_beat(beat, test, target_struct, point)

    @classmethod
    def left_target(cls, test, target_struct, point):
        cls._run_move_actions(cls.moves.ARRIVED_NEXT, test, target_struct)

    @classmethod
    def moved_to_target(cls, test, target_struct, point):
        # Validate that only adhoc beats are setting the delay and arrival values.
        if not cls._is_adhoc_beat:
            if cls.BEAT_ARRIVAL_DELTA is not None or cls.BEAT_START_DELAY is not None:
                raise Exception("Only adhoc beats can set BEAT_ARRIVAL_DELTA or BEAT_START_DELAY [%s]" % cls)

        cls._run_move_actions(cls.moves.ARRIVED, test, target_struct)

    @classmethod
    def extra_duration(cls, test):
        duration = 0
        # If this beat has previous or next adhoc beats, ask for their extra_duration.
        # NOTE: This might go down a chain of adhoc beats connected to adhoc beats.
        beat = test._adhoc_beats_after.get(cls)
        if beat is not None:
            duration += beat.extra_duration(test)
        beat = test._adhoc_beats_before.get(cls)
        if beat is not None:
            duration += beat.extra_duration(test)
        # If this beat is itself an adhoc beat, add in any start or arrival values.
        if cls._is_adhoc_beat:
            if cls.BEAT_START_DELAY is not None:
                duration += cls.BEAT_START_DELAY
            if cls.BEAT_ARRIVAL_DELTA is not None:
                duration += cls.BEAT_ARRIVAL_DELTA
        return duration

    @classmethod
    def _run_adhoc_beat(cls, beat, test, target_struct, point):
        # CREATED is not supported on adhoc beats.
        if hasattr(beat, GameTestBeat.moves.CREATED):
            raise Exception("CREATED not supported for adhoc beats.")

        # If there is a BEAT_START_DELAY defined then tick the game.
        if beat.BEAT_START_DELAY is not None:
            test.advance_game(seconds=beat.BEAT_START_DELAY)
            # See comment below in advanced_story_by that explains this.
            gametime.restore_tick()

        # Adhoc Beats are really just ticking time, so just use whatever is the most recent target in the
        # gamestate as the target_struct data. Reload the target_struct each time to grab any changes
        # that might have happened during a previous adhoc beat in the chain.
        # NOTE: In the case where an adhoc beat (some given point in the story) is actually creating a
        # target directly without user input, this target_struct might in fact be the data for that adhoc target.
        target_struct = test.get_most_recent_target_from_gamestate()

        # Trigger the moving_to at beat events.
        beat.moving_to_target(test, target_struct, None)

        # If the adhoc beat indicates it is going to create a target on its own, then render it.
        if beat.RENDER_ADHOC_TARGET:
            # If this beat is signaling that this target would be marked classifed by real renderer, then insert that
            # information into the target_struct so that the test target rendering system knows to mark
            # this target as classified.
            if beat.TARGET_MARK_CLASSIFIED:
                target_struct['_target_mark_classified'] = True
            test.render_target(target_struct, point=point)

        # Tick the game if BEAT_DURATION_SECONDS was defined.
        if beat.BEAT_ARRIVAL_DELTA is not None:
            test.advance_game(seconds=beat.BEAT_ARRIVAL_DELTA)
            # See comment below in advanced_story_by that explains this.
            gametime.restore_tick()

        # Trigger the arrived at beat events.
        beat.moved_to_target(test, target_struct, None)

        # Trigger the leaving and left beat events.
        beat.leaving_target(test, target_struct, None)
        beat.left_target(test, target_struct, None)

    @classmethod
    def _run_move_actions(cls, move_name, test, target_struct, chips_seconds_ago=None):
        try:
            move_class = getattr(cls, move_name)
        except AttributeError:
            return None

        # If the test has been configured to be vebose, print each Beat and Move.
        if test.VERBOSE:
            if cls.__name__ not in test._visited_beats:
                if len(test._visited_beats) == 0:
                    print
                else:
                    print "... " + termstyle.green("passed")
                print "  test_" + cls.__name__,
            # NOTE: An even more verbose version can be obtained by commenting this line in.
            # Be aware that there is a known issue if targets are created more than one at a time
            # (using CREATE_NEXT_TARGETS) then the order of the move_name output is broken and it
            # will appear that multiple ARRIVED/ARRIVED_NEXT events happened for the same move.
            # print move_name,
            # Flush stdout so each message appears immediately.
            sys.stdout.flush()

        # Record that we 'visited' this GameTestBeat subclass at least once.
        test._visited_beats.add(cls.__name__)

        try:
            # Load a single copy of the gamestate to be used by all assertions.
            # Skip gamestate validation is it significantly slows down this test.
            gamestate = test.get_gamestate(skip_validation=True)

            # Request all chips that were generated between now and chips_seconds_ago so that assertions can be
            # made about what chips were expected.
            # Note that by default chips_seconds_ago is None which means it will just use the
            # most recent value of last_seen_chip_time from the client unless overriden when this method
            # is called, such as for the first Beat in the story.
            chips_struct = test.fetch_chips(seconds_ago=chips_seconds_ago)

            # Validate the gamestate, perform species identifications and mark new messages read,
            # and run any custom additional assertions for this Move.
            move_class.validate_gamestate(test, target_struct, gamestate, chips_struct)
            move_class.identify_species(test, target_struct)
            move_class.mark_new_messages_read(test, gamestate)
            move_class.mark_messages_unlocked(test, gamestate)
            move_class.forward_messages(test, gamestate)
            move_class.achieve_client_progress(test, gamestate)
            move_class.assertions(test, target_struct, gamestate, chips_struct)

        except Exception, e:
            # Annotate the Exception with some test specific information.
            if hasattr(e, 'args'):
                error_msg = "\n\n>>> Test failed in %s.%s\n" % (cls.__name__, move_name)
                # Add the original exception error message if it exists.
                if len(e.args) > 0:
                    error_msg = str(e.args[0]) + error_msg
                e.args = (error_msg,)
            raise

class StoryTestCase(base.TestCase, story.StoryDelegateInterface):
    # Override and define the filenames of the json files in the debug/routes directory to be used
    # when running the story for this test case.
    ROUTE_FILES = []

    # Optionally override the username and password for the user to create for this test.
    TEST_USER = ('testuser@example.com', 'password')

    # Optionally define this to be a GameTestBeat class instance which should be arrived at
    # before any beats in the story.
    # The target_struct value will be whatever the most recent target is at the start of the story.
    START_BEAT = None

    # If true, each beat and move will be echoed to stdout as it is visited.
    VERBOSE = True

    # List of ACH_ achievement keys which should be ignored when asserting when acheivements are achieved.
    # This was put in place so that special date based acheivements could be ignored as they would cause
    # inconsistent results based on what day of the year the tests were run on.
    ACHIEVEMENTS_IGNORE = []

    # Tracks Beats that are added adhoc to the story, e.g. not defined in the Route/Story JSON data.
    # These dicts maps the Beat that the adhoc Beat is supposed to be run before or after (can be another adhoc Beat)
    _adhoc_beats_before = {}
    _adhoc_beats_after = {}

    def setUp(self):
        super(StoryTestCase, self).setUp()
        route_structs = [debug.routes.struct(file_name) for file_name in self.ROUTE_FILES]
        self._story = story.Story(route_structs, delegate=self, beats=[self])
        # Calculate how many seconds ago the first route point should have been created.
        starting_time = self._story.duration()

        # Roll back time to factor in the route elapsed duration before creating the user so that the
        # initial targets (lander and first photos) have the correct times relative to the start
        # of the route.
        debug.rewind_now(seconds=starting_time)
        self.create_validated_user(*self.TEST_USER)

        # Clear out the list of GameTestBeat classes that were visited.
        self._visited_beats = set()

        # Clear out the list of missions being tracked.
        self._not_done_missions = set()
        self._done_missions = set()
        # Clear out the list of regions being tracked.
        self._present_regions = set()
        self._absent_regions = set()
        # Clear out the list of message being tracked.
        self._present_messages = set()
        # Clear out the list of progress keys being tracked.
        self._present_progress = set()
        # Clear out the list of achievements being tracked.
        self._achieved_achievements = set()
        # Clear out the list of capabilities being tracked.
        self._available_capabilities = set()

    def test_run_story(self):
        # If there is an initial start beat defined, run it now.
        if self.START_BEAT is not None:
            # For the first call to START_BEAT.ARRIVED, all chips created between the creation of the user and
            # now will be included in the chips_struct which is the number of seconds since user.epoch.
            chips_seconds_ago = self.get_logged_in_user().epoch_now

            target_struct = self.get_most_recent_target_from_gamestate()
            self.START_BEAT._run_move_actions(GameTestBeat.moves.ARRIVED, self, target_struct, chips_seconds_ago=chips_seconds_ago)
            self.START_BEAT._run_move_actions(GameTestBeat.moves.LEAVE, self, target_struct)
            self._visited_beats.add('START_BEAT')
            self._visited_beats.add(self.START_BEAT.__name__)

        # Find all of the defined Beats for this test. Assert that only known
        # Move types are defined (mainly to catch typos in Move names.)
        all_beats = set()
        for beat_name, beat_class in inspect.getmembers(self):
            if inspect.isclass(beat_class) and issubclass(beat_class, GameTestBeat):
                for move_name, move_class in beat_class.__dict__.iteritems():
                    if inspect.isclass(move_class) and issubclass(move_class, GameTestBeat.Move):
                        if move_name not in GameTestBeat.moves.ALL:
                            raise Exception("%s is not a known GameTestBeat.Move type in %s." % (move_name, beat_name))
                all_beats.add(beat_name)

        # Optionally a TO_POINT environmental variable can be set and this test
        # will only run the story to that point.
        to_point = os.getenv('TO_POINT', None)
        # Start the story.
        self._story.play(to_point=to_point)

        # If we did not run to a specific point, then assert that every GameTestBeat defined in this
        # subclass was visited.
        if to_point is None:
            not_visited = all_beats.difference(self._visited_beats)
            # Fail the test and enumerate the GameTestBeats that were not visited. One reason this might happen
            # is if there is a slightly misnamed GameTestBeats subclass to the corresponding Point name in the
            # route data e.g. POINT1 vs. POINT01
            if len(not_visited) > 0:
                self.fail("Some GameTestBeats were not visited: %s" % not_visited)

    @classmethod
    def before_beat_run_beat(cls, before, beat):
        assert before not in cls._adhoc_beats_before, "Adhoc Beat can only be added before a beat once %s, %s" % (before, beat)
        beat._is_adhoc_beat = True
        cls._adhoc_beats_before[before] = beat

    @classmethod
    def after_beat_run_beat(cls, after, beat):
        assert after not in cls._adhoc_beats_after, "Adhoc Beat can only be added after a beat once %s, %s" % (after, beat)
        beat._is_adhoc_beat = True
        cls._adhoc_beats_after[after] = beat

    ## Assertion helpers.
    def assert_target_sounds(self, target_struct, chips_struct, detected=[]):
        sound_keys = set(target_struct['sounds'].keys())
        self.assertEqual(sound_keys, set(detected), "Missing or unexpected target sound detected %s != %s" % (detected, sound_keys))
        self.assert_chips_actions(detected, chips.ADD, ['user', 'rovers', '*', 'targets', '*', 'sounds', '*'], chips_struct)

    def assert_mission_status(self, gamestate, chips_struct, not_done=[], done=[]):
        """ Assert that the mission definitions listed in not_done at not done at this moment in time
            and the same for the done list. This method remembers the lists over the course of the test
            so only deltas need to be checked. Can be re-called to verify nothing has changed since
            the last call. """
        for m_def in not_done:
            self.assert_(m_def not in self._done_missions, "Not-done mission should not have been in done: %s" % m_def)
            self.assert_(m_def not in self._not_done_missions, "Not-done mission already checked: %s" % m_def)
            self._not_done_missions.add(m_def)
        for m_def in done:
            self.assert_(m_def not in self._done_missions, "Done mission already checked %s" % m_def)
            self._done_missions.add(m_def)
            self.assert_(m_def in self._not_done_missions, "Done mission should have been in not-done %s" % m_def)
            self._not_done_missions.remove(m_def)

        not_done_state = set([m['mission_definition'] for m in gamestate['user']['missions'].values() if m['done'] == 0])
        done_state = set([m['mission_definition'] for m in gamestate['user']['missions'].values() if m['done'] == 1])
        self.assertEqual(not_done_state, self._not_done_missions)
        self.assertEqual(done_state, self._done_missions)

        # Filter the ADD chips for new not done missions and MOD chips for done missions.
        key_func = lambda chip: chip['path'][-1].split('-')[0]
        not_done_chips = self.assert_chips_actions(not_done, chips.ADD, ['user', 'missions', '*'], chips_struct, key_func=key_func)
        done_chips = self.assert_chips_actions(done, chips.MOD, ['user', 'missions', '*'], chips_struct, key_func=key_func)

        # Perform some assertions on the mission chips.
        for chip in done_chips:
            self.assertEqual(chip['value']['done'], 1, "Missions in done list should have MOD chip marking done field '1'.")

            # The chip's mission_def must be listed the 'done' list.
            mission_def = chip['value']['mission_id'].split('-')[0]
            self.assert_(mission_def in done, "Done mission chip not listed in done missions: %s" % mission_def)

            # Make sure the regions_ids lists look correct (every item listed is also in the user.regions collection)
            if 'region_ids' in chip['value']:
                for r_id in chip['value']['region_ids']:
                    self.assert_(r_id in gamestate['user']['regions'], "region_ids key should be in user.regions: %s" % r_id)

        for chip in not_done_chips:
            # Make sure the regions_ids lists look correct (every item listed is also in the user.regions collection)
            if 'region_ids' in chip['value']:
                for r_id in chip['value']['region_ids']:
                    self.assert_(r_id in gamestate['user']['regions'], "region_ids key should be in user.regions: %s" % r_id)

            # The chip's mission_def must be listed the 'not_done' list.
            mission_def = chip['value']['mission_definition']
            self.assert_(mission_def in not_done, "New mission chip not listed in not_done missions: %s" % mission_def)

    def assert_region_list(self, gamestate, chips_struct, present=[], absent=[]):
        for r_id in present:
            self.assert_(r_id not in self._present_regions, "Present region should not have already been present: %s" % r_id)
            self.assert_(r_id not in self._absent_regions, "Present region should not already be absent: %s" % r_id)
            self._present_regions.add(r_id)
        for r_id in absent:
            self.assert_(r_id not in self._absent_regions, "Absent region already checked: %s" % r_id)
            self._absent_regions.add(r_id)
            self.assert_(r_id in self._present_regions, "Absent region should have been present: %s" % r_id)
            self._present_regions.remove(r_id)

        present_state = set(gamestate['user']['regions'].keys())
        self.assertEqual(present_state, self._present_regions)
        self.assert_(present_state.isdisjoint(self._absent_regions))

        self.assert_chips_actions(present, chips.ADD, ['user', 'regions', '*'], chips_struct)
        self.assert_chips_actions(absent, chips.DELETE, ['user', 'regions', '*'], chips_struct)

    def assert_message_list(self, gamestate, chips_struct, present=[]):
        for m_type in present:
            self.assert_(m_type not in self._present_messages,
                         "Present message type should not have already been present: %s" % m_type)
            self._present_messages.add(m_type)

        present_state = set([m['msg_type'] for m in gamestate['user']['messages'].values()])
        self.assertEqual(present_state, self._present_messages)

        key_func = lambda chip: chip['value']['msg_type']
        self.assert_chips_actions(present, chips.ADD, ['user', 'messages', '*'], chips_struct, key_func=key_func)

    def assert_progress_list(self, gamestate, chips_struct, present=[]):
        for p_key in present:
            self.assert_(p_key not in self._present_progress,
                         "Present progress key should not have already been present: %s" % p_key)
            self._present_progress.add(p_key)

        present_state = set(gamestate['user']['progress'].keys())
        self.assertEqual(present_state, self._present_progress)

        self.assert_chips_actions(present, chips.ADD, ['user', 'progress', '*'], chips_struct)

    def assert_achievements_list(self, gamestate, chips_struct, achieved=[], ignore=[]):
        for a_id in achieved:
            self.assert_(a_id not in self._achieved_achievements,
                         "Present achievement_key should not have already been achieved: %s" % a_id)
            self._achieved_achievements.add(a_id)

        present_state = set([a['achievement_key'] for a in gamestate['user']['achievements'].values()
                            if a['achieved_at'] is not None and a['achievement_key'] not in ignore])
        self.assertEqual(present_state, self._achieved_achievements)

        self.assert_chips_actions(achieved, chips.MOD, ['user', 'achievements', '*'], chips_struct)

    def assert_capabilities_list(self, gamestate, chips_struct, available=[]):
        for c_key in available:
            self.assert_(c_key not in self._available_capabilities,
                         "Available capability_key should not have already been made available: %s" % c_key)
            self._available_capabilities.add(c_key)

        present_state = set([c['capability_key'] for c in gamestate['user']['capabilities'].values()
                            if c['available'] == 1])
        self.assertEqual(present_state, self._available_capabilities)

        available_chips = self.assert_chips_actions(available, chips.MOD, ['user', 'capabilities', '*'], chips_struct)
        # Perform some assertions on the capability chips.
        for chip in available_chips:
            self.assertEqual(chip['value']['available'], 1, "Capabilities in available list should have MOD chip marking available field '1'.")

    def assert_chips_actions(self, expected, action, path, struct, key_func=None):
        # Find all chips that match the desired path and have the expected chip action type.
        matched = [c for c in self.chips_for_path(path, struct=struct) if c['action'] == action]
        if key_func is None:
            key_func = lambda chip: chip['path'][-1]
        actions_and_keys = [(chip['action'], key_func(chip)) for chip in matched]
        for key in expected:
            if (action, key) not in actions_and_keys:
                self.fail("Expected chip not found. action=[%s], key=[%s]" % (action, key))
        return matched

    ## StoryDelegate methods
    def create_target_for_point(self, point, relative_arrival_delta):
        # Create a target for this point on whatever the active rover is.
        chips_result = self.create_target(lat=point.lat, lng=point.lng,
                                          yaw=point.yaw, arrival_delta=relative_arrival_delta)
        target_struct = self.last_chip_value_for_path(['user', 'rovers', '*', 'targets', '*'], chips_result)
        point._target_struct = target_struct

    # NOTE: This target_struct is NOT refreshed after creation. If target information changes it will be out of date.
    def target_for_point(self, point):
        return point._target_struct

    def render_target(self, target_struct, point):
        if '_target_mark_classified' in target_struct:
            result = self.render_next_target(classified=1)
        else:
            result = self.render_next_target()
        # Story any JSON results from the render_next_target call in a _render_result key
        # attached to the target_struct.
        target_struct['_render_result'] = result
        # If anything was rendered, check to make sure what was rendered was expected.
        if len(result) > 1:
            (user_id, rover_id, target_id, target_arrival, metadata) = self.renderer_decompose_next_target(result)
            # If the target was neutered, then it should have been deleted and if another target was
            # rendered after that, then it was a target created by the server itself and its target_id
            # should not be the same as the neutered one.
            if '_target_will_be_neutered' in target_struct:
                self.assertNotEqual(target_struct['target_id'], target_id)
            # Otherwise, be sure we rendered the target we were expecting to render.
            else:
                self.assertEqual(target_struct['target_id'], target_id)

    def advanced_story_by(self, seconds, point):
        # Advance the gametime forward and process any deferred actions.
        processed = self.advance_game(seconds=seconds)
        # Restore the gametime tick after advancing the game and freezing time so that chips created
        # during the story beats get microsecond distribution and result in more accurate and useful
        # fetch_chips behavior.
        gametime.restore_tick()

        # Story any processed DeferredRow objects in a _deferred_actions key
        # attached to the Point object.
        if not hasattr(point, '_deferred_actions'):
            point._deferred_actions = []
        point._deferred_actions += processed
