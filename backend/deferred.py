# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.

import uuid
from datetime import timedelta

from front.lib import db, gametime, get_uuid, event, xjson
from front.callbacks import run_callback, TIMER_CB

import logging
logger = logging.getLogger(__name__)

class DeferredRow(object):
    """
    Wraps the fields from a a deferred database row.
    """
    fields = frozenset(['deferred_id', 'user_id', 'deferred_type', 'subtype', 'created', 'run_at', 'payload'])
    def __init__(self, **kwargs):
        for field in self.fields:
            setattr(self, field, kwargs[field])
        self.deferred_id = get_uuid(self.deferred_id)
        self.user_id = get_uuid(self.user_id)
        if self.payload is not None:
            self.payload = xjson.loads(self.payload)

    def delete(self, ctx):
        db.run(ctx, 'deferred/delete_deferred', deferred_id=self.deferred_id)

    def __repr__(self):
        payload = None if self.payload is None else ",".join(sorted(self.payload.keys()))
        return "%s(%s:%s)[%s]" % (self.__class__.__name__, self.deferred_type, self.subtype, payload)

# deferred_type definitions.
class types(object):
    EMAIL = "EMAIL"
    MESSAGE = "MESSAGE"
    # subtype is a string representation of the target UUID.
    TARGET_ARRIVED = "TARGET_ARRIVED"
    MISSION_DONE_AFTER = "MISSION_DONE_AFTER"
    TIMER = "TIMER"
    ALL = set([EMAIL, MESSAGE, TARGET_ARRIVED, MISSION_DONE_AFTER, TIMER])

def run_on_timer(ctx, timer_subtype, user, delay, **kwargs):
    """
    Request that a timer_arrived_at event be dispatched to the timer_callbacks for the given TMR_ subtype.
    :param ctx: The database context.
    :param subtype: str a type specific value supplied when the action is run e.g. TMR_SOME_TIMER
    :param user: User instance for whom this action will be run.
    :param delay: int, Number of seconds that the timer will wait before firing.
    :param kwargs: dict, Any additonal keyword arguments will be added to the deferred payload and passed
        to the timer callback as arguments. NOTE: These arguments must be able to be JSON serializable and
        also note that the size of the payload is not very large so keep the keys and values small.
    """
    assert timer_subtype.startswith("TMR_"), "Timer subtype keys must start with a TMR_ prefix."
    # If any extra arguments were supplied, pack them into a payload dictionary ready to
    # be serialized into JSON.
    if len(kwargs) > 0:
        payload = dict(kwargs)
    else:
        payload = None
    run_later(ctx, types.TIMER, timer_subtype, user, delay, _payload=payload)

def run_later(ctx, deferred_type, subtype, user, delay, _payload=None):
    """
    Request that an action be run after a given delay.
    :param ctx: The database context.
    :param deferred_type: str defining this deferred action e.g EMAIL.
    :param subtype: str a type specific value supplied when the action is run e.g. EMAIL_WELCOME
    :param user: User instance for whom this action will be run.
    :param delay: int, Number of seconds to wait before running action.
    :param _payload: Optional dict of JSON-ifyable data to associate with this deferred action.
        NOTE: It is intended that if payload is used, run_later will be wrapped by a function which
        enumerates in a clear manner what data should be placed into the payload, hence its private nature.
    """
    assert deferred_type in types.ALL, "Unknown deferred_type %s" % deferred_type
    if delay < 0:
        logger.warn("Refusing to run later a deferred with a negative delay time, setting to 0. [%s][%s][%s][%d]", deferred_type, subtype, user.user_id, delay)
        delay = 0
    params = {}
    params['deferred_id'] = uuid.uuid1()
    params['deferred_type'] = deferred_type
    params['subtype'] = subtype
    params['user_id'] = user.user_id
    # Calculate datetime when action should be run.
    params['run_at'] = gametime.now() + timedelta(seconds=delay)
    # Serialize the payload data if provided.
    if _payload is not None:
        params['payload'] = xjson.dumps(_payload)
    else:
        params['payload'] = None

    # Save all data needed to run the action to the deferred table.
    with db.conn(ctx) as ctx:
        db.run(ctx, "deferred/insert_deferred", **params)

def is_queued_to_run_later_for_user(ctx, deferred_type, subtype, user):
    """
    Return True if there is at least one deferred action in the queue for the
    given deferred_type and subtype for the given user. False otherwise.
    See run_later for parameter documentation.
    """
    with db.conn(ctx) as ctx:
        row = db.row(ctx, "deferred/deferred_type_exists_for_user",
                       deferred_type=deferred_type, subtype=subtype, user_id=user.user_id)
        return row['exist'] == 1

def run_deferred_since(ctx, since):
    '''
    Find all rows in the deferred table where the run_at time has passed.
    Run action and delete row.
    :param ctx: The database context.
    :param since: datetime Run deferred actions with run_at times older than this.
    Returns the number of deferred actions run.
    '''
    # Have to import user_module this way to avoid a cyclic dependency import error.
    from front.models import user as user_module
    with db.conn(ctx) as ctx:
        processed = 0
        rows = db.rows(ctx, 'deferred/select_deferred_since', since=since)
        for row in rows:
            try:
                deferred_row = DeferredRow(**row)
                user = user_module.user_from_context(ctx, deferred_row.user_id)

                # Process this deferred action.
                process_row(ctx, user, deferred_row)

                # If no exception ocurred for this deferred, delete it from the database and
                # commit the transaction.
                deferred_row.delete(ctx)
                db.commit(ctx)
                processed += 1

            except:
                # If any exception occurs processing this row, rollback the transaction
                # and try the next deferred row. process_row is responsible for logging
                # any exceptions that occur.
                db.rollback(ctx)

    return processed

def process_row(ctx, user, row):
    if row.deferred_type == types.EMAIL:
        from front.lib import email_module
        try:
            email_module.send_now(ctx, user, row.subtype)
        except email_module.EmailSendFailed, e:
            logger.exception("Sending deferred email failed for deferred_id %s with address %s. [%s]",
                row.deferred_id, user.email, e.message)
            raise

    elif row.deferred_type == types.MESSAGE:
        from front.models import message
        try:
            message.send_now(ctx, user, row.subtype)
        except Exception, e:
            logger.exception("Sending deferred message failed "
                + "[deferred_id:%s, user:%s, subtype:%s]. [%s]",
                row.deferred_id, user, row.subtype, e)
            raise

    elif row.deferred_type == types.TARGET_ARRIVED:
        try:
            # The deferred subtype is a string representation of the target_id for the target just arrived at.
            target_id = get_uuid(row.subtype)
            target = user.rovers.find_target_by_id(target_id)
            # The target might have been pruned or deleted in which case we will ignore it
            # and mark this deferred as handled.
            if target is not None:
                # Dispatch the TARGET_ARRIVED event.
                event.dispatch(ctx, user, event.types.TARGET_ARRIVED, row.subtype, target)

                # If the just arrived at target has next target which has not been arrived at, then dispatch
                # the TARGET_EN_ROUTE event for the next target.
                # See target.py to see how the TARGET_EN_ROUTE event is dispatched for targets with no next target.
                next_target = target.next()
                if next_target is not None:
                    if next_target.has_been_arrived_at():
                        logger.error("Dispatching target_en_route event for already arrived target, deferred system down/delayed? [%s][%s]", next_target.target_id, user.user_id)
                    event.dispatch(ctx, user, event.types.TARGET_EN_ROUTE, row.subtype, next_target)
        except Exception, e:
            logger.exception("Processing target arrived deferred failed "
                + "[deferred_id:%s, user:%s, subtype:%s, target_id:%s]. [%s]",
                row.deferred_id, user, row.subtype, target_id, e)
            raise

    elif row.deferred_type == types.MISSION_DONE_AFTER:
        try:
            mission = user.missions.get_only_by_definition(row.subtype)
            if mission is None:
                logger.error("Cannot locate mission_definition for user to mark done after [%s][%s]", row.subtype, user.user_id)
            else:
                # Do not attempt to mark an already marked mission done.
                if not mission.is_done():
                    mission.mark_done()
                
        except Exception, e:
            logger.exception("Processing target arrived deferred failed "
                + "[deferred_id:%s, user:%s, subtype:%s, target_id:%s]. [%s]",
                row.deferred_id, user, row.subtype, target_id, e)
            raise

    elif row.deferred_type == types.TIMER:
        try:
            if row.payload is None:
                run_callback(TIMER_CB, "timer_arrived_at", row.subtype, ctx=ctx, user=user)
            # If a payload was supplied, pass all the arguments to the callback.
            else:
                run_callback(TIMER_CB, "timer_arrived_at", row.subtype, ctx=ctx, user=user, **row.payload)
        except Exception, e:
            logger.exception("Processing timer deferred failed [deferred_id:%s, user:%s, subtype:%s]. [%s]",
                row.deferred_id, user, row.subtype, e)
            raise

    else:
        raise Exception("Unknown deferred_type, aborting process %s", row.deferred_type)
