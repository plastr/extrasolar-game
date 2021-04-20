#!/usr/bin/env python
# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import os, sys
BASEDIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASEDIR)

import optparse

from front import read_config_and_init, debug, target_image_types
from front.lib import db, xjson
from front.debug import route
from front.models import species
from front.models import user as user_module

def targets_as_route_for_user_id(ctx, user_id):
    """
    Return the given user's (using their user_id) current game progress as both
    a list of Route objects and a list of targets sorted by start_time.
    Returns:
    [(rover1, route_obj), (rover2, route_obj), ...], all_targets_by_start_time
    """
    # Load a fresh user object so target data is current.
    user = user_module.user_from_context(ctx, user_id)

    # Sort all targets across all rovers by start_time for this user.
    all_targets = [t for r in user.rovers.values() for t in r.targets.values()]
    all_targets = sorted(all_targets, key=lambda t: t.start_time)
    current_rover_id = None
    routes_by_rover = []
    current_points = []
    # Iterate through the list of targets. Whenever a new rover is activated,
    # append that rover and a Route of all user_created targets to the list.
    for i, t in enumerate(all_targets):
        if t.rover.rover_id != current_rover_id:
            if len(current_points) > 0:
                # Convert the points for the previous rover into a Route and reset the array.
                routes_by_rover.append((t.rover, route.Route(current_points)))
                current_points = []
            current_rover_id = t.rover.rover_id

        # If the target was not created by the user, we will not put it in the Route.
        if not t.was_user_created():
            continue

        # Determine the Point.arrival_delta for this Target.
        # First calculate the travel time from target start to arrival. Then, if there was a
        # previous target, add in how long it was between arriving at the previous target
        # and starting this target.
        arrival_delta = t.arrival_time - t.start_time
        if i > 0:
            # If this is the first rover, and the first user created target, we need to factor in
            # the amount of time that elapsed between the rover being created, the initial system
            # targets being created, and the moment when the user was able to make their first target.
            # It is the time between the moment the user was able to make the first target and the
            # moment they actually chose to create that target that is the start_delay for the
            # first user created target.
            if len(routes_by_rover) == 0 and len(current_points) == 0:
                start_delay = t.start_time - user.first_move_possible_at()
            # For all other targets, the start_delay is the amount of time between the arrival_time
            # of the previous target and the start_time of this target.
            else:
                start_delay = t.start_time - all_targets[i - 1].arrival_time
        # If this is the first target, use its start_time for the start_delay.
        else:
            start_delay = t.start_time

        # Find all of the identified species_keys.
        identified = [str(species.get_key_from_id(species_id)) for species_id in t.species_count().keys()]

        # Store all of the pertinent target data in a Point object.
        point = route.Point(t.lat, t.lng, t.yaw, name=None,
                            arrival_delta=arrival_delta, start_delay=start_delay, identified=identified)
        current_points.append(point)

    # Handle the last rover.
    routes_by_rover.append((t.rover, route.Route(current_points)))

    return routes_by_rover, all_targets

def print_route_json_for_rover(route, rover):
    # NOTE: The outer most array is printed direct (e.g. the []) for a prettier format.
    print "JSON for route, rover_id=" + str(rover.rover_id)
    print "-----------"
    print "["
    for i, p in enumerate(route.iterpoints()):
        out = "    " + xjson.dumps(p.to_struct())
        if i < route.num_points() - 1:
            out += ","
        print out
    print "]"
    print "-----------"
    print

def print_targets_for_user(user, targets):
    print "Current targets for user email=[%s] id=[%s]" % (user.email, user.user_id)
    current_rover_id = None
    for t in targets:
        if t.rover.rover_id != current_rover_id:
            print "New rover activated:", t.rover.rover_id
            current_rover_id = t.rover.rover_id

        print "    Target:", t.target_id, "user_created:", t.was_user_created()
        print "      start_time:", t.start_time_date, "arrival_time:", t.arrival_time_date
        print "      lat:", t.lat, " lng:", t.lng, "yaw:", t.yaw, "processed:", t.processed, "picture:", t.picture
        print "      viewed_at:", t.viewed_at, "photo:", t.images.get(target_image_types.PHOTO)
        print "      species:", [str(species.get_key_from_id(species_id)) for species_id in t.species_count().keys()]
        print

def make_optparser():
    usage = "%prog user_email"
    usage += "\nDump the current route/targets for the given user, optionally as Route compatible JSON"
    optparser = optparse.OptionParser(usage=usage)
    optparser.add_option(
        "", "--deployment", dest="deployment", default="development",
        help="Set the deployment name. Defaults to development.",
    )
    optparser.add_option(
        "-j", "--json", dest="dump_json", action="store_true", default=False,
        help="Dump the route data in JSON.",
    )
    return optparser

def main(argv=None):
    print "This tool is has error prone and unreliable data output and should not be used as currently written."
    sys.exit()

    if argv is None:
        argv = sys.argv[1:]

    optparser = make_optparser()
    opts, args = optparser.parse_args(argv)

    if len(args) < 1:
        optparser.print_help()
        return

    config = read_config_and_init(opts.deployment)
    with db.commit_or_rollback(config) as ctx:
        with db.conn(ctx) as ctx:
            user = debug.get_user_by_email(ctx, args[0])
            if user is None:
                print "No user with email", args[0]
                return

            routes_by_rover, all_targets = targets_as_route_for_user_id(ctx, user.user_id)
            if opts.dump_json:
                for rover, route in routes_by_rover:
                    print_route_json_for_rover(route, rover)
            else:
                print_targets_for_user(user, all_targets)

if __name__ == "__main__":
    main(sys.argv[1:])
