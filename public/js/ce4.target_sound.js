// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.target_sound contains the TargetSound model.
goog.provide("ce4.target_sound.TargetSound");
goog.provide("ce4.target_sound.TargetSoundCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.target_sound.TargetSound = function TargetSound(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.target_sound.TargetSound, lazy8.chips.Model);

/** @override */
ce4.target_sound.TargetSound.prototype.fields = {
    sound_key: new lazy8.chips.Field({id_field:true}),
    title:     new lazy8.chips.Field({required:true}),
    video_id:  new lazy8.chips.Field({required:true})
};

/**
 * Return the current URL 
 */
ce4.target_sound.TargetSound.prototype.video_url = function() {
    return "https://player.vimeo.com/video/" + this.video_id;
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.target_sound.TargetSoundCollection = function TargetSoundCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.target_sound.TargetSoundCollection, lazy8.chips.Collection);

/** @override */
ce4.target_sound.TargetSoundCollection.prototype.model_constructor = ce4.target_sound.TargetSound;
