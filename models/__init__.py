# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
#
from front.models import chips
from front.lib import utils

class UserChild(object):
    """ A mixin for children of the gamestate UserModel to provide access to the database
        context and user object in preditable ways. """
    @property
    def user(self):
        """ Return the UserModel at the root of the gamestate. Child Models which are
            members of UserModel collections must override this method and provide the
            UserModel instance at the root of the gamestate by walking the hierarchy. """
        raise NotImplementedError("UserChild Models must provided a user property.")

    @property
    def ctx(self):
        """ Return the database context that this Model was loaded from. This is assumed
            to be the same database context which loaded the root model, in this case the
            UserModel. """
        return self.user.ctx

    def approx_time_since(self, field_name):
        """ Returns a string which is a user friendly description of the amount of time
            that has elapsed since this model's epoch time field was 'arrived' at or will be
            'arriving' at.
            NOTE field_name must be a valid epoch time field.
            e.g. "In 8 hours or 8 hours ago"
            """
        assert field_name in self.fields
        seconds = self.user.seconds_between_now_and_after_epoch(getattr(self, field_name))
        approx = utils.format_time_approx(abs(seconds))
        if abs(seconds) < 60:
            return "just now"
        if seconds > 0:
            return "in " + approx
        else:
            return approx + " ago"

    def approx_time_between(self, field_name_1, field_name_2):
        """ Returns a string which is a user friendly description of the amount of time
            that has elapsed between two epoch time fields on this model.
            field_name_1 should be the 'earlier' of the two.
            NOTE field_names must be a valid epoch time field.
            e.g. "8 hours"
            """
        assert field_name_1 in self.fields
        assert field_name_2 in self.fields
        seconds_between = getattr(self, field_name_2) - getattr(self, field_name_1)
        return utils.format_time_approx(abs(seconds_between))

class EpochDatetimeField(chips.ComputedField):
    """ This ComputedField assumes the wrapped field value is seconds since the user epoch and
        returns that value as a datetime object. This class assumes that the Model this is attached
        to has a user property which is an instance of UserModel. """
    def create_computed_field(self, model_class, computed_field):
        wrapped_field = self.wrapped_field
        def getter(self):
            return self.user.after_epoch_as_datetime(getattr(self, wrapped_field))
        setattr(model_class, computed_field, property(getter))

### region_list helpers
def RegionPack(region_id, center=None, verts=None):
    """ This function packs a region_id and the constructor overrides for that Region
        into a tuple. Only center or verts can be overridden currently and only one of
        those per Region. The resulting tuple looks like:
        (region_id, {region_constructor_args}) """
    region_args = {}
    if center != None:
        assert verts is None
        region_args['center'] = center
    if verts != None:
        assert center is None
        region_args['verts'] = verts
    return (region_id, region_args)

def convert_to_region_descriptions(region_ids_or_packs):
    """ This function consumes a list of a mix of region_ids and/or RegionPack objects
        and normalizes the data so that it is ready to reliable be turned into Region objects. """
    region_descriptions = []
    for region_id_or_pack in region_ids_or_packs:
        if isinstance(region_id_or_pack, basestring):
            assert region_id_or_pack not in region_descriptions
            region_descriptions.append((region_id_or_pack, {}))
        else:
            assert region_id_or_pack[0] not in region_descriptions
            region_descriptions.append(region_id_or_pack)
    return region_descriptions
