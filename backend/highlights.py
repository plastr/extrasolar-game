# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
#
from front import target_image_types
from front.lib import db, get_uuid, gametime, urls
from front.callbacks import run_callback, TARGET_CB

import logging
logger = logging.getLogger(__name__)

def add_target_highlight(ctx, target):
    """ Mark the given Target object as highlighted (insert into highlighted_target table). """
    with db.conn(ctx) as ctx:
        db.run(ctx, "insert_highlighted_target", target_id=target.target_id, highlighted_at=gametime.now(),
               available_at=target.arrival_time_date)
        target.mark_highlighted()
        # Inform the target_callbacks that a target was highlighted
        run_callback(TARGET_CB, "target_was_highlighted", ctx=ctx, user=target.user, target=target)

def remove_target_highlight(ctx, target):
    """ Mark the given Target object as no longer highlighted (delete from highlighted_target table). """
    with db.conn(ctx) as ctx:
        db.run(ctx, "delete_highlighted_target", target_id=target.target_id)
        target.mark_unhighlighted()

def recent_highlighted_targets(ctx, count):
    """
    Returns a list of highlighted targets suitable for public API consumption, limited to the provided count.
    If somehow a highlighted target has no rendered images (the renderer is backed up or somehow
    a neutered or non-picture target was highlighted) this might mean that the API returns fewer targets
    than requested by the count value even though there might be enough highlighted targets.

    Example result:
        [{'target_id':UUID, 'url_photo':URL, 'url_thumbnail':URL, 'url_public_photo':URL}, {'target_id'...}]
    :param ctx: The database context.
    :param count: int, The maximum number of highlights to return.
    """
    # Returns all target_images rows for all recent highlighted photos.
    with db.conn(ctx) as ctx:
        rows = db.rows(ctx, "select_highlighted_targets_recent", limit=count, now=gametime.now())
    highlights = []
    # Track the most recently seen target_id. The target_images rows are returned in the order they were highlighted
    # and grouped together by target_id, so whenever the target_id changes all the image data for that target_id
    # has been seen by the loop.
    current_target_id = None
    current_target_images = {}
    for index, r in enumerate(rows):
        r_target_id = get_uuid(r['target_id'])
        # Initialize current_target_id to be the first rows target_id
        if current_target_id is None: current_target_id = r_target_id
        # New target has been seen or this is the last row, so finish processing previous target data.
        if r_target_id != current_target_id or index == len(rows) - 1:
            highlights.append({
                'target_id': current_target_id,
                'url_photo': current_target_images[target_image_types.PHOTO],
                'url_thumbnail': current_target_images[target_image_types.THUMB],
                # Can be None.
                'url_thumbnail_large': current_target_images.get(target_image_types.THUMB_LARGE),
                'url_public_photo': urls.target_public_photo(current_target_id)
            })
            current_target_id = r_target_id
            current_target_images = {}

        # NOTE: Some image URLs returned might not be absolute (initial and testing scene images)
        current_target_images[r['type']] = r['url']
    return highlights
