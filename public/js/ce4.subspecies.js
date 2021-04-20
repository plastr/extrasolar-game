// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.subspecies contains the SubSpecies model.
goog.provide("ce4.subspecies.SubSpecies");
goog.provide("ce4.subspecies.SubSpeciesCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.subspecies.SubSpecies = function SubSpecies(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.subspecies.SubSpecies, lazy8.chips.Model);

/** @override */
ce4.subspecies.SubSpecies.prototype.fields = {
    subspecies_id: new lazy8.chips.Field({id_field:true}),
    name: new lazy8.chips.Field({required:true})
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.subspecies.SubSpeciesCollection = function SubSpeciesCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.subspecies.SubSpeciesCollection, lazy8.chips.Collection);

/** @override */
ce4.subspecies.SubSpeciesCollection.prototype.model_constructor = ce4.subspecies.SubSpecies;
