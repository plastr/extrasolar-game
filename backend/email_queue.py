# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
import uuid

from front.lib import db, gametime, get_uuid, email_ses

import logging
logger = logging.getLogger(__name__)

def enqueue_email_message(ctx, email_message):
    """
    Request that a given EmailMessage be added to the email sending queue.
    :param ctx: The database context.
    :param email_message: The email_module.EmailMessage to be sent.
    """
    params = {}
    params['queue_id']      = uuid.uuid1()
    params['email_from']    = email_message.email_from
    params['email_to']      = email_message.email_to
    params['email_subject'] = email_message.subject
    params['body_html']     = email_message.body_html
    params['created']       = gametime.now()
    with db.conn(ctx) as ctx:
        db.run(ctx, "email_queue/insert_queued_email", **params)

def process_email_queue(ctx):
    '''
    Find all rows in the email_queue and send them all via SES. If the email is sent to SES successfully,
    then the row is deleted from the queue.
    :param ctx: The database context.
    Returns the number of queued_emails sent.
    '''
    with db.conn(ctx) as ctx:
        processed = 0
        rows = db.rows(ctx, 'email_queue/select_unsent_queued_emails')
        for row in rows:
            try:
                queued_row = QueuedRow(**row)
                # Attempt to send the email via the Amazon SES module.
                email_ses.send_email(queued_row.email_from, queued_row.email_to,
                                     queued_row.email_subject, queued_row.body_html)

                # If no exception occurred sending this queued email, delete it from the database and
                # commit the transaction.
                queued_row.delete(ctx)
                db.commit(ctx)
                processed += 1

            except Exception, e:
                logger.exception("Sending queued email failed for queue_id:[%s] to address:[%s] subject:[%s] [%s]",
                    queued_row.queue_id, queued_row.email_to, queued_row.email_subject, e.message)
                # If any exception occurs sending this email, rollback the transaction
                # and try the next queued email row.
                db.rollback(ctx)

    return processed

class QueuedRow(object):
    """ Wraps the fields from an email_queue database row. """
    fields = frozenset(['queue_id', 'email_from', 'email_to', 'email_subject', 'body_html', 'created'])
    def __init__(self, **kwargs):
        for field in self.fields:
            value = kwargs[field]
            # Values the come out of the database as unicode objects, like the rendered body which is stored
            # in a TEXT UTF-8 encoded field, need to be converted back to UTF-8 encoded str objects so that
            # the Amazon SES library and API will accept the values.
            if isinstance(value, unicode):
                value = value.encode("utf-8")
            setattr(self, field, value)
        self.queue_id = get_uuid(self.queue_id)

    def delete(self, ctx):
        db.run(ctx, 'email_queue/delete_queued_email', queue_id=self.queue_id)
