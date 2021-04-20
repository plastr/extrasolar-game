# Copyright (c) 2010-2013 Lazy 8 Studios, LLC.
# All rights reserved.
import pkg_resources

from front import models
from front.lib import db
from front.data import load_json, schemas
from front.models import chips
from front.models import capability as capability_module
from front.callbacks import run_callback, VOUCHER_CB

# The path relative to this package where the mission data is stored.
VOUCHER_DEFINITIONS = pkg_resources.resource_filename('front', 'data/voucher_definitions.json')

def deliver_new_voucher(ctx, user, voucher_key, suppress_callbacks=False):
    """
    This creates a new Voucher object and persists it for this user. These are used to unlock
    capabilities and are part of the store/purchase system.

    :param ctx: The database context.
    :param user: User object, this comes from the session usually
    :param voucher_key: str The voucher key identifying the voucher to deliver to this user. e.g. VCH_*
    """
    # Be sure all capabilities are loaded so their available and unlimited values can be
    # compared pre and post voucher creation, as they might change and require a chip.
    user.capabilities.available_and_unlimited_prepare_refresh()
    # Be sure all available products are loaded so their available and price values can be
    # compared pre and post voucher creation, as they might change and require a chip.
    user.shop.available_products.available_and_price_prepare_refresh()
    # Be sure that current_voucher_level is loaded as its value might be changing.
    user.current_voucher_level_prepare_refresh()

    params = {}
    params['voucher_key'] = voucher_key
    params['delivered_at'] = user.epoch_now

    with db.conn(ctx) as ctx:
        # user_id is only used when creating the Voucher in the database, it is not loaded
        # by chips as the user.vouchers collection takes care of assigning Voucher to a User.
        db.run(ctx, "insert_voucher", user_id=user.user_id, **params)
        v = user.vouchers.create_child(**params)
        v.send_chips(ctx, user)

    # A new voucher means that a capability which is using the voucher to determine
    # unlimited state might now be unlimited.
    user.capabilities.available_and_unlimited_refresh()
    # A new voucher means that a product which delivers that voucher might no longer be available
    # (for instance) if this voucher was delivered by a gift.
    user.shop.available_products.available_and_price_refresh()
    # A new voucher most likely means a new current_voucher_level for this user.
    user.current_voucher_level_refresh()

    if not suppress_callbacks:
        # Inform the callbacks that this voucher was delivered.
        run_callback(VOUCHER_CB, "voucher_was_delivered", voucher_key, ctx=ctx, user=user, voucher=v)

    return v

class Voucher(chips.Model, models.UserChild):
    """
    Holds the parameters for a single voucher.
    """
    # These fields come from the voucher definitions JSON file.
    DEFINITION_FIELDS = frozenset(['name', 'description', 'unlimited_capabilities', 'not_available_after'])

    id_field = 'voucher_key'
    fields = frozenset(['delivered_at']).union(DEFINITION_FIELDS)
    # These JSON fields are used to determine the availability of capabilities or vouchers, but the client
    # will rely on the capabilities themselves to tell them what is active/available.
    server_only_fields = frozenset(['unlimited_capabilities', 'not_available_after'])

    # user_id and created are database only fields.
    def __init__(self, voucher_key, delivered_at, user_id=None, created=None):
        definition = get_voucher_definition(voucher_key)
        super(Voucher, self).__init__(voucher_key=voucher_key, delivered_at=delivered_at, **definition)

    @property
    def user(self):
        # self.parent is user.vouchers, the parent of that is the User itself
        return self.parent.parent

    def does_specify_capability_as_unlimited(self, capability):
        """ Returns True if the given capability is specified as being unlimited by this
            voucher (using unlimited_capabilities).
            NOTE: The supplied capability object might be in the process of being initialized via callbacks
            therefore it is not safe to rely on its unlimited and available values. """
        for unlimited in self.unlimited_capabilities:
            if unlimited == capability.capability_key:
                return True
        return False

def is_voucher_key_available(voucher_key, user):
    """ Returns True if the given voucher_key is available to be redeemed by the given user.
        Returns False if the voucher is already owned by the user or is listed in the not_available_after property
        of an already owned voucher. """
    assert is_known_voucher_key(voucher_key)
    # If the voucher being tested has already been granted then it is no longer available
    # (e.g. to be granted via a gift)
    if voucher_key in user.vouchers:
        return False
    # If the voucher being tested has any vouchers listed in its not_available_after list already granted to the user
    # then it is no longer available.
    not_available_after = get_voucher_definition(voucher_key)['not_available_after']
    for v_key in not_available_after:
        if v_key in user.vouchers:
            return False
    return True

def is_known_voucher_key(voucher_key):
    """ Returns True if the given voucher_key was defined in the voucher definitions. """
    return voucher_key in all_voucher_definitions()

def get_voucher_definition(voucher_key):
    """
    Return the voucher definition as a dictionary for the given voucher key.

    :param voucher_key: str key for this voucher definition e.g VCH_*. Defined in
    voucher_definitions.json
    """
    return all_voucher_definitions()[voucher_key]

def all_voucher_definitions():
    """ Load the JSON file that contains the voucher definitions """
    return _g_voucher_definitions

_g_voucher_definitions = None
def init_module():
    global _g_voucher_definitions
    if _g_voucher_definitions is not None: return

    _g_voucher_definitions = load_json(VOUCHER_DEFINITIONS, schema=schemas.VOUCHER_DEFINITIONS)
    # Verify every capability_key listed in unlimited_capabilities is known/valid and is unique.
    for voucher_key, definition in _g_voucher_definitions.iteritems():
        unlimited_capabilities = definition['unlimited_capabilities']
        for capability_key in unlimited_capabilities:
            if unlimited_capabilities.count(capability_key) > 1:
                raise Exception("Duplicate capability_key in voucher definition unlimited_capabilities [%s][%s]" % (capability_key, voucher_key))
            if not capability_module.is_known_capability_key(capability_key):
                raise Exception("capability_key is not known in voucher definition [%s][%s]" % (capability_key, voucher_key))
        not_available_after = definition['not_available_after']
        for v_key in not_available_after:
            if not_available_after.count(v_key) > 1:
                raise Exception("Duplicate voucher_key in voucher definition not_available_after [%s]" % v_key)
            if v_key not in _g_voucher_definitions:
                raise Exception("voucher_key is not known in not_available_after definition [%s]" % v_key)
        # Convert the JSON lists into Python sets.
        definition['unlimited_capabilities'] = set(unlimited_capabilities)
        definition['not_available_after'] = set(not_available_after)
