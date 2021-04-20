# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.lib import utils

class BaseCallbacks(object):
    __metaclass__ = utils.NoOverrideRequiredNotNoneMetaClass

    @classmethod
    def unlimited_current_value(cls, capability, user):
        """
        A callback which returns the current 'unlimited' field value for this capability based on the gamestate
        of the provided user or any other criteria desired.
        NOTE: The capability object supplied might be in the process of being initialized and its current
        unlimited or available value should not be used.
        The return value is an integer boolean, 1 or 0.
        """
        if capability.is_always_unlimited():
            return 1
        for voucher in user.vouchers.itervalues():
            if voucher.does_specify_capability_as_unlimited(capability):
                return 1
        return 0

    @classmethod
    def available_current_value(cls, capability, user):
        """
        A callback which returns the current 'available' field value for this capability based on the gamestate
        of the provided user or any other criteria desired.
        NOTE: The capability object supplied might be in the process of being initialized and its current
        unlimited or available value should not be used.
        The return value is an integer boolean, 1 or 0.
        """
        # If the user has any rover with the chassis listed in any available_on_rovers, then capability is available
        # FUTURE: Check only active rovers so capabilities can be made unavailable as the game moves between seasons.
        active_rover_chassis = set([r.rover_chassis for r in user.rovers.itervalues()])
        if len(set(capability.available_on_rovers).intersection(active_rover_chassis)) > 0:
            return 1
        else:
            return 0

    @classmethod
    def unlimited_value_changing(cls, capability, user):
        """
        A callback which is called just before the 'unlimited' field value for this capability is being changed.
        NOTE: This is NOT called during the initialization of a Capability object, only if the value changes later.
        """
        # Inform the lazy loaded rover collection that some of its values might be changing as a capability's
        # unlimited value is changing. This forces the lazy loaded collection to be loaded so original
        # and new values can be compared for sending chips and the like.
        user.rovers.callback_values_prepare_refresh()

    @classmethod
    def unlimited_value_changed(cls, capability, user, old_value, new_value):
        """
        A callback which is called just after the 'unlimited' field value for this capability has changed.
        The old_value and new_value will contain the previous and new values for the field.
        NOTE: This is NOT called during the initialization of a Capability object, only if the value changes later.
        """
        # Only equipped to deal a capability becoming unlimited currently.
        assert new_value == 1
        # Inform the rover collection (and therefore every rover) that the capabilities have changed and that
        # those objects should update any values they have which depend on capability state and send any chips.
        user.rovers.callback_values_refresh()

    @classmethod
    def available_value_changing(cls, capability, user):
        """
        A callback which is called just before the 'available' field value for this capability is being changed.
        NOTE: This is NOT called during the initialization of a Capability object, only if the value changes later.
        """
        pass

    @classmethod
    def available_value_changed(cls, capability, user, old_value, new_value):
        """
        A callback which is called just after the 'available' field value for this capability has changed.
        The old_value and new_value will contain the previous and new values for the field.
        NOTE: This is NOT called during the initialization of a Capability object, only if the value changes later.
        """
        assert new_value == 1
        pass
