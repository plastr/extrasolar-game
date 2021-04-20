#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse
from datetime import timedelta
import inspect

from front import read_config_and_init, debug
from front.lib import db, gametime, utils, xjson, email_module
from front.backend import check_species
from front.models import target as target_module
from front.models import progress as progress_module
from front.models import user as user_module
from front.debug import story

TEST_PASSWORD = "test"
TEST_FIRSTNAME = "Test"
TEST_LASTNAME = "Last"

class ReplayGameBeat(story.StoryBeatInterface):
    """
    This is a base StoryBeat class meant to be used as a convenience when constructing a Story to
    be run by the ReplayGame. It is intended that these subclasses will live in a .py module passed
    to replay_game.
    NOTE: Be sure to call super() if overriding any of the StoryBeatInterface declared below.
    Standard arguments:
        tool - A ReplayGame instance. Intended to expose useful utilites such as identify_species.
        target - The Target instance.
        point - The Point instance.
    """
    # Protect these base beat callback methods from being overriden by subclasses as they perform
    # special functionality in this class and cannot be safely overriden without remembering to call
    # super. Alternative methods are provided below which are called by these original methods
    # should a subclass need to perform activities at those events.
    __metaclass__ = utils.NoOverrideMetaClass
    NO_OVERRIDE = ['create_next_targets', 'moved_to_target', 'leaving_target', 'left_target']

    # A list of species_ids to identify after arriving at this Beat.
    ID_SPECIES = []
    # A list of msg_types to unlock after arriving at this Beat.
    MESSAGES_UNLOCK = []
    # A list of (msg_type, recipient) to forward messages to after arriving at this Beat.
    MESSAGES_FORWARD = []
    # A list of client progress keys to achieve after arriving at this Beat.
    CLIENT_PROGRESS = []

    # The number of targets to create next in the Story before moving away from this Beat.
    # This simulates the user creating multiple new targets at the same time.
    CREATE_NEXT_TARGETS = 0

    # For adhoc Beats, define how much time is spent before moving to that Beat (how long to wait at
    # the previous Beat) and how long it takes to arrive at that Beat.
    # (how much the game should be advanced before leaving/left and moving_to events are fired)
    BEAT_START_DELAY = None
    BEAT_ARRIVAL_DELTA = None

    # For adhoc Beats, if that given point in the story creates a target directly (not from user input) then
    # this flag will inform the system to render that server created target
    RENDER_ADHOC_TARGET = False

    # If an adhoc beat is to be run before or after this beat, these will not be None.
    _prev_adhoc_beat = None
    _next_adhoc_beat = None
    # A flag to mark a beat subclass as adhoc
    _is_adhoc_beat = False

    @classmethod
    def before_beat_run_beat(cls, beat):
        assert cls._prev_adhoc_beat is None, "Only one prev adhoc beat can be added to a given beat."
        beat._is_adhoc_beat = True
        cls._prev_adhoc_beat = beat

    @classmethod
    def after_beat_run_beat(cls, beat):
        assert cls._next_adhoc_beat is None, "Only one next adhoc beat can be added to a given beat."
        beat._is_adhoc_beat = True
        cls._next_adhoc_beat = beat

    # Override these methods in subclasses if additional actions are needed during these events,
    # instead of using the StoryBeatInterface methods below which provide special functionality.
    @classmethod
    def moving_to_beat(cls, tool, target, point):
        pass

    @classmethod
    def arrived_at_beat(cls, tool, target, point):
        pass

    @classmethod
    def leaving_beat(cls, tool, target, point):
        pass

    @classmethod
    def left_beat(cls, tool, target, point):
        pass

    ## StoryBeatInterface methods
    @classmethod
    def create_next_targets(cls, tool, target, point):
        return cls.CREATE_NEXT_TARGETS

    @classmethod
    def moving_to_target(cls, tool, target, point):
        # Call the optional subclass callback.
        cls.moving_to_beat(tool, target, point)

        # If there is an adhoc beat to run before this current beat, run it now.
        if cls._prev_adhoc_beat is not None:
            cls._run_adhoc_beat(cls._prev_adhoc_beat, tool, target, point)

    @classmethod
    def moved_to_target(cls, tool, target, point):
        # Validate that only adhoc beats are setting the delay and arrival values.
        if not cls._is_adhoc_beat:
            if cls.BEAT_ARRIVAL_DELTA is not None or cls.BEAT_START_DELAY is not None:
                raise Exception("Only adhoc beats can set BEAT_ARRIVAL_DELTA or BEAT_START_DELAY [%s]" % cls)

        # Track that this Beat was visited.
        tool._visited_beats.add(cls.__name__)

        # Identify any species.
        if cls.ID_SPECIES != []:
            rects = [debug.rects.for_species_key(species_key) for species_key in cls.ID_SPECIES]
            tool.identify_species(rects, target)
        # Mark any unread messages as read.
        tool.mark_messages_read()
        # Unlock any messages.
        for msg_type in cls.MESSAGES_UNLOCK:
            tool.unlock_message(msg_type)
        # Forward any messages.
        for msg_type, recipient in cls.MESSAGES_FORWARD:
            tool.forward_message(msg_type, recipient)
        # Achieve any client progress keys.
        for progress_key in cls.CLIENT_PROGRESS:
            tool.achieve_client_progress(progress_key)
        # Call the optional subclass callback.
        cls.arrived_at_beat(tool, target, point)

    ADHOC_FORBIDDEN = ['created_target', 'waited_to_create_target', 'moving_to_target_halfway']
    @classmethod
    def leaving_target(cls, tool, target, point):
        # Call the optional subclass callback.
        cls.leaving_beat(tool, target, point)

        # If there is an adhoc beat to run after this current beat, run it now.
        if cls._next_adhoc_beat is not None:
            cls._run_adhoc_beat(cls._next_adhoc_beat, tool, target, point)

    @classmethod
    def left_target(cls, tool, target, point):
        # Call the optional subclass callback.
        cls.left_beat(tool, target, point)

    @classmethod
    def extra_duration(cls, tool):
        duration = 0
        # If this beat has previous or next adhoc beats, ask for their extra_duration.
        # NOTE: This might go down a chain of adhoc beats connected to adhoc beats.
        if cls._next_adhoc_beat is not None:
            duration += cls._next_adhoc_beat.extra_duration(tool)
        if cls._prev_adhoc_beat is not None:
            duration += cls._prev_adhoc_beat.extra_duration(tool)
        # If this beat is itself an adhoc beat, add in any start or arrival values.
        if cls._is_adhoc_beat:
            if cls.BEAT_START_DELAY is not None:
                duration += cls.BEAT_START_DELAY
            if cls.BEAT_ARRIVAL_DELTA is not None:
                duration += cls.BEAT_ARRIVAL_DELTA
        return duration

    @classmethod
    def _run_adhoc_beat(cls, beat, tool, target, point):
        # Certain beat callbacks are not supported or implemented for adhoc beats. Inform the user
        # if any of those have been implemented on the adhoc beat class.
        found = [f for f in cls.ADHOC_FORBIDDEN if f in beat.__dict__]
        if len(found) > 0:
            raise Exception("Certain beat callbacks are not permitted in adhoc beats %s" % found)
        if beat.CREATE_NEXT_TARGETS > 0:
            raise Exception("Defining CREATE_NEXT_TARGETS in adhoc beats is not supported.")

        # If there is a BEAT_START_DELAY defined then tick the game and wait to move towards the beat.
        if beat.BEAT_START_DELAY is not None:
            tool.advanced_story_by(beat.BEAT_START_DELAY, None)

        # Trigger the moving_to at beat events.
        beat.moving_to_target(tool, target, None)

        # If the adhoc beat indicates it is going to create a target on its own, then render it.
        if beat.RENDER_ADHOC_TARGET:
            # NOTE: In the case where an adhoc beat (some given point in the story) is actually creating a
            # target directly without user input then the original point._target_id might have been neutered
            # or deleted so regrab the most recent target for the rover target.
            if target is None:
                target = tool._user.all_picture_targets()[-1]
                assert not target.is_processed()
            tool.render_target(target, point=point)

        # Tick the game if BEAT_DURATION_SECONDS was defined.
        if beat.BEAT_ARRIVAL_DELTA is not None:
            tool.advanced_story_by(beat.BEAT_ARRIVAL_DELTA, None)

        # Trigger the arrived at beat events.
        beat.moved_to_target(tool, target, None)

        # Trigger the leaving and left beat events.
        beat.leaving_target(tool, target, None)
        beat.left_target(tool, target, None)

class ReplayGameFallbackBeat(story.StoryBeatInterface):
    """
    This is a StoryBeat class meant to be used when only a route .json file is passed to replay_game.
    It handles any additional data in the route/point data (such as species identification).
    This class is NOT meant for subclassing.
    """
    @classmethod
    def moved_to_target(cls, tool, target, point):
        if len(point.identified) > 0:
            rects = [debug.rects.for_species_key(species_key) for species_key in point.identified]
            tool.identify_species(rects, target)

# Number of seconds to push the story back from 'now'. 
# This is to prevent a pile of chips coming in when we first login.
EXTRA_START_TIME = 1

class ReplayGame(story.StoryDelegateInterface):
    def __init__(self, ctx, email, route_structs, beats=[], fallback_beat=None, verbose=True, password=TEST_PASSWORD):
        self._ctx = ctx
        self._email = email
        self._password = password
        self._story = story.Story(route_structs, delegate=self, beats=beats, fallback_beat=fallback_beat)
        self._verbose = verbose
        # Tracks the list of ReplayGameBeat classes that were visited.
        # NOTE: The fallback_beat is ignored by this tracking.
        self._visited_beats = set()

    def run(self, to_point=None, run_renderer=False, no_prompt=False):
        existing_user = debug.get_user_by_email(self._ctx, self._email)
        if existing_user is not None:
            if no_prompt:
                answer = 'y'
            else:
                answer = raw_input("Existing user for [%s], delete? (y/n)" % (self._email))
            if answer == "y":
                debug.delete_user_and_data(self._ctx, existing_user.user_id)
            else:
                raise Exception("Aborting process.")

        # Calculate how many seconds ago the first route point should have been created.
        if to_point is None:
            starting_time = self._story.duration()
        else:
            try:
                starting_time = self._story.duration_to_point(to_point)
            except story.UnknownPointError:
                self.error("Point name not in this Story [%s]\n" % to_point)
                self.known_points()
                return

        self.info("Creating new user for [%s] with password [%s]" % (self._email, self._password))
        # Roll back time to factor in the route elapsed duration before creating the user so that the
        # initial targets (lander and first photos) have the correct times relative to the start
        # of the route.
        debug.rewind_now(seconds=starting_time + EXTRA_START_TIME)
        self._user = user_module.create_and_setup_password_user(self._ctx, self._email, self._password,
                                                                TEST_FIRSTNAME, TEST_LASTNAME)

        moved_to = self._story.play(to_point=to_point)
        # The is not None is needed to exclude neutered and deleted targets.
        targets_moved_to = [self.target_for_point(p) for p in moved_to
                            if self.target_for_point(p) is not None]

        # If the entire story was run and every ReplayGameBeat that was defined in the beats modules was not visited,
        # log an error.
        if to_point is None:
            # Find the name of every beat defined in every beat module.
            all_beats = set()
            for beat_module in self._story._beats:
                for beat_name, beat_class in inspect.getmembers(beat_module):
                    if inspect.isclass(beat_class) and issubclass(beat_class, ReplayGameBeat):
                        all_beats.add(beat_name)
            not_visited = all_beats.difference(self._visited_beats)
            # Report an error and enumerate the ReplayGameBeats that were not visited. One reason this might happen
            # is if there is a slightly misnamed ReplayGameBeats subclass to the corresponding Point name in the
            # route data e.g. POINT1 vs. POINT01
            if len(not_visited) > 0:
                raise Exception("Some ReplayGameBeats were not visited: %s" % not_visited)

        # If requested, mark the newly created targets as unprocessed and run the real renderer so that
        # map tiles will be created.
        if run_renderer:
            self.info("Running real renderer for %d targets." % len(targets_moved_to))
            debug.mark_targets_for_rerender(self._ctx, targets_moved_to)
            # We must commit finally in order for the real renderer process to see the new targets and user.
            db.commit(self._ctx)
            debug.run_real_renderer()

    def known_points(self):
        self.info("Known points in this story (%d total):" % self._story.num_points())
        for p_name in self._story.named_points():
            self.info(p_name)

    ## Utilities for the ReplayGameBeats available from the 'tool' method parameter.
    def identify_species(self, rects, target):
        check_species.identify_species_in_target(self._ctx, target, rects)

    def mark_messages_read(self):
        for m in self._user.messages.unread():
            m.mark_as_read(self._ctx)

    def unlock_message(self, msg_type):
        message = self._user.messages.by_type(msg_type)
        message.unlock(message.keycode)

    def forward_message(self, msg_type, recipient):
        message = self._user.messages.by_type(msg_type)
        message.forward_to(recipient)

    def achieve_client_progress(self, key):
        progress_module.create_new_client_progress(self._ctx, self._user, key)

    ## StoryDelegate methods
    def create_target_for_point(self, point, relative_arrival_delta):
        # Find the currently active rover. Assumes one at a time.
        rovers = self._user.rovers.active()
        assert(len(rovers) == 1)
        active_rover = rovers[0]
        # Create the target using the point data.
        metadata = {}
        t = target_module.create_new_target_with_constraints(self._ctx, active_rover,
                                                             lat=point.lat, lng=point.lng, yaw=point.yaw,
                                                             arrival_delta=relative_arrival_delta, metadata=metadata)
        if t is None:
            raise Exception("Failed to create target during replay_game [%s]" % point)
        # Store the target_id created for this Point to be used by target_for_point.
        point._target_id = t.target_id

    def target_for_point(self, point):
        # The target might be None, which means it was neutered or deleted in some other manner.
        # Return None to indicate that no callbacks should be dispatched.
        return self._user.rovers.find_target_by_id(point._target_id)

    def render_target(self, target, point):
        debug.render_target_for_user(self._ctx, self._user, target)

    def advanced_story_by(self, seconds, point):
        # Run any deferred actions simulating the deferred system running halfway between the two
        # points. It will be run again on arrival to catch any more.
        # run_deferred_since_and_advance_now will set gametime.now to 'until'.
        debug.run_deferred_and_advance_now_until(self._ctx, self._user, until=gametime.now() + timedelta(seconds=seconds))

    def info(self, message):
        if self._verbose:
            print message

    def error(self, message):
        print "ERROR:", message

def make_optparser():
    usage = "%prog <user_email> <story_file/route_file> [to_point_name]"
    usage += "\n story_file is a .py Story module, route_file is a .json file containing a single Route"
    optparser = optparse.OptionParser(usage=usage)
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development.",
    )
    optparser.add_option(
        "-r", "--renderer", dest="run_renderer", action="store_true", default=False,
        help="Run the real renderer process.",
    )
    optparser.add_option(
        "", "--no_prompt", dest="no_prompt", action="store_true", default=False,
        help="Do not prompt for verification before deleting existing user.",
    )
    optparser.add_option(
        "-p", "--points", dest="list_points", action="store_true", default=False,
        help="List all of the known Point names for this Story.",
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if len(args) < 2:
        optparser.print_help()
        return

    email = args[0]
    input_file = args[1]
    if len(args) > 2:
        to_point = args[2]
    else:
        to_point = None

    # Silence the email sending system. No emails will be displayed or sent by replay_game.
    email_module.set_echo_dispatcher(quiet=True)

    config = read_config_and_init(opts.deployment)
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            # If supplied a .py file load the code and pass that to ReplayGame
            if input_file.endswith('.py'):
                import imp
                _story_module = imp.load_source('_story_module', input_file)
                game = ReplayGame(ctx, email, _story_module.routes(), beats=_story_module.beats())

            # Otherwise assume this is a route JSON with no beats and load it.
            else:
                with open(input_file) as f:
                    r_struct = xjson.load(f)
                    game = ReplayGame(ctx, email, [r_struct], fallback_beat=ReplayGameFallbackBeat)

            if opts.list_points:
                game.known_points()
            else:
                game.run(to_point=to_point, run_renderer=opts.run_renderer, no_prompt=opts.no_prompt)

if __name__ == "__main__":
    main(sys.argv[1:])
