// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.target contains the Target model.
goog.provide("ce4.target.Target");
goog.provide("ce4.target.TargetCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');
goog.require('ce4.target_sound.TargetSoundCollection');
goog.require('ce4.image_rect.ImageRectCollection');

goog.require('ce4.gamestate');
goog.require('ce4.util');
goog.require('ce4.util.EpochDateField');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.target.Target = function Target(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.target.Target, lazy8.chips.Model);

/** @override */
ce4.target.Target.prototype.fields = {
    target_id: new lazy8.chips.Field({id_field:true, allow_cid:true}),
    start_time: new ce4.util.EpochDateField({required:true}),
    arrival_time: new ce4.util.EpochDateField({required:true}),
    picture: new lazy8.chips.Field({required:true}),
    processed: new lazy8.chips.Field({required:true}),
    classified: new lazy8.chips.Field({required:true}),
    highlighted: new lazy8.chips.Field({required:true}),
    viewed_at: new ce4.util.EpochDateField({required:true}), // Can be null
    can_abort_until: new ce4.util.EpochDateField({required:true}), // Can be null
    lat: new lazy8.chips.Field({required:true}),
    lng: new lazy8.chips.Field({required:true}),
    yaw: new lazy8.chips.Field({required:true}),
    pitch: new lazy8.chips.Field({required:true}), // Can be null
    images: new lazy8.chips.Field({required:true}),
    metadata: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

/** @override */
ce4.target.Target.prototype.collections = {
    sounds: ce4.target_sound.TargetSoundCollection,
    image_rects: ce4.image_rect.ImageRectCollection
};

ce4.target.Target.prototype.getCoords = function() {
    return [this.lat, this.lng];
};

ce4.target.Target.prototype.checkSpecies = function(rects, success, failure) {
    ce4.util.json_post({
        url: ce4.util.url_api(this.urls.check_species),
        data: {'rects':rects},
        success: function(data) {
            if (success !== undefined) {
                success();
            }
        },
        error: function() {
            console.error("Error in checkSpecies.");
            if (failure !== undefined) {
                failure();
            }
        }
    });
};

// Return true if this target can currently be aborted.
ce4.target.Target.prototype.can_abort = function() {
    if (this.can_abort_until === null) {
        return false;
    } else {
        return this.can_abort_until >= ce4.gamestate.user.epoch_now();
    }
}

ce4.target.Target.prototype.abort = function(success, failure) {
    ce4.util.json_post({
        url: ce4.util.url_api(this.urls.abort_target),
        data: {},
        success: function(data) {
            if (success !== undefined) {
                success();
            }
        },
        error: function() {
            console.error("Error in abort target.");
            if (failure !== undefined) {
                failure();
            }
        }
    });
};

ce4.target.Target.prototype.markViewed = function() {
    if (this.hasBeenViewed()) {
        return;
    }

    ce4.util.json_post({
        url: ce4.util.url_api(this.urls.mark_viewed),
        data: {},
        error: function() {
            console.error("Error in markViewed.");
        }
    });
};

// Return true if this target has any detected sound attached
ce4.target.Target.prototype.has_sound = function() {
    return !this.sounds.isEmpty();
};

// Return true if this target has an infrared
ce4.target.Target.prototype.has_infrared = function() {
    return (this.images.INFRARED != undefined);
};

// Get a list of species names found in all selection rectangles for this target.
// The list will be sorted by the seq attribute.
// Return an array in the following format:
// [{'seq':1, 'species_id':123, name':'Purple Yucca'}, {'seq':2, ... },...]
ce4.target.Target.prototype.get_detected_species_data = function() {
    var user = ce4.gamestate.user;

    // Convert the species IDs to names.
    var species_strings = [];
    this.image_rects.forEach(function(image_rect) {
        // Add the seq, species_id, and species name to our list for return.
        var species_id = image_rect.species_id;
        var species_name = "Insufficient data for species ID";
        if (species_id !== null) {
            var species = user.species.get(species_id);
            if (species !== undefined) {
                species_name = species.name;
            }
        }
        species_strings.push({'seq':image_rect.seq + 1, 'species_id':species_id, 'name':species_name});
    });
    return ce4.util.sortBy(species_strings, 'seq');
};

// Get a list of unique species {id:name} pairs found in all selection rectangles for this target.
// e.g., {123:'Purple Yucca', 456:'Swizzler',...}
ce4.target.Target.prototype.get_unique_species = function() {
    var user = ce4.gamestate.user;

    // Add unique id:name pairs to the set.
    var unique_species = {};
    this.image_rects.forEach(function(image_rect) {
        // Build an array with 0-3 species names found in this region.
        for (var i=0; i<3; i++) {
            var species_id = image_rect['species_id_'+i];
            if(species_id !== null) {
                var species = user.species.get(species_id);
                if (species === undefined)
                    unique_species[species_id] = "Insufficient data for species ID";
                else
                    unique_species[species_id] = species.name;
            }
        }
    });
    return unique_species;
};

ce4.target.Target.prototype.get_unique_species_count = function() {
    var obj = this.get_unique_species();
    var size = 0, key;
    for (key in obj) {
        if (obj.hasOwnProperty(key)) size++;
    }
    return size;
};

// Return the total number of times the given species was tagged in this target.
ce4.target.Target.prototype.get_count_of_species = function(species_id, subspecies_id) {
    var count = 0;
    this.image_rects.forEach(function(image_rect) {
        if (image_rect.has_species_id(species_id, subspecies_id))
            count += 1;
    });
    return count;
};

ce4.target.Target.prototype.picture_url = function() {
    return "#picture," + this.target_id;
};

ce4.target.Target.prototype.picture_url_shared = function(show_infrared) {
    if (show_infrared === true && this.has_infrared())
        return ce4.util.url_full(this.images.INFRARED);
    else
        return ce4.util.url_full(this.images.PHOTO);
};

ce4.target.Target.prototype.link_url_shared = function(show_infrared) {
    if (show_infrared === true && this.has_infrared())
        return ce4.util.url_full(this.urls.public_photo) + '?layer=ir';
    else
        return ce4.util.url_full(this.urls.public_photo);
};

ce4.target.Target.prototype.link_url_download_hires = function() {
    if (this.images.WALLPAPER != undefined)
        return this.urls.download_image + '/WALLPAPER';
};

ce4.target.Target.prototype.map_url = function() {
    return ce4.util.url_map({id: this.target_id}); // TODO: no longer seems used
};

ce4.target.Target.prototype.hasBeenViewed = function() {
    return this.viewed_at !== null;
};

// Returns true if the target's data is classified (should not be socially shared)
ce4.target.Target.prototype.is_classified = function() {
    return this.classified === 1;
};

// Returns true if this target has been highlighted by an admin.
ce4.target.Target.prototype.is_highlighted = function() {
    return this.highlighted === 1;
};

// Returns true if the target's photo is a panorama
ce4.target.Target.prototype.is_panorama = function() {
    return ("TGT_FEATURE_PANORAMA" in this.metadata);
};

// Returns true if the target's photo used flash
ce4.target.Target.prototype.is_flash = function() {
    return ("TGT_FEATURE_FLASH" in this.metadata);
};

// Returns true if the target's photo used infrared
ce4.target.Target.prototype.is_infrared = function() {
    return ("TGT_FEATURE_INFRARED" in this.metadata);
};

// Returns details for the target
ce4.target.Target.prototype.get_description = function() {
    return ce4.util.format_time_since(this.arrival_time_ms()); //+' facing '+ce4.util.yaw_to_compass(this.yaw);
}

// Returns true if the target's data is processed (picture exists for viewing)
ce4.target.Target.prototype.is_processed = function() {
    return this.processed === 1;
};

// Return true if the player should have arrived at this target by now, regardless of
// whether the target is actually processed.
ce4.target.Target.prototype.has_arrived = function() {
    return (this.arrival_time <= ce4.gamestate.user.epoch_now());
};

// Note that if the image has been tagged for reprocessing, this will still return true.
ce4.target.Target.prototype.has_available_photo = function() {
    return this.picture && this.images.PHOTO !== undefined;
};

// Returns true if the target's data is processed (picture exists for viewing)
ce4.target.Target.prototype.is_panorama = function() {
    return this.metadata.TGT_FEATURE_PANORAMA !== undefined;
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.target.TargetCollection = function TargetCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.target.TargetCollection, lazy8.chips.Collection);

/** @override */
ce4.target.TargetCollection.prototype.model_constructor = ce4.target.Target;
