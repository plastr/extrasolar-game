# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from collections import Counter

from front import models
from front.lib import db, gametime
from front.models import chips

import logging
logger = logging.getLogger(__name__)

# This is the value of the lower 4 bits of the species_id that indicates
# this species_id has no subspecies data.
NO_SUBSPECIES = 0

def create_new_image_rect_from_score(ctx, target, rect_score):
    """
    This creates a new ImageRect object for the given Target based on the RectScore object processed
    by the checkspecies system. It is assumed all user data being provided here has been validated
    by the checkspecies system.
    Returns the newly created ImageRect object.

    Fields in params:
    :param seq: int, The unique id for this region within the target image.
    :param xmin: float, These four values are the rectangle coordinates [0.0, 1.0] within the image.
    :param ymin: ditto
    :param xmax: ditto
    :param ymax: ditto
    :param density: float, The pixel density of species_id.
    species_id: int, The most important species seen in this region (inorganic has higher weight).
    subspecies_id: int, The corresponding subspecies_id.
    """
    params = {}
    # The rectangle sequence and dimensions.
    params['seq']  = rect_score.seq
    params['xmin'] = rect_score.xmin
    params['xmax'] = rect_score.xmax
    params['ymin'] = rect_score.ymin
    params['ymax'] = rect_score.ymax
    # And the density and detected species data.
    params['species_id'] = rect_score.species_id
    params['subspecies_id'] = rect_score.subspecies_id
    params['density'] = rect_score.density

    with db.conn(ctx) as ctx:
        db.run(ctx, "insert_image_rect", user_id=target.user.user_id, target_id=target.target_id, created=gametime.now(), **params)
        image_rect = target.image_rects.create_child(**params)
        image_rect.send_chips(ctx, target.user)
    return image_rect


class SpeciesRect(object):
    """ This mixin class is meant to factor out support for returning lists of detected species
        and subspecies for both objects in the check_species module and ImageRect. Over the lifetime
        of the game, rectangles have supported detecting multiple species per rectangle or
        just one. We are keeping these methods as supporting lists/iterables in order to more easily
        change our minds about how many species per rect but also to avoid having to constantly do
        checkes against None/NO_SUBSPECIES when examining these values.
        It is expected that any class that mixes this class in will have a species_id and a 
        subspecies_id property, either of which can be None. (currently). """

    def detected_species(self):
        """ Returns a set of any species identified for this rectangle. """
        if self.species_id is not None:
            return set([self.species_id])
        else:
            return set()

    def detected_subspecies(self):
        """ Returns a dict of any subspecies identified for this rectangle for a given species_id.
            species_id -> set(subspecies_id, ...)
            Note that if a species_id was identified but no subspecies data was present
            (e.g. subspecies is 0) then the subspecies set will be empty.
            If no species were detected in this rectangle than an empty dict will be returned. """
        if self.species_id is None:
            return {}
        if self.subspecies_id is not None and self.subspecies_id != NO_SUBSPECIES:
            return {self.species_id: set([self.subspecies_id])}
        else:
            return {self.species_id: set()}


class ImageRect(chips.Model, models.UserChild, SpeciesRect):
    id_field = 'seq'
    fields = frozenset(['xmin', 'ymin', 'xmax', 'ymax', 'species_id', 'subspecies_id', 'density'])

    # user_id, target_id and created are database only fields.
    def __init__(self, user_id=None, target_id=None, created=None, **params):
        super(ImageRect, self).__init__(**params)

    @property
    def target(self):
        # self.parent is target.image_rects, the parent of that is the target itself
        return self.parent.parent

    @property
    def user(self):
        return self.target.user

    def species_count(self, only_subspecies_id=None):
        '''
        Returns a Counter object of the number of times a given species_id was
        detected in this rect.
        :param only_subspecies_id: int, if included, limit counts to this subspecies type.
        '''
        count = Counter()
        if self.species_id is not None:
            if only_subspecies_id is None or only_subspecies_id == self.subspecies_id:
                count[self.species_id] += 1
        return count

    def subspecies_count_for_species(self, species_id):
        '''
        Returns a Counter object of the number of times a given subspecies_id was
        observed for the indicated species.
        :param species_id: int, the id of the species that we're interested in.
        '''
        count = Counter()
        if species_id == self.species_id:
            count[self.subspecies_id] += 1
        return count

    def has_species(self):
        """ Returns True if any species were identified by this rect. """
        return len(self.species_count()) > 0
