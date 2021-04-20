# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
#
import inspect

# The class name prefix which indicates a callback class.
CALLBACK_PREFIX = "_Callbacks"
# The base class name which provides default functionality.
BASE_CALLBACKS_CLASS = "BaseCallbacks"

# Lazy initialized mapping, see below for documentation.
CALLBACK_MODULES = None

# Constants to use for module_name parameters.
EMAIL_CB       = "email"
MESSAGE_CB     = "message"
MISSION_CB     = "mission"
TARGET_CB      = "target"
SPECIES_CB     = "species"
PROGRESS_CB    = "progress"
ACHIEVEMENT_CB = "achievement"
CAPABILITY_CB  = "capability"
SHOP_CB        = "shop"
VOUCHER_CB     = "voucher"
PRODUCT_CB     = "product"
GIFT_CB        = "gift"
ROVER_CB       = "rover"
USER_CB        = "user"
TIMER_CB       = "timer"

def callback_key_from_class(callback_class):
    """ Derive the 'key' or specific name of the given callback class by stripping
        CALLBACK_PREFIX from the name. Useful when a callback method cannot be provided
        this information by the caller. """
    if not callback_class.__name__.endswith(CALLBACK_PREFIX):
        raise Exception("callback_key cannot be called on %s" % callback_class)
    return callback_class.__name__.replace(CALLBACK_PREFIX, '')

def run_all_callbacks_flatten_results(module_name, callback_name, ctx, user, *args, **kwargs):
    """
    Runs all callback functions defined in the given module name with the given callback_name and
    flattens all non-None returned values into a single list, one at a time, which is then returned.
    e.g. callback1 -> [1,2,3], callback2 -> [4,5,6]
         return value -> [1,2,3,4,5,6]
    SEE: run_all_callbacks
    """
    return_values = run_all_callbacks(module_name, callback_name, ctx, user, *args, **kwargs)
    results = []
    for r in return_values:
        if r is not None:
            results.extend(r)
    return results

def run_all_callbacks(module_name, callback_name, ctx, user, *args, **kwargs):
    """
    Runs all callback functions defined in the given module name with the given callback_name and
    appends all return values from the callbacks one at a time to a list, which is then returned.
    NOTE: All remaining arguments are passed to each callback function in turn.
    SEE: run_callback
    """
    return_values = []
    for callback_class in get_all_callback_classes(module_name):
        callback_func = getattr(callback_class, callback_name)
        result = callback_func(ctx, user, *args, **kwargs)
        return_values.append(result)
    return return_values

def run_callback(module_name, callback_name, subtype=None, *args, **kwargs):
    """
    Runs a callback function if it is defined in the given module in a class called
    subtype_Callbacks. Returns None if the class is not defined in the module or the callback function
    is not defined in the class. Otherwise returns the return value of the callback function.
    :param module_name: The module name as a string, see _CB constants above.
    :param callback_name: str The name of the func object to search the callback class for.
    :param subtype: str The class name holding the callback func. _Callbacks will be appended.
        If subtype is None, only the callback fucntions in the BASE_CALLBACKS_CLASS will be run.
    NOTE: All remaining arguments are passed the callback function.
    """
    func = _get_callback_func(module_name, callback_name, subtype)
    if func is None:
        return None
    else:
        return func(*args, **kwargs)

def implements_callback(module_name, callback_name, subtype):
    """ Returns True if the given callback name is implemented/overridden by the specific
        subtype and not just implemented in the base class. """
    callback_class = get_callback_class(module_name, subtype)
    if callback_class is None:
        return False
    else:
        return callback_class.__dict__.get(callback_name) != None

# These getters are public API but intended for testing and debug tools.
def get_callback_class(module_name, subtype):
    """ Can return None. If no class implementation exists for the given subtype, the module is
        searched for a BASE_CALLBACKS_CLASS implemention which is used if found. """
    module = _get_module_from_name(module_name)
    if subtype is None:
        return _get_callback_base_class(module)
    try:
        return getattr(module, subtype + CALLBACK_PREFIX)
    # If the callback implementation for this subtype doesn't exist,
    # attempt to load the BASE_CALLBACKS_CLASS class.
    except AttributeError:
        return _get_callback_base_class(module)

def get_all_callback_classes(module_name):
    """ Returns all callback classes defined in the given module, excluding any BaseCallbacks class. """
    callback_classes = []
    module = _get_module_from_name(module_name)
    for name, callback_class in inspect.getmembers(module):
        if name.endswith(CALLBACK_PREFIX) and inspect.isclass(callback_class):
            callback_classes.append(callback_class)
    return callback_classes

## Private helper functions.
def _get_callback_func(module_name, callback_name, subtype=None):
    """ Can return None. """
    callback_class = get_callback_class(module_name, subtype)
    if callback_class is None:
        return None
    else:
        return getattr(callback_class, callback_name)

def _get_module_from_name(module_name):
    # Map a shorthand name to the callback module for that callback type.
    # This helps to avoid circular dependencies between the model modules
    # and their callback modules.
    # This is lazily initialized so that the callbacks can be imported inside the
    # function to avoid circular dependencies.
    global CALLBACK_MODULES
    if CALLBACK_MODULES is None:
        from front.callbacks import email_callbacks, message_callbacks, mission_callbacks, target_callbacks
        from front.callbacks import species_callbacks, progress_callbacks, achievement_callbacks, capability_callbacks
        from front.callbacks import shop_callbacks, voucher_callbacks, gift_callbacks, product_callbacks, rover_callbacks
        from front.callbacks import user_callbacks, timer_callbacks
        CALLBACK_MODULES = {
            EMAIL_CB:   email_callbacks,
            MESSAGE_CB: message_callbacks,
            MISSION_CB: mission_callbacks,
            TARGET_CB:  target_callbacks,
            SPECIES_CB: species_callbacks,
            PROGRESS_CB: progress_callbacks,
            ACHIEVEMENT_CB: achievement_callbacks,
            CAPABILITY_CB: capability_callbacks,
            SHOP_CB: shop_callbacks,
            VOUCHER_CB: voucher_callbacks,
            PRODUCT_CB: product_callbacks,
            GIFT_CB: gift_callbacks,
            ROVER_CB: rover_callbacks,
            USER_CB: user_callbacks,
            TIMER_CB: timer_callbacks
        }

    try:
        return CALLBACK_MODULES[module_name]
    except KeyError:
        raise Exception("Unknown callbacks module name [%s]" % module_name)

def _get_callback_base_class(module):
    try:
        return getattr(module, BASE_CALLBACKS_CLASS)
    except AttributeError:
        raise Exception("No %s class provided in callbacks module %s" % (BASE_CALLBACKS_CLASS, module))
