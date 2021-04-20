// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.species contains the Species model.
goog.provide("ce4.species.Species");
goog.provide("ce4.species.SpeciesCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');
goog.require('ce4.subspecies.SubSpeciesCollection');

goog.require('ce4.gamestate');
goog.require('ce4.util.EpochDateField');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.species.Species = function Species(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.species.Species, lazy8.chips.Model);

/** @override */
ce4.species.Species.prototype.fields = {
    species_id: new lazy8.chips.Field({id_field:true}),
    name: new lazy8.chips.Field({required:true}),
    key: new lazy8.chips.Field({required:true}),
    type: new lazy8.chips.Field({required:true}),
    icon: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    science_name: new lazy8.chips.Field({required:true}),
    detected_at: new ce4.util.EpochDateField({required:true}),
    available_at: new ce4.util.EpochDateField({required:true}),
    viewed_at: new ce4.util.EpochDateField({required:true}),
    target_ids: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

/** @override */
ce4.species.Species.prototype.collections = {
    subspecies: ce4.subspecies.SubSpeciesCollection
};

ce4.species.Species.prototype.get_targets = function() {
    var user = ce4.gamestate.user;
    var targets = [];
    if (this.target_ids && this.target_ids.length > 0) {
        for (var i = 0; i < this.target_ids.length; i++) {
            var rover_id = this.target_ids[i][0];
            var target_id = this.target_ids[i][1];
            var target = user.rovers.get(rover_id).targets.get(target_id);
            targets[i] = target;
        }
    }
    return targets;
};

ce4.species.Species.prototype.format_detected_at = function() {
    return ce4.util.format_time_since(this.detected_at_ms());
};

ce4.species.Species.prototype.get_icon_url = function(width, height) {
    return ce4.util.url_static("/static/img/species_icons/" + this.icon + "_" + width + "x" + height + ".png");
};

ce4.species.Species.prototype.hasBeenViewed = function() {
    return this.viewed_at !== null;
};

// Return true if all species description data (which might have been delayed when initially
// identified during identification) is in the gamestate.
ce4.species.Species.prototype.isFullyAvailable = function() {
    return ce4.gamestate.user.epoch_now() >= this.available_at;
};

ce4.species.Species.prototype.markViewed = function() {
    if (this.hasBeenViewed()) {
        return;
    }

    // Wait until all description data is fully available before marking the species viewed.
    if (!this.isFullyAvailable()) {
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

// Species IDs with their lowests 20 bits set to 0 are reserved for species that
// are too far to accurately identify.
ce4.species.is_too_far_for_id = function(species_id) {
    return ((species_id & 0xFFFFF) === 0);
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.species.SpeciesCollection = function SpeciesCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.species.SpeciesCollection, lazy8.chips.Collection);

/** @override */
ce4.species.SpeciesCollection.prototype.model_constructor = ce4.species.Species;

// Return a Species object for the given species key if it exists in the collection.
ce4.species.SpeciesCollection.prototype.for_key = function(species_key) {
    return this.find(function(species) {
        return species.key === species_key;
    });
};

// Returns true a given species_key is in the collection, false otherwise.
ce4.species.SpeciesCollection.prototype.has_key = function(species_key) {
    return this.for_key(species_key) !== undefined;
};

// Returns the number of targets for the given species_key.
ce4.species.SpeciesCollection.prototype.count_of_targets_for_key = function(species_key, subspecies_id) {
    var species = this.for_key(species_key);
    if (species === undefined)
        return 0;
    if (subspecies_id == undefined)
        return species.target_ids.length;
    // If we also want to filter by subspecies type, we'll need to check each target.
    var count = 0;
    var species_targets = species.get_targets();
    for (var i = 0; i < species_targets.length; i++) {
        count += species_targets[i].get_count_of_species(species.species_id, subspecies_id);
    }
    return count;
};

// Returns the number of all plant and animal species.
ce4.species.SpeciesCollection.prototype.count_organic = function() {
    var organic_count = 0;
    this.forEach(function(model) {
        if (model.type === 'PLANT' || model.type === 'ANIMAL')
            organic_count += 1;
    });
    return organic_count;
}
