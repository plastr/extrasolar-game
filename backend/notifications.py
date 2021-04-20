# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import timedelta

from front import activity_alert_types, Constants
from front.lib import db, email_module, get_uuid, utils
from front.backend import activity
from front.models import user as user_module

import logging
logger = logging.getLogger(__name__)

def send_activity_alert_at(ctx, at_time, notify_activity_callback, continue_on_fail=False):
    '''
    Find all rows in the users_notification table where the user has enabled notifications.
    Then determine if their activity_alert_window_start is older than the max_window determined by the frequency interval
    set in the user's users_notification table and we have not sent them an email during that window
    (as a guard) by checking activity_alert_last_sent. For any user who has notifiable activity, where the
    oldest activity falls at or beyond the max_window, send them a digest email of their activity.
    Otherwise update their activity_alert_window_start to be current.
    :param ctx: The database context.
    :param at_time: datetime Send expected notifications for at_time (usually now).
    :param notify_activity_callback: Callable a callable of the form callback(ctx, user, user_activity, at_time)
        which will be called if a user has reportable activity. The default implementation will send
        an email, factored out for testing purposes.
    :param continue_on_fail: If True, then a failure processing or sending a digest for a given user
        will not fail/abort the entire process. Defaults to False.
    Returns the number of users for whom activity data was checked/processed (not necessarily an email sent).
    '''
    processed = 0
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'notifications/select_pending_activity_alerts', now=at_time,
                       activity_alert_inactive_threshold=Constants.ACTIVITY_ALERT_INACTIVE_THRESHOLD)
        for row in rows:
            try:
                # Calculate the moment in time when the max_window_size would first have been exceeded
                # for this frequency
                window_size = activity_alert_types.windows[row['activity_alert_frequency']]
                max_window_start = at_time - timedelta(seconds=window_size)

                # Load the rest of the row data.
                user_id = get_uuid(row['user_id'])
                user = user_module.user_from_context(ctx, user_id)
                activity_alert_last_sent = row['activity_alert_last_sent']
                activity_alert_window_start = row['activity_alert_window_start']

                # If this user's activity_alert_window_start is still earlier than their frequency window size
                # skip this user for now.
                if activity_alert_window_start is not None and activity_alert_window_start > max_window_start:
                    continue

                # If this user does not (yet) have a window start (maybe they are new or have just turned
                # notifications on), then set it to at_time (usually now).
                if activity_alert_window_start is None:
                    activity_alert_window_start = at_time

                # Add a guard to be sure not to send emails more often than the max_window_start so as not
                # to accidently spam the user.
                if activity_alert_last_sent is not None and activity_alert_last_sent > max_window_start:
                    logger.error("Refusing to send digest email, too soon. Programmer error? at:%s last:%s start:%s %s",
                        at_time, activity_alert_last_sent, max_window_start, user_id)
                    continue

                # Lookup all unseen activity (messages, targets etc) for this user between activity_alert_window_start
                # and at_time.
                user_activity = activity.recent_activity_for_user(ctx, user, since=activity_alert_window_start, until=at_time)

                # If this user has no activity to notify on, then update their window_start to now and move
                # on to the next user.
                if user_activity.earliest is None:
                    # Jump the activity_alert_window_start time forward to now.
                    db.run(ctx, 'notifications/update_user_notifications_activity_alert_window_start',
                                activity_alert_window_start=at_time, user_id=user_id)

                else:
                    # Else if they have activity in the window, and the time between the first activity event and
                    # now is greater than window_size, send the user their digest email.
                    if utils.seconds_between_datetimes(user_activity.earliest, at_time) > window_size:
                        # Inform the callback that there is notifiable activity. Usually this will send an email
                        notify_activity_callback(ctx, user, user_activity, at_time)
                        # Now that the email is sent, the window start needs to be updated to "now".
                        activity_alert_window_start = at_time

                    # Else they have activity, but the earliest activity event is newer than the window_size so
                    # update the window_start to be the earliest activity event. This would happen the event which had
                    # originally set the activity_alert_window_start had been seen/read but another event had come in
                    # after that
                    else:
                        activity_alert_window_start = user_activity.earliest

                    # Persist activity_alert_window_start as it has (most likely) changed.
                    db.run(ctx, 'notifications/update_user_notifications_activity_alert_window_start',
                                activity_alert_window_start=activity_alert_window_start, user_id=user_id)

                # If no exception ocurred sending this digest email, commit the transaction.
                db.commit(ctx)
                processed += 1

            except Exception, e:
                logger.exception("Sending digest email failed for user_id %s. [%s]", user_id, e)
                db.rollback(ctx)
                if not continue_on_fail:
                    raise

    return processed

def send_activity_alert_email_callback(ctx, recipient, user_activity, at_time):
    """ The callback used by the tool to actually send emails. Exposed as public API so it can be
        used selectively in unit testing, if the email module has been mocked correctly. """
    # Send the activity alert email for this user.
    email_module.send_now(ctx, recipient, "EMAIL_ACTIVITY_ALERT", template_data={'user_activity':user_activity})
    # Mark in the database that an email was sent for this user.
    db.run(ctx, 'notifications/update_user_notifications_activity_alert_last_sent', activity_alert_last_sent=at_time, user_id=recipient.user_id)

def send_lure_alert_at(ctx, at_time, notify_activity_callback, continue_on_fail=False):
    '''
    Find all rows in the users_notification table where the user has enabled notifications and who have not been
    active (as determined by last_accessed) in the last lure window (as determiend by LURE_ALERT_WINDOW). If a
    user has already been checked after the LURE_ALERT_WINDOW since their last_accessed, do not check again, unless
    they become active again (so only check once per inactive window).
    If the user has lure reportable activity as determined by the LureUserActivity object during an inactive window,
    then send them a lure alert notification email.
    NOTE: Anytime a user is checked, lure_alert_last_checked is updated in the database, even if an email was not sent.
    :param ctx: The database context.
    :param at_time: datetime Send expected notifications for at_time (usually now).
    :param notify_activity_callback: Callable a callable of the form callback(ctx, user, user_activity, at_time)
        which will be called if a user has reportable activity. The default implementation will send
        an email, factored out for testing purposes.
    :param continue_on_fail: If True, then a failure processing or sending a digest for a given user
        will not fail/abort the entire process. Defaults to False.
    Returns the number of users for whom lure data was checked/processed (not necessarily an email sent).
    '''
    processed = 0
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, 'notifications/select_pending_lure_alerts', now=at_time, lure_threshold_seconds=Constants.LURE_ALERT_WINDOW)
        for row in rows:
            try:
                # Load the row data.
                user_id = get_uuid(row['user_id'])
                user = user_module.user_from_context(ctx, user_id)
                lure_alert_last_checked = row['lure_alert_last_checked']
                last_accessed = row['last_accessed']

                # Add a guard to be sure not to send emails if a lure email was ever sent and it was sent
                # more recently than the players last access to avoid accidently spam the user.
                if lure_alert_last_checked is not None and lure_alert_last_checked > last_accessed:
                    logger.error("Refusing to send lure email, too soon. Programmer error? at:%s last:%s access:%s %s",
                        at_time, lure_alert_last_checked, last_accessed, user_id)
                    continue

                # Lookup all lure activity (not done missions, unviewed messages, etc) for this user.
                user_activity = activity.lure_activity_for_user(ctx, user)

                # If there has been user activity during the lure window (as determined by the UserActivity
                # has_lure_activity method) then inform the callback that there is notifiable activity.
                # Usually this will send an email
                if user_activity.has_lure_activity():
                    notify_activity_callback(ctx, user, user_activity, at_time)

                # Mark in the database that this lure window was checked for this user.
                db.run(ctx, 'notifications/update_user_notifications_lure_alert_last_checked', lure_alert_last_checked=at_time, user_id=user_id)

                # If no exception ocurred sending this digest email, commit the transaction.
                db.commit(ctx)
                processed += 1

            except Exception, e:
                logger.exception("Sending digest email failed for user_id %s. [%s]", user_id, e)
                db.rollback(ctx)
                if not continue_on_fail:
                    raise

    return processed

def send_lure_alert_email_callback(ctx, recipient, user_activity, at_time):
    """ The callback used by the tool to actually send emails. Exposed as public API so it can be
        used selectively in unit testing, if the email module has been mocked correctly. """
    # Send the lure email for this user.
    email_module.send_now(ctx, recipient, "EMAIL_LURE_ALERT", template_data={'user_activity':user_activity})
