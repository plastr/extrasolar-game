# Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
# All rights reserved.
import pkg_resources

from front import models
from front.lib import db, gametime
from front.data import load_json, schemas
from front.models import chips
from front.callbacks import run_callback, CAPABILITY_CB

# The path relative to this package where the mission data is stored.
CAPABILITY_DEFINITIONS = pkg_resources.resource_filename('front', 'data/capability_definitions.json')

class Capability(chips.Model, models.UserChild):
    """
    Holds the parameters for a single capability.
    """
    # These fields come from the capability definitions JSON file.
    DEFINITION_FIELDS = frozenset(['free_uses', 'available_on_rovers', 'rover_features', 'always_unlimited'])

    id_field = 'capability_key'
    fields = frozenset(['uses', 'unlimited', 'available']).union(DEFINITION_FIELDS)
    # These JSON fields are used to determine the available and unlimited values, which are
    # all the client will rely on/be able to see.
    server_only_fields = frozenset(['available_on_rovers', 'always_unlimited'])

    def __init__(self, capability_key, user, uses):
        definition = get_capability_definition(capability_key)
        # The initial values of unlimited and available are determined by the callbacks.
        # Use None as sentinels to indicate that the values will be set after super is called.
        super(Capability, self).__init__(capability_key=capability_key, uses=uses,
                                         unlimited=None, available=None, **definition)

        # Set the values of unlimited and available now that super has been called so that we can use
        # the capability object in the callbacks themselves (albeit with bogus unlimited and available values
        # which will be set by the callback return values).
        self.set_silent(unlimited = self._unlimited_current_value(user))
        self.set_silent(available = self._available_current_value(user))

    @property
    def user(self):
        # self.parent is user.capabilities, the parent of that is the User itself
        return self.parent.parent

    def is_available(self):
        return self.available == 1

    def is_unlimited(self):
        return self.unlimited == 1

    def is_always_unlimited(self):
        return self.always_unlimited == 1

    def provides_rover_feature(self, metadata_key):
        """ Returns True if this capability provides (allows to be used) the given rover feature (metadata key). """
        return metadata_key in self.rover_features

    def has_uses(self):
        """ Returns True if this capability has uses left (can be used by the user).
            The capability must be available, and be either unlimited or have free_uses remaining. """
        if not self.is_available():
            return False
        if self.is_unlimited():
            return True
        else:
            return self.uses < self.free_uses

    def increment_uses(self):
        """ Increment the number of uses for this capability. """
        assert self.is_available()
        assert self.has_uses()
        new_uses = self.uses + 1
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'insert_or_update_capability_uses', user_id=self.user.user_id,
                   capability_key=self.capability_key, uses=new_uses, created=gametime.now())
            self.uses = new_uses # Make our state mirror the database's
            self.send_chips(ctx, self.user)

    def decrement_uses(self):
        """ Decrement the number of uses for this capability. """
        assert self.is_available()
        assert self.uses > 0
        new_uses = self.uses - 1
        with db.conn(self.ctx) as ctx:
            db.run(ctx, 'insert_or_update_capability_uses', user_id=self.user.user_id,
                   capability_key=self.capability_key, uses=new_uses, created=gametime.now())
            self.uses = new_uses # Make our state mirror the database's
            self.send_chips(ctx, self.user)

    def available_and_unlimited_refresh(self):
        """
        Compare the stored available and unlimited field values in this instance to the values returned
        from the callbacks. If the values in the callbacks are different, update the instance values
        and issue a chip. This method must be called whenever a gamestate change occurs which might
        affect the available or unlimited values of a capability, e.g. number of rovers changed or new purchase.
        """
        current_unlimited = self._unlimited_current_value(self.user)
        current_available = self._available_current_value(self.user)
        if current_unlimited != self.unlimited or current_available != self.available:
            if current_unlimited != self.unlimited:
                run_callback(CAPABILITY_CB, "unlimited_value_changing", self.capability_key, capability=self, user=self.user)
                old_value = self.unlimited
                self.unlimited = current_unlimited
                run_callback(CAPABILITY_CB, "unlimited_value_changed", self.capability_key,
                             capability=self, user=self.user, old_value=old_value, new_value=current_unlimited)
            if current_available != self.available:
                run_callback(CAPABILITY_CB, "available_value_changing", self.capability_key, capability=self, user=self.user)
                old_value = self.available
                self.available = current_available
                run_callback(CAPABILITY_CB, "available_value_changed", self.capability_key,
                             capability=self, user=self.user, old_value=old_value, new_value=current_available)
            with db.conn(self.ctx) as ctx:
                self.send_chips(ctx, self.user)

    def _unlimited_current_value(self, user):
        return run_callback(CAPABILITY_CB, "unlimited_current_value", self.capability_key, capability=self, user=user)

    def _available_current_value(self, user):
        return run_callback(CAPABILITY_CB, "available_current_value", self.capability_key, capability=self, user=user)

def all_rover_features():
    """ Return the unique set of all rover feature metadata keys listed in the
        capability definition rover_features fields. """
    return _g_all_rover_features

def is_known_capability_key(capability_key):
    """ Returns True if the given capability_key was defined in the capability definitions. """
    return capability_key in all_capability_definitions()

def get_capability_definition(capability_key):
    """
    Return the capability definition as a dictionary for the given capability key.

    :param capability_key: str key for this capability definition e.g CAP_*. Defined in
    capability_definitions.json
    """
    return all_capability_definitions()[capability_key]

def all_capability_definitions():
    """ Return the capabilities as loaded from the JSON data file. """
    return _g_capability_definitions

_g_capability_definitions = None
_g_all_rover_features = None
def init_module():
    global _g_capability_definitions
    global _g_all_rover_features
    if _g_capability_definitions is not None: return

    _g_capability_definitions = load_json(CAPABILITY_DEFINITIONS, schema=schemas.CAPABILITY_DEFINITIONS)
    _g_all_rover_features = set()

    # Cache all of the known rover features.
    for definition in _g_capability_definitions.itervalues():
        _g_all_rover_features.update(definition['rover_features'])
