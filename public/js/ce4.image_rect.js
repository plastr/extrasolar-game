// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.image_rect contains the ImageRect model.
goog.provide("ce4.image_rect.ImageRect");
goog.provide("ce4.image_rect.ImageRectCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.image_rect.ImageRect = function ImageRect(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.image_rect.ImageRect, lazy8.chips.Model);

/** @override */
ce4.image_rect.ImageRect.prototype.fields = {
    seq:          new lazy8.chips.Field({id_field:true}),
    xmin:         new lazy8.chips.Field({required:true}),
    ymin:         new lazy8.chips.Field({required:true}),
    xmax:         new lazy8.chips.Field({required:true}),
    ymax:         new lazy8.chips.Field({required:true}),
    species_id:   new lazy8.chips.Field({required:true}),
    subspecies_id:new lazy8.chips.Field({required:true}),
    density:      new lazy8.chips.Field({required:true})
};

/**
 * We are currently only using data from the first identified species_id.
 * Check for a non-null value to see if we've succesfully identified a species.
 */
ce4.image_rect.ImageRect.prototype.has_species = function() {
    if (this.species_id === null)
        return false;
    return true;
};

/**
 * Return true if this image rect has a matching species key and, if included,
 * a matching subspecies key.
 */
ce4.image_rect.ImageRect.prototype.has_species_id = function(species_id, subspecies_id) {
    if (subspecies_id === undefined)
        return (this.species_id === species_id);
    return (this.species_id === species_id && this.subspecies_id === subspecies_id);
}

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.image_rect.ImageRectCollection = function ImageRectCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.image_rect.ImageRectCollection, lazy8.chips.Collection);

/** @override */
ce4.image_rect.ImageRectCollection.prototype.model_constructor = ce4.image_rect.ImageRect;
