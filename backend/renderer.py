# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
from front.data import renderer_asset

def process_target_struct(user, target):
    """ Construct the a dict object ready to be JSON-ified which satisfies the renderers requirements
        to process the target."""
    # Build up a list of all rovers for this user.
    rovers = user.rovers.values()
    # The rover for the target being processed must be the last rover in the list.
    last_rover = user.rovers[target.rover_id]
    rovers.remove(last_rover)
    rovers.append(last_rover)

    # And a map from those rover's IDs to their targets in sorted order.
    rover_targets = {}
    for rover in rovers:
        rover_targets[rover.rover_id] = rover.targets.by_arrival_time()

    # For the rover which owns the target being rendered, the target being rendered
    # should be the last target in the list. Any newer targets will be sliced off.
    rover_targets[last_rover.rover_id] = last_rover.targets.split_on_target(target)[0]

    # At this point the last rovers last target must match the target that was selected
    # as the target to work on, otherwise the renderer will not know which target to process.
    assert rover_targets[last_rover.rover_id][-1].target_id == target.target_id

    # Build up the rover and target structs ready to be JSON-ified.
    rovers_struct = []
    for r in rovers:
        struct = r.to_struct_renderer_input()
        struct.update(
            {'targets': [t.to_struct_renderer_input() for t in rover_targets[r.rover_id]]})
        rovers_struct.append(struct)

    return {
        'status': 'ok',
        'user_id': str(user.user_id),
        'rovers': rovers_struct,
        'assets': [a.to_struct() for a in renderer_asset.assets_for_user_at_time(user, last_rover, target.arrival_time)]
    }
