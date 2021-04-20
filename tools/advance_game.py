#!/usr/bin/env python
# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys, optparse
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import time

from front import read_config_and_init, debug
from front.lib import db, gametime

class AdvanceGameTool(object):
    def __init__(self, ctx, email, run_renderer, tick_seconds, pause_seconds, verbose=True):
        self.ctx = ctx
        self.email = email
        self.run_renderer = run_renderer
        self.tick_seconds = tick_seconds
        self.pause_seconds = pause_seconds
        self._verbose = verbose

        # Track various activity that happens during the lifespan of this tool instance.
        self.processed_targets = []
        self.activated_chips = []
        self.deferreds_run = []

        if self.run_renderer:
            self.info("Running with real renderer.")
        else:
            self.info("Running with fake renderer.")

    def load_user(self):
        u = debug.get_user_by_email(self.ctx, self.email)
        if u is None:
            raise Exception("No user found for [%s], aborting." % self.email)
        return u

    def enter_run_mode(self, mode):
        RUN_MODES[mode](self)

    def run_increment_mode(self):
        u = self.load_user()

        # Process any pending targets.
        self._process_targets(u)

        # And advance the rest of the game data.
        self._advance_game_by_seconds(u, self.tick_seconds)
        db.commit(self.ctx)

    def run_catchup_mode(self):
        u = self.load_user()

        while debug.user_has_pending_game_actions(self.ctx, u):
            # Process any pending targets.
            self._process_targets(u)

            # And advance the rest of the game data using the tick_seconds setting. This will keep
            # ticking until user_has_pending_game_actions returns False.
            self._advance_game_by_seconds(u, self.tick_seconds)

        db.commit(self.ctx)

    def run_target_mode(self):
        while True:
            # Load a fresh User for every tick, so that the gamestate models look correct.
            u = self.load_user()

            # Process any pending targets.
            processed = self._process_targets(u)

            # Iterate through each target, jumping the game forward to its arrival_time,
            # then sleeping until advancing to the next target.
            previous_arrival = None
            for t in processed:
                # For the first target, the start of the tick is the start_time of the target.
                if previous_arrival is None:
                    previous_arrival = processed[0].start_time

                # Advance the game between this targets arrival_time and the previous
                # targets arrival time.
                travel_seconds = t.arrival_time - previous_arrival
                self._advance_game_by_seconds(u, tick_seconds=travel_seconds)

                previous_arrival = t.arrival_time
                # Between every target, commit what has happened so far and then pause.
                db.commit(self.ctx)
                self._pause_loop()

            # Commit required even if nothing happens so ctx will see newly created targets etc.
            db.commit(self.ctx)
            self._pause_loop()

    def run_looping_mode(self):
        while True:
            # Load a fresh User for every tick, so that the gamestate models look correct.
            u = self.load_user()

            # If the game has any pending actions, then advance the game by tick_seconds
            # and process anything that should have been processed in that window.
            if debug.user_has_pending_game_actions(self.ctx, u):
                # Process any pending targets.
                self._process_targets(u)
            
                # And advance the rest of the game data.
                self._advance_game_by_seconds(u, self.tick_seconds)

            db.commit(self.ctx)
            self._pause_loop()

    def info(self, message):
        if self._verbose:
            print message

    def error(self, message):
        print "ERROR:", message

    # Private helper API.
    def _advance_game_by_seconds(self, u, tick_seconds):
        self.info("Advancing game by %d seconds (%.2f hours)." % (tick_seconds, tick_seconds/3600.0))
        (deferred_rows, activated_chips) = debug.advance_game_for_user_by_seconds(self.ctx, u, seconds=tick_seconds)
        self.deferreds_run += deferred_rows
        self.activated_chips += activated_chips

        for row in deferred_rows:
            self.info("Ran deferred action (%s:%s)" % (row.deferred_type, row.subtype))
        for chip in activated_chips:
            text = "Activated chip [%s][%s]" % (', '.join([str(k) for k in chip['path'][1:]]), chip['action'])
            if 'msg_type' in chip['value']:
                text += '[%s]' % chip['value']['msg_type']
            self.info(text)

    def _process_targets(self, u):
        processed = debug.render_all_due_targets_for_user(self.ctx, u, run_renderer=self.run_renderer)
        if len(processed) > 0:
            if self.run_renderer:
                # Need to commit our transaction now so that this connection can see
                # that the real renderer marked the target as processed.
                db.commit(self.ctx)
                self.info("Real renderered targets (%d)." % len(processed))
            else:
                self.info("Fake renderered targets (%d)." % len(processed))
        self.processed_targets += processed
        return processed

    def _pause_loop(self):
        # Restore gametime to the real wallclock 'now' so that if this loop is long running, the client
        # doesn't get too far ahead of this processes concept of 'now', meaning that chips will still
        # be fetched in roughly the correct window.
        gametime.unset_now()

        self.info("Paused for %d seconds. Use Ctrl-C to quit." % self.pause_seconds)
        time.sleep(self.pause_seconds)

RUN_MODES = {
    "increment": AdvanceGameTool.run_increment_mode,
    "catchup": AdvanceGameTool.run_catchup_mode,
    "target": AdvanceGameTool.run_target_mode,
    "looping": AdvanceGameTool.run_looping_mode
}

def make_optparser():
    usage = "%prog <user_email>"
    usage += """

Run Modes:
    increment :  Advance the game once by the provided tick_seconds.
    catchup   :  Advance the game until all pending actions have run.
    target    :  Advance the game in a loop, jumping forward between pending targets.
    looping   :  Advance the game in a loop, jumping forward by tick_seconds."""

    optparser = optparse.OptionParser(usage=usage)
    optparser.add_option(
        "-r", "--renderer", dest="run_renderer", action="store_true", default=False,
        help="Run the real renderer process.",
    )
    optparser.add_option(
        "-m", "--mode", dest="run_mode", default="catchup", choices=RUN_MODES.keys(),
        help="Select the run mode (%s)." % RUN_MODES.keys()
    )
    optparser.add_option(
        "-q", "--quiet", dest="quiet", action="store_true", default=False,
        help="Run in quiet mode."
    )
    optparser.add_option(
        "-S", "--seconds", dest="tick_seconds", default=3600, type="int",
        help="The number of seconds the game advances per 'tick'."
    )
    def hours_to_seconds(option, opt_str, value, parser):
        setattr(parser.values, option.dest, value * 3600)
    optparser.add_option(
        "-H", "--hours", dest="tick_seconds", type="int", action="callback", callback=hours_to_seconds,
        help="The number of hours the game advances per 'tick'."
    )
    optparser.add_option(
        "-P", "--pause", dest="pause_seconds", default=6, type="int",
        help="The number of seconds to sleep before performing the next 'tick'."
    )
    return optparser

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if len(args) < 1:
        optparser.print_help()
        return

    email = args[0]
    config = read_config_and_init('development')
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            advance = AdvanceGameTool(ctx, email, run_renderer=opts.run_renderer,
                tick_seconds=opts.tick_seconds, pause_seconds=opts.pause_seconds,
                verbose=not opts.quiet)
            try:
                advance.enter_run_mode(opts.run_mode)
            except KeyboardInterrupt:
                print "\nExiting."

if __name__ == "__main__":
    main(sys.argv[1:])
