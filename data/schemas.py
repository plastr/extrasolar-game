# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front import target_image_types, species_types

## Gamestate schema
SUBSPECIES = {
    "subspecies_id":{"type":"number", "format":"int_positive_key"},
    "name":{"type":"string"}
}

SPECIES = {
    "species_id":{"type":"number", "format":"int_positive_key"},
    "name":{"type":"string"},
    "key":{"type":"string"},
    "type":{"type":"string"},
    "icon":{"type":"string"},
    "description":{"type":"string"},
    "science_name":{"type":"any"}, # Can be None.
    "detected_at": {"type":"number", "format":"epoch_delta"},
    "available_at": {"type":"number", "format":"epoch_delta"},
    "viewed_at": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "subspecies": {"type":"object", "format":"int_positive_key_struct", # "minItems":0},
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":SUBSPECIES}},
    "target_ids": {"type":"array", "minItems":0, "items":{
        "type":"array", "minItems":1, "items":{
            "type":"string", "format":"uuid"}}},
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "mark_viewed": {"type":"string", "format":"simple_url"}
    }}
}

MESSAGE = {
    "message_id": {"type": "string", "format":"uuid"},
    "msg_type": {"type": "string", "format":"definition_key"},
    "style": {"type": "string", "format":"definition_key"},
    "sender": {"type":"string"},
    "sender_key": {"type":"string", "format":"definition_key"},
    "subject": {"type":"string"},
    "read_at": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "sent_at": {"type":"number", "format":"epoch_delta"},
    "locked": {"type":"number", "format":"int_boolean"},
    "needs_password": {"type":"number", "format":"int_boolean"},
    "urls": {"type": "object", "additionalProperties":False, "properties":{
        "message_content": {"type":"string", "format":"simple_url"},
        "message_forward": {"type":"string", "format":"simple_url"},
        "message_unlock": {"type":"string", "format":"simple_url", "required":False}
    }}
}

MISSION = {
    "mission_id": {"type": "string", "format":"mission_id"},
    "mission_definition": {"type": "string", "format":"definition_key"},
    "parent_id": {"type":"any", "format":"mission_id"}, # Can be None.
    "parent_definition": {"type":"any", "format":"definition_key"}, # Can be None.
    "type": {"type": "string"},
    "title": {"type":"string"},
    "summary": {"type":"any"}, # Can be None.
    "description": {"type":"any"}, # Can be None.
    "done_notice": {"type":"any"}, # Can be None.
    "title_icon":{"type":"any", "format":"string_constant"}, # Can be None.
    "description_icon":{"type":"any", "format":"string_constant"}, # Can be None.
    "done": {"type":"number", "format":"int_boolean"},
    "done_at": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "sort": {"type":"number", "format":"int_positive"},
    "started_at": {"type":"number", "format":"epoch_delta"},
    "viewed_at": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "region_ids": {"type":"array", "minItems":0, "items":{
        "type":"string", "format":"definition_key"}
    },
    # specifics is a mission specific payload serialized as JSON into the DB.
    "specifics": {"type":"object", "additionalProperties":True, "properties":{
        # Any property is valid as each mission is different.
    }},
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "mark_viewed": {"type":"string", "format":"simple_url"}
    }}
}

IMAGE_RECT = {
    "seq":{"type":"number", "format":"int_positive_key"},
    "species_id": {"type":"any", "format":"int_positive"}, # Can be None.
    "subspecies_id": {"type":"any", "format":"int_positive"}, # Can be None.
    "density": {"type":"any", "format":"float"}, # Can be None.
    "xmin": {"type":"number", "format":"float"},
    "xmax": {"type":"number", "format":"float"},
    "ymin": {"type":"number", "format":"float"},
    "ymax": {"type":"number", "format":"float"}
}

TARGET_SOUND = {
    "sound_key":{"type":"string", "format":"definition_key"},
    "comment":{"type":"string", "required":False}, # Optional comment field.
    "title": {"type":"string"},
    "video_id": {"type":"number", "format":"int_positive"}
}

TARGET = {
    "target_id": {"type": "string", "format":"uuid"},
    "start_time": {"type": "number", "format":"epoch_delta"},
    "arrival_time": {"type": "number", "format":"epoch_delta"},
    "picture": {"type":"number", "format":"int_boolean"},
    "processed": {"type":"number", "format":"int_boolean"},
    "classified": {"type":"number", "format":"int_boolean"},
    "highlighted": {"type":"number", "format":"int_boolean"},
    "viewed_at": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "can_abort_until": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "lat": {"type":"number", "format":"coordinate"},
    "lng": {"type":"number", "format":"coordinate"},
    "yaw": {"type":"number", "format":"float"},
    "pitch": {"type":"number", "format":"float"},
    "images": {"type":"object", "additionalProperties":False, "properties":{
        # The SPECIES image should not be in the gamestate.
        target_image_types.PHOTO: {"type":"string", "format":"simple_url", "required":False},
        target_image_types.THUMB: {"type":"string", "format":"simple_url", "required":False},
        target_image_types.WALLPAPER: {"type":"string", "format":"simple_url", "required":False},
        target_image_types.INFRARED: {"type":"string", "format":"simple_url", "required":False},
        target_image_types.THUMB_LARGE: {"type":"string", "format":"simple_url", "required":False}
    }},
    "metadata": {"type":"object", "additionalProperties":True, "properties":{
        # The metadata dictionary can contain arbitrary keys in the TGT_ namespace.
    }},
    "sounds": {"type":"object", "format":"definition_key_struct", # "minItems":0},
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":TARGET_SOUND}},
    "image_rects": {"type":"object", "format":"int_positive_key_struct", # "minItems":0},
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":IMAGE_RECT}},
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "check_species": {"type":"string", "format":"simple_url"},
        "abort_target": {"type":"string", "format":"simple_url"},
        "mark_viewed": {"type":"string", "format":"simple_url"},
        "download_image": {"type":"string", "format":"simple_url"},
        "public_photo": {"type":"string", "format":"simple_url"}
    }}
}

ROVER = {
    "rover_id": {"type": "string", "format":"uuid"},
    "rover_key": {"type": "string", "format":"definition_key"},
    "rover_chassis": {"type": "string", "format":"definition_key"},
    "activated_at": {"type": "number", "format":"epoch_delta"},
    "active": {"type": "number", "format":"int_boolean"},
    "max_unarrived_targets": {"type": "number", "format":"int_positive"},
    "min_target_seconds": {"type": "number", "format":"int_positive"},
    "max_target_seconds": {"type": "number", "format":"int_positive"},
    "max_travel_distance": {"type": "number", "format":"float"},
    "lander": {"type":"object", "additionalProperties":False, "properties":{
        "lander_id": {"type": "string", "format":"uuid"},
        "lat": {"type":"number", "format":"coordinate"},
        "lng": {"type":"number", "format":"coordinate"},
    }},
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "target": {"type":"string", "format":"simple_url"}
    }},
    "targets": {"type":"object", "format":"uuid_struct", # "minItems":1},
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":TARGET}}
}

REGION = {
    "region_id":{"type":"string", "format":"definition_key"},
    "title":{"type":"string"},
    "description":{"type":"string"},
    "restrict":{"type":"string", "format":"string_constant"},
    "style":{"type":"string", "format":"string_constant"},
    "visible": {"type":"number", "format":"int_boolean"},
    "shape":{"type":"string", "format":"string_constant"},
    "marker_icon":{"type":"any", "format":"string_constant"}, # Can be None.
    "region_icon":{"type":"any", "format":"string_constant"}, # Can be None.
    "verts": {"type": "array", "minItems":0, "items":{
            "type":"array", "minItems":2, "maxItems":2, "items":{
                "type":"number", "format":"coordinate"
        }}},
    "center": {"type": "array", "maxItems":2, "items":{  # Can be empty list.
            "type":"number", "format":"coordinate"
        }},
    "radius":{"type":"any", "format":"float"}
}

PROGRESS = {
    "key":{"type":"string", "format":"definition_key"},
    "value":{"type":"string", "blank":True},
    "achieved_at": {"type": "number", "format":"epoch_delta"},
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "reset": {"type":"string", "format":"simple_url"}
    }}
}

ACHIEVEMENT = {
    "achievement_key":{"type":"string", "format":"definition_key"},
    "title":{"type":"string"},
    "description":{"type":"string"},
    "type":{"type":"string"},
    "secret": {"type":"number", "format":"int_boolean"},
    "classified": {"type":"number", "format":"int_boolean"},
    "icon": {"type":"string", "format":"definition_key"},
    "achieved_at": {"type": "any", "format":"epoch_delta"}, # Can be None.
    "viewed_at": {"type":"any", "format":"epoch_delta"}, # Can be None.
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "mark_viewed": {"type":"string", "format":"simple_url"}
    }}
}

CAPABILITY = {
    "capability_key":{"type":"string", "format":"definition_key"},
    "uses":{"type":"number", "format":"int_positive"},
    "free_uses":{"type":"number", "format":"int_positive"},
    "unlimited": {"type":"number", "format":"int_boolean"},
    "available": {"type":"number", "format":"int_boolean"},
    "rover_features": {"type":"array", "minItems":0, "items":{
        "type":"string", "format":"definition_key"}
    }
}

VOUCHER = {
    "voucher_key":{"type":"string", "format":"definition_key"},
    "name":{"type":"string"},
    "description":{"type":"string"},
    "delivered_at": {"type": "number", "format":"epoch_delta"}
}

MAP_TILE = {
    "tile_key":{"type":"string", "format":"map_tile_key"},
    "zoom":{"type":"number", "format":"int_positive"},
    "x":{"type":"number", "format":"int_positive"},
    "y":{"type":"number", "format":"int_positive"},
    "arrival_time": {"type": "number", "format":"epoch_delta"}
}

INVITE = {
    "invite_id": {"type": "string", "format":"uuid"},
    "sender_id": {"type": "string", "format":"uuid"},
    "recipient_id": {"type": "any", "format":"uuid"}, # Can be None.
    "recipient_email": {"type":"string"},
    "recipient_first_name": {"type":"string"},
    "recipient_last_name": {"type":"string"},
    "sent_at": {"type": "number", "format":"timestamp"},
    "accepted_at": {"type": "any", "format":"timestamp"}, # Can be None.
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "invite_accept": {"type":"string", "format":"simple_url"},
        "recipient_public_profile": {"type":"any", "format":"simple_url"} # Can be None.
    }}
}

AVAILABLE_PRODUCT = {
    "product_key":{"type":"string", "format":"definition_key"},
    "name":{"type":"string"},
    "description":{"type":"string"},
    "price": {"type": "number", "format":"int_positive"},
    "currency":{"type":"string"},
    "price_display": {"type": "string"},
    "initial_price": {"type": "number", "format":"int_positive"},
    "initial_price_display": {"type": "string"},
    "icon": {"type":"string", "format":"simple_url"},
    "sort": {"type":"number", "format":"int_positive"},
    "repurchaseable": {"type":"number", "format":"int_boolean"},
    "cannot_purchase_after": {"type":"array", "minItems":0, "items":{
        "type":"string", "format":"definition_key"}
    }
}

PURCHASED_PRODUCT = {
    "product_id": {"type": "string", "format":"uuid"},
    "product_key": {"type":"string", "format":"definition_key"},
    "name": {"type":"string"},
    "description": {"type":"string"},
    "price": {"type": "number", "format":"int_positive"},
    "currency":{"type":"string"},
    "price_display": {"type": "string"},
    "icon": {"type":"string", "format":"simple_url"},
    "sort": {"type":"number", "format":"int_positive"},
    "repurchaseable": {"type":"number", "format":"int_boolean"},
    "purchased_at": {"type": "number", "format":"epoch_delta"},
    "cannot_purchase_after": {"type":"array", "minItems":0, "items":{
        "type":"string", "format":"definition_key"}
    }
}

SHOP = {
    "shop_id": {"type":"string"},
    "stripe_customer_data": {"type": "any", "additionalProperties":False, "properties": { # Can be None.
        "card_type": {"type":"string"},
        "card_last4": {"type":"string"},
        "card_exp_month": {"type":"string"},
        "card_exp_year": {"type":"string"},
        "card_name": {"type":"string"}
    }},
    "stripe_has_saved_card": {"type":"number", "format":"int_boolean"},
    "stripe_publishable_key": {"type":"string"},
    "available_products":{"type":"object", "format":"definition_key_struct", # "minItems":0
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":AVAILABLE_PRODUCT}
    },
    "purchased_products":{"type":"object", "format":"uuid_struct", # "minItems":0
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":PURCHASED_PRODUCT}
    },
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "stripe_purchase_products": {"type":"string", "format":"simple_url"},
        "stripe_remove_saved_card": {"type":"string", "format":"simple_url"}
    }}
}

USER = {
    # Add format validator for email.
    "email": {"type":"string"},
    "first_name": {"type":"string"},
    "last_name": {"type":"string"},
    "epoch": {"type": "number", "format":"timestamp"},
    "dev": {"type":"number", "format":"int_boolean"},
    "auth": {"type":"string", "enum":["PASS", "FB", "EDMO"]},
    "valid": {"type":"number", "format":"int_boolean"},
    "activity_alert_frequency": {"type":"string"},
    "viewed_alerts_at": {"type": "any", "format":"epoch_delta"}, # Can be None.
    "invites_left": {"type": "number", "format":"int_positive"},
    "inviter_id": {"type": "any", "format":"uuid"}, # Can be None.
    "inviter": {"type": "object", "additionalProperties":False, "properties": {
        "url_public_profile": {"type":"string", "format":"simple_url", "required":False}
    }},
    "current_voucher_level": {"type": "any", "format":"definition_key"}, # Can be None.
    "shop": {"type": "object", "additionalProperties":False, "properties":SHOP},
    "species": {"type":"object", "format":"int_positive_key_struct", # "minItems":0
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":SPECIES}
    },
    "messages": {"type":"object", "format":"uuid_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":MESSAGE}
    },
    "missions": {"type":"object", "format":"mission_id_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":MISSION}
    },
    "rovers":{"type":"object", "format":"uuid_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":ROVER}
    },
    "regions":{"type":"object", "format":"definition_key_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":REGION}
    },
    "progress":{"type":"object", "format":"definition_key_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":PROGRESS}
    },
    "achievements":{"type":"object", "format":"definition_key_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":ACHIEVEMENT}
    },
    "capabilities":{"type":"object", "format":"definition_key_struct", # "minItems":1
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":CAPABILITY}
    },
    "vouchers":{"type":"object", "format":"definition_key_struct", # "minItems":0
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":VOUCHER}
    },
    "map_tiles":{"type":"object", "format":"map_tile_key_struct", # "minItems":0
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":MAP_TILE}
    },
    "invitations":{"type":"object", "format":"uuid_struct", # "minItems":0
        "additionalProperties": {"type":"object", "additionalProperties":False, "properties":INVITE}
    },
    "urls": {"type": "object", "additionalProperties":False, "properties": {
        "settings_notifications": {"type":"string", "format":"simple_url"},
        'update_viewed_alerts_at': {"type":"string", "format":"simple_url"}
    }}
}

GAMESTATE = {
    "additionalProperties":False,
    "properties":{
        "user": {"type":"object", "additionalProperties":False, "properties":USER},
        "config": {"type": "object", "additionalProperties":False, "properties": {
            "server_time": {"type":"number", "format":"timestamp"},
            "last_seen_chip_time": {"type":"string"}, # e.g. "1352765719142900"
            "chip_fetch_interval": {"type":"number", "format":"int_positive"},
            "use_social_networks": {"type":"boolean"}
        }},
        "urls": {"type": "object", "additionalProperties":False, "properties": {
            "gamestate": {"type":"string", "format":"simple_url"},
            "map_tile": {"type":"string", "format":"simple_url"},
            "user_map_tile": {"type":"string", "format":"simple_url"},
            "user_public_profile": {"type":"string", "format":"simple_url"},
            "fetch_chips": {"type":"string", "format":"simple_url"},
            "create_progress": {"type":"string", "format":"simple_url"},
            "create_invite": {"type":"string", "format":"simple_url"}
    }}}
}

## Mission definitions schema
MISSION_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":{
            "type": {"type":"string", "format":"string_constant"}, # e.g. "TUT"
            "title": {"type":"string"},
            "summary": {"type":"string", "required":False},
            "description": {"type":"string", "required":False},
            "done_notice": {"type":"string", "required":False},
            "parent_definition": {"type":"string", "format":"definition_key", "required":False},
            "sort": {"type":"number", "format":"int_positive"},
            "title_icon":{"type":"string", "format":"string_constant", "required":False},
            "description_icon":{"type":"string", "format":"string_constant", "required":False}
        }
    }
}

## Message types schema
MESSAGE_TYPES = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":{
            "id": {"type":"string", "format":"definition_key"},
            "sender": {"type":"string"},
            # Not in YAML file but inserted into data before validation.
            "sender_key": {"type":"string", "format":"definition_key"},
            "subject": {"type":"string"},
            "style": {"type":"string", "required":False},
            "body": {"type":"string"},
            "body_locked": {"type":"string", "required":False},
            "needs_password": {"type":"number", "format":"int_boolean", "required":False}
        }
    }
}

## Email types schema
EMAIL_TYPES = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":{
            "id": {"type":"string", "format":"definition_key"},
            "sender": {"type":"string"},
            "subject": {"type":"string"},
            "body": {"type":"string"}
        }
    }
}

## Region definitions schema
# The regions.json file has identical fields to the regions structure in the gamestate, without
# a region_id field.
REGION_DEFINITIONS_PROPS = REGION.copy()
del REGION_DEFINITIONS_PROPS['region_id']
REGION_DEFINITIONS_PROPS['marker_icon']['required'] = False
REGION_DEFINITIONS_PROPS['region_icon']['required'] = False
REGION_DEFINITIONS_PROPS['comment'] = {"type":"string", "required":False} # Optional comment field.
REGION_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":REGION_DEFINITIONS_PROPS
    }
}

## Achievement definitions schema
# The achievement_descriptions.json file has identical fields to the achievement structure in the gamestate, without
# achievement_key or achieved_at fields.
ACHIEVEMENT_DEFINITIONS_PROPS = ACHIEVEMENT.copy()
del ACHIEVEMENT_DEFINITIONS_PROPS['achievement_key']
del ACHIEVEMENT_DEFINITIONS_PROPS['achieved_at']
del ACHIEVEMENT_DEFINITIONS_PROPS['viewed_at']
del ACHIEVEMENT_DEFINITIONS_PROPS['urls']
ACHIEVEMENT_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":ACHIEVEMENT_DEFINITIONS_PROPS
    }
}

## Capability definitions schema
CAPABILITY_DEFINITIONS_PROPS = CAPABILITY.copy()
del CAPABILITY_DEFINITIONS_PROPS['capability_key']
del CAPABILITY_DEFINITIONS_PROPS['uses']
del CAPABILITY_DEFINITIONS_PROPS['unlimited']
del CAPABILITY_DEFINITIONS_PROPS['available']
CAPABILITY_DEFINITIONS_PROPS['available_on_rovers'] = {"type":"array", "minItems":0, "items":{
    "type":"string", "format":"definition_key"}
}
CAPABILITY_DEFINITIONS_PROPS['always_unlimited'] = {"type":"number", "format":"int_boolean"}
CAPABILITY_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":CAPABILITY_DEFINITIONS_PROPS
    }
}

## Voucher definitions schema
VOUCHER_DEFINITIONS_PROPS = VOUCHER.copy()
del VOUCHER_DEFINITIONS_PROPS['voucher_key']
del VOUCHER_DEFINITIONS_PROPS['delivered_at']
VOUCHER_DEFINITIONS_PROPS['unlimited_capabilities'] = {"type":"array", "minItems":0, "items":{
    "type":"string", "format":"definition_key"}
}
VOUCHER_DEFINITIONS_PROPS['not_available_after'] = {"type":"array", "minItems":0, "items":{
    "type":"string", "format":"definition_key"}
}
VOUCHER_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":VOUCHER_DEFINITIONS_PROPS
    }
}

## Product definitions schema
PRODUCT_DEFINITIONS_PROPS = AVAILABLE_PRODUCT.copy()
del PRODUCT_DEFINITIONS_PROPS['product_key']
del PRODUCT_DEFINITIONS_PROPS['price']
del PRODUCT_DEFINITIONS_PROPS['price_display']
del PRODUCT_DEFINITIONS_PROPS['initial_price_display']
PRODUCT_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":PRODUCT_DEFINITIONS_PROPS
    }
}

## Target sounds definitions schema
# The target_sounds.json file has identical fields to the target_sound structure in the gamestate, without
# sound_key.
TARGET_SOUND_DEFINITIONS_PROPS = TARGET_SOUND.copy()
del TARGET_SOUND_DEFINITIONS_PROPS['sound_key']
TARGET_SOUNDS_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":TARGET_SOUND_DEFINITIONS_PROPS
    }
}

## AudioRegion definitions schema
AUDIO_REGION_DEFINITIONS = {
    "type":"object", "format":"definition_key_struct", "additionalProperties":{
        "type":"object", "additionalProperties":False, "properties":{
            "mission_definition": {"type": "string", "format":"definition_key"},
            "comment":{"type":"string", "required":False}, # Optional comment field.
            "shape":{"type":"string", "format":"string_constant"},
            "verts": {"type": "array", "minItems":0, "items":{
                    "type":"array", "minItems":2, "maxItems":2, "items":{
                        "type":"number", "format":"coordinate"
                }}},
            "center": {"type": "array", "maxItems":2, "items":{  # Can be empty list.
                    "type":"number", "format":"coordinate"
                }},
            "radius":{"type":"any", "format":"float"}
        }
    }
}

## Species list schema
SPECIES_LIST_PROPS = SPECIES.copy()
# species_id is a hex string in the json.
del SPECIES_LIST_PROPS['species_id']
SPECIES_LIST_PROPS["species_id"] = {"type":"string", "format":"hex_string"}
del SPECIES_LIST_PROPS['detected_at']
del SPECIES_LIST_PROPS['available_at']
del SPECIES_LIST_PROPS['viewed_at']
del SPECIES_LIST_PROPS['subspecies']
del SPECIES_LIST_PROPS['target_ids']
del SPECIES_LIST_PROPS['urls']
SPECIES_LIST_PROPS['science_name']['required'] = False
SPECIES_LIST = {
    "type":"object", "additionalProperties":False, "properties":{
        "speciesList": {"type":"array", "minItems":1, "items":{
            "type":"object", "additionalProperties":False, "properties":SPECIES_LIST_PROPS
            }
        }
    }
}

## SubSpecies list schema
SUBSPECIES_TYPES = {}
for t in species_types.ALL:
    SUBSPECIES_TYPES[t] = {"type":"array", "minItems":0, "items":{
            "type":"object", "additionalProperties":False, "properties":SUBSPECIES
        }
    }
SUBSPECIES_LIST = {
    "type":"object", "additionalProperties":False, "properties":{
        "subSpeciesList": {"type":"object", "additionalProperties":False, "properties":SUBSPECIES_TYPES
        }
    }
}
