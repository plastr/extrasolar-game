// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.capability contains the Capability model.
goog.provide("ce4.capability.Capability");
goog.provide("ce4.capability.CapabilityCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util.EpochDateField');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.capability.Capability = function Capability(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.capability.Capability, lazy8.chips.Model);

/** @override */
ce4.capability.Capability.prototype.fields = {
    capability_key: new lazy8.chips.Field({id_field:true}),
    uses: new lazy8.chips.Field({required:true}),
    free_uses: new lazy8.chips.Field({required:true}),
    unlimited: new lazy8.chips.Field({required:true}),
    available: new lazy8.chips.Field({required:true}),
    rover_features: new lazy8.chips.Field({required:true})
};

ce4.capability.Capability.prototype.is_unlimited = function is_unlimited() {
    return (this.unlimited !== 0);
};

ce4.capability.Capability.prototype.is_available = function is_available() {
    return (this.available !== 0);
};

ce4.capability.Capability.prototype.uses_left = function uses_left() {
    return this.free_uses - this.uses;
};

ce4.capability.Capability.prototype.uses_left_text = function uses_left_text() {
    return this.is_unlimited() ? '&infin;' : ''+this.uses_left(); // Character options: &infin; &#xa74e; &#xa74f;
};

// Returns True if this capability has uses left (can be used by the user)
ce4.capability.Capability.prototype.has_uses = function has_uses() {
    if(!this.is_available())    return false;
    else                        return (this.is_unlimited() || this.uses_left() > 0);
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.capability.CapabilityCollection = function CapabilityCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.capability.CapabilityCollection, lazy8.chips.Collection);

/** @override */
ce4.capability.CapabilityCollection.prototype.model_constructor = ce4.capability.Capability;
