# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
"""This class represents the state of a single rover."""
import uuid

from front import models, rover_chassis
from front.lib import db, get_uuid, urls, geometry, gametime
from front.models import chips, target
from front.callbacks import run_callback, ROVER_CB, TARGET_CB

def create_new_lander(ctx, lat, lng):
    """
    Insert a row into the landers table with the given parameters.
    Returns the lander attributes as a dict.
    """
    # Note: This is not a full-fledged Model.
    lander_id = uuid.uuid1()
    db.run(ctx, "insert_lander", lander_id=lander_id, lat=lat, lng=lng)
    return {'lander_id':lander_id, 'lat':lat, 'lng':lng}

def create_new_rover(ctx, user, lander, rover_key, activated_at, active=1):
    """
    :param ctx: The database context.
    :param user: The User who will own this rover.
    :param lander: A dict with the lander attributes returned by create_new_lander.
    :param rover_key: A string key that uniquely identifies this rover in user's gamestate, e.g. RVR_S1_INITIAL
    :param activated_at: int When this rover first became active in the game, in number of seconds since user.epoch_now.
    :param active: 0 or 1 to indicate if the new rover should be active.
    """
    assert rover_key.startswith("RVR_"), "Rover keys must start with a RVR_ prefix."
    # Be sure all capabilities are loaded so their available and unlimited values can be
    # compared pre and post rover creation, as they might change and require a chip.
    user.capabilities.available_and_unlimited_prepare_refresh()

    with db.conn(ctx) as ctx:
        params = {}
        params['rover_id']     = uuid.uuid1()
        params['lander_id']    = lander['lander_id']
        params['lander_lat']   = lander['lat']
        params['lander_lng']   = lander['lng']
        params['rover_key']    = rover_key
        params['activated_at'] = activated_at
        params['active']       = active
        # Create the rover.
        # user_id is only used when creating and selecting the Rover in the database, it is not loaded
        # by chips as the user.rovers collection takes care of assigning a User to a Rover.
        db.run(ctx, "insert_rover", user_id=user.user_id, created=gametime.now(), **params)
        rover = user.rovers.create_child(**params)
        rover.send_chips(ctx, user)

        # A new rover means that a capability which is using the rover count to determine
        # availablity might now be available.
        user.capabilities.available_and_unlimited_refresh()

        return rover

class Rover(chips.Model, models.UserChild):
    # These fields come from the capabilities_callbacks.
    CALLBACK_FIELDS = frozenset(['max_unarrived_targets', 'min_target_seconds', 'max_target_seconds', 'max_travel_distance'])

    id_field = 'rover_id'
    fields = frozenset(['lander', 'rover_key', 'rover_chassis', 'activated_at', 'active']).union(CALLBACK_FIELDS)
    collections = frozenset(['targets'])

    rover_chassis = chips.LazyField("rover_chassis", lambda m: m._load_rover_chassis())
    # These fields have their values lazy loaded from functions in the rover_callbacks module.
    # They are lazy loaded as some of those callbacks expect the rover to be fully created and in the user
    # hierarchy when deriving the current field value and so we delay populating the values for these fields
    # until after the Rover has had its other fields initialized and it has been added to the rovers collection.
    max_unarrived_targets = chips.LazyField("max_unarrived_targets", lambda m: m._callback_field_current_value('max_unarrived_targets'))
    min_target_seconds    = chips.LazyField("min_target_seconds", lambda m: m._callback_field_current_value('min_target_seconds'))
    max_target_seconds    = chips.LazyField("max_target_seconds", lambda m: m._callback_field_current_value('max_target_seconds'))
    max_travel_distance   = chips.LazyField("max_travel_distance", lambda m: m._callback_field_current_value('max_travel_distance'))

    # user_id, created and updated are database only fields.
    def __init__(self, rover_id, lander_id, lander_lat, lander_lng, rover_key, activated_at, active,
                user_id=None, created=None, updated=None):
        """
        Construct a Rover Model object.

        :param ctx: The database context.
        :param rover_id: The UUID for this Rover. May be a string or UUID object.
        :param lander_id: The UUID for this Lander. May be a string or UUID object.
        :param lander_lat: float The latitude of this Rover's lander. From the landers table.
        :param lander_lng: float The longitude of this Rover's lander. From the landers table.
        :param rover_key: A string key that uniquely identifies this rover in user's gamestate, e.g. RVR_S1_INITIAL
        :param activated_at: int When this rover first became active in the game, in number of seconds since user.epoch_now.
        :param active: int An int boolean whether this Rover is active or not.
        """
        # If the UUID data is coming straight from the database row, convert it to a UUID instance.
        rover_id = get_uuid(rover_id)
        lander_id = get_uuid(lander_id)
        super(Rover, self).__init__(
            rover_id = rover_id,
            lander = {'lander_id':lander_id, 'lat':lander_lat, 'lng':lander_lng},
            targets = TargetCollection.load_later('targets', self._load_targets),
            rover_key = rover_key, activated_at = activated_at, active = active)

    @property
    def user(self):
        # self.parent is user.rovers, the parent of that is the user itself
        return self.parent.parent

    def is_active(self):
        return self.active == 1

    @property
    def url_target_create(self):
        return urls.rover_target_create(self.rover_id)

    def location_at_time(self, at_time):
        """
        Returns a tuple with (lat, lng, yaw) for the interpolated position of the rover
        at the given time.  If at_time is prior than any target start_time, return the
        first target's position.
        at_time is in terms of seconds since user.epoch
        """
        sorted_targets = self.targets.by_arrival_time()
        # Search the list to find the two targets with start_times prior to at_time.
        index = 0
        for index, target in enumerate(sorted_targets):
            if (target.start_time > at_time):
                break
        # If the currently indexed target still has an earlier start_time than at_time, increment once more.
        if sorted_targets[index].start_time <= at_time:
            index += 1
           
        current_target = sorted_targets[max(0, index-1)] 
        prev_target    = sorted_targets[max(0, index-2)]       

        return geometry.interpolate_between_targets(current_target, prev_target, at_time)

    def distance_traveled(self):
        """ Returns the total distance, in meters, this rover has traveled in the game so far.
            This method only considers targets which have been arrived at as of the current gametime. """
        sorted_targets = self.targets.arrived_at()
        distance = 0
        for t in sorted_targets:
            if t.next() is not None and t.next().has_been_arrived_at():
                distance += t.straight_distance_between_targets(t.next())
        return distance

    def distance_will_have_traveled(self):
        """ Returns the total distance, in meters, this rover will have traveled in the game so far.
            This method INCLUDES targets which have been created but not yet been arrived at. """
        sorted_targets = self.targets.by_arrival_time()
        distance = 0
        for t in sorted_targets:
            if t.next() is not None:
                distance += t.straight_distance_between_targets(t.next())
        return distance

    def mark_inactive(self):
        with db.conn(self.ctx) as ctx:
            db.run(ctx, "update_rover_inactive", rover_id=self.rover_id)
            self.active = 0  # Make our state mirror the database's.
            self.send_chips(ctx, self.user)

    def abort_target(self, target):
        """
        Attempt to abort the given target which must be a target created for this rover.
        An exception will be raised if this target does not belong to this rover or if it is not
        allowed to be aborted or if any future targets past it cannot be aborted.
        See delete_target for more details on what chips and data are deleted if this method succeeds.
        """
        assert target in self.targets
        to_delete = []
        current = target
        # This target and any future ones will be deleted.
        while current is not None:
            # Assert that this and all future targets can be aborted.
            assert current.can_abort(), "Cannot abort target. [%s][%d]" % (target.target_id, target.user.epoch_now)
            to_delete.append(current)
            current = current.next()
        # Now delete the targets, newest first.
        for t in reversed(to_delete):
            self.delete_target(t)

    def delete_target(self, target):
        """
        Delete this target and any related data (highlights, rects, images, metadata, and sounds) and issue a
        DEL chip for this target.
        NOTE: If the image has been rendered AND map tiles have been rendered, this method
        makes no attempt to cleanup those map tiles. This will need to be handled in a special
        way if need be.
        """
        assert target in self.targets
        # Inform the callback that this target is being deleted.
        run_callback(TARGET_CB, "target_will_be_deleted", ctx=self.ctx, user=self.user, target=target)

        with db.conn(self.ctx) as ctx:
            db.run(ctx, "delete_highlighted_target", target_id=target.target_id)
            db.run(ctx, "delete_target_image_rects", target_id=target.target_id)
            db.run(ctx, "delete_target_images", target_id=target.target_id)
            db.run(ctx, "delete_target_metadata", target_id=target.target_id)
            db.run(ctx, "delete_target_sounds", target_id=target.target_id)
            db.run(ctx, "delete_target", target_id=target.target_id)
        self.targets.delete_child(target)
        target.send_chips(self.ctx, self.user)

    ## Capabilities Methods.
    # These methods are used to determine certain limitations of this rover and if certain capabilities
    # are enabled for this rover.
    def can_use_feature(self, metadata_key):
        """
        Returns True if the given rover feature, as described by a target metadata key, has uses available.
        If more than one capability is available, has uses left and  reports itself as providing the given rover
        feature an exception will be raised.
        """
        capabilities = self.user.capabilities.provides_rover_feature_has_uses(metadata_key)
        # At a given time at most one capability is allowed to provide a rover feature.
        assert len(capabilities) < 2
        if len(capabilities) == 1:
            return True
        else:
            return False

    def use_feature(self, metadata_key):
        """
        Record the given rover feature, as described by a target metadata key (TGT_*), as being used once.
        It is recommended to use can_use_feature before calling this method to be sure there is a capability
        which provides the given rover feature, is available and has uses. If no capability is found, an exception
        will be raised.
        """
        capabilities = self.user.capabilities.provides_rover_feature_has_uses(metadata_key)
        assert len(capabilities) == 1
        capabilities[0].increment_uses()

    def can_reuse_feature(self, metadata_key):
        """
        Returns True if the given rover feature, as described by a target metadata key, can be 'reused', meaning
        that there is a capability which provides that feature and its uses count can be decremented.
        If more than one capability is available, can have its uses left decremented and reports itself as
        providing the given rover feature an exception will be raised.
        """
        capabilities = self.user.capabilities.provides_rover_feature(metadata_key)
        # At a given time at most one capability is allowed to provide a rover feature.
        assert len(capabilities) < 2
        if len(capabilities) == 1:
            return True
        else:
            return False

    def reuse_feature(self, metadata_key):
        """
        Record the given rover feature, as described by a target metadata key (TGT_*), has been 'unused' once
        so it can be reused.
        This should be called at the very least if a target is aborted which had used this rover feature.
        It is recommended to use can_reuse_feature before calling this method to be sure there is a capability
        which provides the given rover feature, is available and has uses which can be decremented.
        If no capability is found, an exception will be raised.
        """
        # Find any _available_ capabilities which provide this rover feature, even if they have no free uses left
        # as this decrement might free up uses.
        capabilities = self.user.capabilities.provides_rover_feature(metadata_key)
        assert len(capabilities) == 1
        capabilities[0].decrement_uses()

    def capabilities_changing(self):
        """
        This is called just before any capability available or unlimited fields are changed.
        """
        # Since at least some of the callback derived rover fields depend on capabilities to determine their
        # values and those fields are lazy, trigger the lazy loaders for all those fields so that we have values
        # to compare to in capabilities_changed().
        for field in self.CALLBACK_FIELDS:
            getattr(self, field)

    def capabilities_changed(self):
        """
        This is called whenever any capability available or unlimited fields change.
        """
        # Since at least some of the callback derived rover fields depend on capabilities to determine their
        # values, iterate through every callback field and compare its currently stored value vs. the value
        # currently being returned by the callback. If the values are different, then call setattr to update
        # the stored value and then issue a MOD chip if anything changed.
        values_changed = False
        for field in self.CALLBACK_FIELDS:
            current_value = getattr(self, field)
            callback_value = self._callback_field_current_value(field)
            if current_value != callback_value:
                setattr(self, field, callback_value)
                values_changed = True
        if values_changed:
            with db.conn(self.ctx) as ctx:
                self.send_chips(ctx, self.user)

    def _callback_field_current_value(self, field):
        assert field in self.CALLBACK_FIELDS
        return run_callback(ROVER_CB, field, user=self.user, rover=self)

    def to_struct_renderer_input(self):
        return self.to_struct(fields=['active'])

    def modify_struct(self, struct, is_full_struct):
        if is_full_struct:
            struct['urls'] = {'target':self.url_target_create}
        return struct

    ## Lazy load attribute methods.
    def _load_rover_chassis(self):
        return rover_chassis.for_key[self.rover_key]

    ## Lazy load collection methods.
    def _load_targets(self):
        with db.conn(self.ctx) as ctx:
            rows = ctx.row_cache.get_rows_from_query("gamestate/select_targets_by_user_id", self.rover_id)
            if rows is not None:
                return rows
            else:
                return db.rows(ctx, "select_targets_by_rover_id", rover_id=self.rover_id)

class TargetCollection(chips.Collection):
    model_class = target.Target

    def first(self):
        """ Return the first to be arrived at target. """
        return self.by_arrival_time()[0]

    def last(self):
        """ Return the last to be arrived at target. """
        return self.by_arrival_time()[-1]

    def by_arrival_time(self, newest_first=False):
        """ Return the list of targets for this rover sorted by arrival_time. """
        return sorted(self.values(), key=lambda t: t.arrival_time, reverse=newest_first)

    def arrived_at(self, newest_first=False):
        """ Return the list of arrived at targets for this rover sorted by arrival_time. """
        return [t for t in self.by_arrival_time(newest_first=newest_first) if t.has_been_arrived_at()]

    def unarrived_at(self, newest_first=False):
        """ Return the list of unarrived at targets for this rover sorted by arrival_time. """
        return [t for t in self.by_arrival_time(newest_first=newest_first) if not t.has_been_arrived_at()]

    def pictures(self, newest_first=False):
        """ Returns the sorted list of ALL targets which are pictures, regardless of process or
            whether they have been arrived at. """
        return [t for t in self.by_arrival_time(newest_first=newest_first) if t.is_picture()]

    def processed_pictures(self, newest_first=False):
        """ Returns the sorted list of all targets which have processed pictures and have been arrived at. """
        return [t for t in self.arrived_at(newest_first=newest_first) if t.is_picture() and t.is_processed()]

    def split_on_target(self, target):
        """
        Split the list of sorted targets for this rover using the given target as the pivot.
        Return a tuple of lists. The first list is all targets older than the given target,
        with the given target the last element in the list. The second list is any targets
        newer than the given target.
        """
        assert target in self
        # Count newest targets starting at the end of the list until we find the target
        # we are working on.
        sorted_targets = self.by_arrival_time()
        count = 0
        for count, current_target in enumerate(reversed(sorted_targets)):
            if current_target.target_id == target.target_id:
                break
        # Slice off any newer targets if there are any.
        if count > 0:
            return (sorted_targets[:len(sorted_targets) - count], sorted_targets[-count:])
        else:
            return (sorted_targets, [])
