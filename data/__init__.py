# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
#
import re
from functools import wraps

import yaml
import validictory

from front.lib import xjson, utils

def validate_dict(d, required={}):
    """
    Validate in a very simplistic way a dictionary object. Returns the dictionary object, possibly with values cast.
    If this is None, then the second returned argument will be a user facing error message.
    :param required: Optionally pass a dict of required fields. If any are missing, an error response is
        created. The dict maps requied field names to their required data types (int, float, etc). The field
        value will be cast into the required type if they are not already and if that conversion fails,
        an error will be returned.

    >>> validate_dict({'f1':1})
    ({'f1': 1}, None)
    >>> validate_dict({'f1':1}, required={'f1':int})
    ({'f1': 1}, None)
    >>> validate_dict({'f1':1, 'f2':2}, required={'f1':int})
    ({'f1': 1, 'f2': 2}, None)
    >>> validate_dict({'f1':1}, required={'f1':str})
    ({'f1': '1'}, None)
    >>> validate_dict({'f2':2}, required={'f1':int})
    (None, 'Missing required field: f1')
    >>> validate_dict({'f1':None}, required={'f1':int})
    (None, 'Bad data type for field: f1')
    """
    for field, d_type in required.iteritems():
        if field not in d:
            return None, utils.tr("Missing required field: %s" % field)
        # If the value is already the correct data type, do not attempt to cast/convert again.
        if isinstance(d[field], d_type): continue
        try:
            d[field] = d_type(d[field])
        except (ValueError, TypeError):
            return None, utils.tr("Bad data type for field: %s" % field)
    return d, None

def validate_struct(struct, schema):
    validictory.validate(struct, schema, format_validators=CUSTOM_VALIDATORS, blank_by_default=False)

def load_json(file_path, schema=None):
    with open(file_path) as f:
        data = xjson.load(f)
        if schema is not None:
            validate_struct(data, schema)
        return data

def load_yaml_and_header(file_path, schema=None):
    with open(file_path) as f:
        yaml_documents = yaml.load_all(f)
        # The first document is the header.
        header = yaml_documents.next()
        # The remaining yaml documents will be treated as the data.
        data = list(yaml_documents)
        if schema is not None:
            validate_struct(data, schema)
        return (header, data)

## Custom format validators.
# A decorator which makes a format validation function allow for optional values (where value=None).
def optional(validate_function):
    @wraps(validate_function)
    def _optional_decorator(validator, fieldname, value, format_option, *args, **kwargs):
        if value is None:
            return

        return validate_function(validator, fieldname, value, format_option, *args, **kwargs)
    return _optional_decorator

# Example format: MSG_WELCOME
MESSAGE_NAME_PATTERN = re.compile(r'MSG_[A-Z]+')
def validate_format_message_name(validator, fieldname, value, format_option):
    if not MESSAGE_NAME_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid message name format %(pattern)s", value, fieldname, pattern=MESSAGE_NAME_PATTERN.pattern)

# Example format: EMAIL_VERIFY
EMAIL_NAME_PATTERN = re.compile(r'EMAIL_[A-Z]+')
def validate_format_email_name(validator, fieldname, value, format_option):
    if not EMAIL_NAME_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid email name format %(pattern)s", value, fieldname, pattern=EMAIL_NAME_PATTERN.pattern)

# This is used where a collection key is the string representation of a positive int but the value in the model
# is stored as a number.
def validate_format_int_positive_key(validator, fieldname, value, format_option):
    # key is stored as a string when it is an object key, integer when it is a value.
    if not isinstance(value, int):
        try:
            value = int(value)
        except ValueError:
            _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid positive integer key", value, fieldname)

    if not value >= 0:
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a positive integer", value, fieldname)

# Example format: MIS_TUT01a or MIS_SPECIES_FIND_5
DEFINITION_KEY_PATTERN = re.compile(r'[A-Z0-9_]+[a-z]*')
@optional # Use type:"any" if optional, type:"string" if required.
def validate_format_definition_key(validator, fieldname, value, format_option):
    if not DEFINITION_KEY_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid definition key format %(pattern)s", value, fieldname, pattern=DEFINITION_KEY_PATTERN.pattern)

# Example format: 17,123,456
MAP_TILE_KEY_PATTERN = re.compile(r'[0-9]+,[0-9]+,[0-9]+')
@optional # Use type:"any" if optional, type:"string" if required.
def validate_format_map_tile_key(validator, fieldname, value, format_option):
    if not MAP_TILE_KEY_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid map tile key format %(pattern)s", value, fieldname, pattern=MAP_TILE_KEY_PATTERN.pattern)

# Example format: MIS_TUT01a-c29da660344e65e388a4eff4dc7d65fb
MISSION_ID_PATTERN = re.compile(r'%s-[a-z0-9]{32}' % DEFINITION_KEY_PATTERN.pattern)
@optional # Use type:"any" if optional, type:"string" if required.
def validate_format_mission_id(validator, fieldname, value, format_option):
    if not MISSION_ID_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid mission_id format %(pattern)s", value, fieldname, pattern=MISSION_ID_PATTERN.pattern)

# Example format: /path or http://example.com
SIMPLE_URL_PATTERN = re.compile(r'^/|^http[s]?://')
@optional # Use type:"any" if optional, type:"string" if required.
def validate_format_simple_url(validator, fieldname, value, format_option):
    if not SIMPLE_URL_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid simple URL (starts with / or http)", value, fieldname)

# Example format: TUT or STYLE_HAZARD_LINE
STRING_CONSTANT_PATTERN = re.compile(r'[A-Z_]+')
@optional # Use type:"any" if optional, type:"string" if required.
def validate_format_string_constant(validator, fieldname, value, format_option):
    if not STRING_CONSTANT_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid string constant format %(pattern)s", value, fieldname, pattern=STRING_CONSTANT_PATTERN)

HEX_STRING_PATTERN = re.compile(r'0x[A-Fa-f0-9]+')
@optional # Use type:"any" if optional, type:"string" if required.
def validate_hex_string(validator, fieldname, value, format_option):
    if not HEX_STRING_PATTERN.match(value):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid hex string format %(pattern)s", value, fieldname, pattern=HEX_STRING_PATTERN)

@optional # Use type:"any" if optional, type:"number" if required.
def validate_format_coordinate(validator, fieldname, value, format_option):
    validate_format_float(validator, fieldname, value, format_option)

    # This could be broken out into coordinate_lat and coordinate_lng but just check the extreme range.
    if value > 180.0 or value < -180:
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid coordinate (> -180.0 and < 180.0)", value, fieldname)

@optional # Use type:"any" if optional, type:"number" if required.
def validate_format_float(validator, fieldname, value, format_option):
    if not isinstance(value, float):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a float", value, fieldname)

@optional # Use type:"any" if optional, type:"number" if required.
def validate_format_int_positive(validator, fieldname, value, format_option):
    if not isinstance(value, int):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not an integer", value, fieldname)

    if value < 0:
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a positive (> 0)", value, fieldname)

def validate_format_int_boolean(validator, fieldname, value, format_option):
    if not isinstance(value, int):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid integer", value, fieldname)

    if value not in [0, 1]:
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid integer boolean value (0, 1)", value, fieldname)

@optional # Use type:"any" if optional, type:"string if required.
def validate_format_uuid(validator, fieldname, value, format_option):
    from front.lib import get_uuid

    try:
        if not get_uuid(value):
            _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid UUID", value, fieldname)
    except ValueError:
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid UUID", value, fieldname)

# Example format: 1299176791
TIMESTAMP_PATTERN = re.compile(r'[0-9]{10}')
@optional # Use type:"any" if optional, type:"string if required.
def validate_format_timestamp(validator, fieldname, value, format_option):
    if not isinstance(value, int):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid timestamp (expected int)", value, fieldname)

    if not TIMESTAMP_PATTERN.match(str(value)):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid timestamp format %(pattern)s", value, fieldname, pattern=TIMESTAMP_PATTERN.pattern)

# Example format: 0 or 26600 etc.
@optional # Use type:"any" if optional, type:"number" if required.
def validate_format_epoch_delta(validator, fieldname, value, format_option):
    if not isinstance(value, int):
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid epoch delta (expected int)", value, fieldname)

    if value < 0:
        _validation_error("Value %(value)r of field '%(fieldname)s' is not a valid epoch delta format (> 0)", value, fieldname)

def _make_struct_key_validator(key_validator, minItems=0):
    def _validate_struct_keys(validator, fieldname, value, format_option):
        if not len(value) >= minItems:
            _validation_error("Value %(value)r of field '%(fieldname)s' must have more than %(minItems)d items", value, fieldname, minItems=minItems)

        for struct_key in value:
            key_validator(validator, fieldname + "(key)", struct_key, format_option)
    return _validate_struct_keys

# Lifted from validator.py because the _error helper is private API.
def _validation_error(desc, value, fieldname, **params):
    params['value'] = value
    params['fieldname'] = fieldname
    message = desc % params
    raise validictory.ValidationError(message)

CUSTOM_VALIDATORS = {
    'timestamp': validate_format_timestamp,
    'epoch_delta': validate_format_epoch_delta,
    'uuid': validate_format_uuid,
    'int_boolean': validate_format_int_boolean,
    'int_positive': validate_format_int_positive,
    'coordinate': validate_format_coordinate,
    'float': validate_format_float,
    'simple_url': validate_format_simple_url,
    'string_constant': validate_format_string_constant,
    'hex_string': validate_hex_string,
    'uuid_struct': _make_struct_key_validator(validate_format_uuid, minItems=1),
    'int_positive_key': validate_format_int_positive_key,
    'int_positive_key_struct': _make_struct_key_validator(validate_format_int_positive_key, minItems=0),
    'mission_id': validate_format_mission_id,
    'mission_id_struct': _make_struct_key_validator(validate_format_mission_id, minItems=1),
    'definition_key': validate_format_definition_key,
    'definition_key_struct': _make_struct_key_validator(validate_format_definition_key, minItems=1),
    'map_tile_key': validate_format_map_tile_key,
    'map_tile_key_struct': _make_struct_key_validator(validate_format_map_tile_key, minItems=0)
}
