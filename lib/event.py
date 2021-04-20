# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.callbacks import run_callback, run_all_callbacks, MISSION_CB, TARGET_CB, SPECIES_CB, ACHIEVEMENT_CB

# event_type definitions.  This is the mapping between event types and the
# callback function names in the corresponding *_callbacks.py files.
class types(object):
    TARGET_CREATED  = "target_created"
    TARGET_EN_ROUTE = "target_en_route"
    TARGET_ARRIVED  = "arrived_at_target"
    SPECIES_ID      = "species_identified"
    ALL = set([TARGET_CREATED, TARGET_EN_ROUTE, TARGET_ARRIVED, SPECIES_ID])

# Enumerate event_types which specific callback code types are interested in.
# The callbacks for the subsystem listed on the left side of the "="
# responds to the events listed on the right.
MISSION_EVENTS     = (types.TARGET_CREATED, types.TARGET_EN_ROUTE, types.TARGET_ARRIVED, types.SPECIES_ID)
TARGET_EVENTS      = (types.TARGET_CREATED, types.TARGET_EN_ROUTE, types.TARGET_ARRIVED)
SPECIES_EVENTS     = (types.SPECIES_ID)
ACHIEVEMENT_EVENTS = (types.TARGET_CREATED, types.TARGET_EN_ROUTE, types.TARGET_ARRIVED, types.SPECIES_ID)

def dispatch(ctx, user, event_type, subtype, *args, **kwargs):
    """
    Dispatch an event. Callback code will be loaded and run as appropriate based on the event_type and
    sub_type and args and kwargs will be passed through to the callback.
    :param ctx: The database context.
    :param user: The User for whom this event is being dispatched.
    :param event_type: str The type of this event, defined as constants in this module.
    :param subtype: str The subtype for this event, specific to the event_type.
    """
    assert event_type in types.ALL, "Unknown event_type %s" % event_type

    if event_type in MISSION_EVENTS:
        # Need to use keys() or values() as a mission trigger may add a new mission to user.missions which would
        # mutate the dict which is not allowed in an iteration.
        for m in user.missions.not_done():
            # It is possible that a mission will be marked done by another mission during the iteration so check again.
            if not m.done:
                result = run_callback(MISSION_CB, event_type, m.mission_definition, ctx, user, m, *args, **kwargs)
                # These callbacks can just return (None) in order to handle mark_done themselves.
                if result is True:
                    m.mark_done()

    if event_type in TARGET_EVENTS:
        # All defined callbacks in target_callbacks are run for any target creation or arrival.
        run_all_callbacks(TARGET_CB, event_type, ctx, user, *args, **kwargs)

    if event_type in SPECIES_EVENTS:
        run_callback(SPECIES_CB, event_type, subtype, ctx, user, *args, **kwargs)

    if event_type in ACHIEVEMENT_EVENTS:
        for a in user.achievements.not_achieved():
            # It is possible that an achievement will be marked achieved by another achievement callback during
            # the iteration so check again.
            if not a.was_achieved():
                result = run_callback(ACHIEVEMENT_CB, event_type, a.achievement_key, ctx, user, a, *args, **kwargs)
                if result:
                    a.mark_achieved()
