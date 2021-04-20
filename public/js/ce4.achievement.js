// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.achievement contains the Achievment model.
goog.provide("ce4.achievement.Achievment");
goog.provide("ce4.achievement.AchievmentCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util.EpochDateField');
goog.require('ce4.assets');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.achievement.Achievment = function Achievment(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.achievement.Achievment, lazy8.chips.Model);

/** @override */
ce4.achievement.Achievment.prototype.fields = {
    achievement_key: new lazy8.chips.Field({id_field:true}),
    title: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    type: new lazy8.chips.Field({required:true}),
    secret: new lazy8.chips.Field({required:true}),
    classified: new lazy8.chips.Field({required:true}),
    icon: new lazy8.chips.Field({required:true}),
    achieved_at: new ce4.util.EpochDateField({required:true}),
    viewed_at: new ce4.util.EpochDateField({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

ce4.achievement.Achievment.prototype.was_achieved = function was_achieved() {
    return (this.achieved_at !== null);
};

ce4.achievement.Achievment.prototype.is_secret = function is_secret() {
    return (this.secret !== 0);
};

ce4.achievement.Achievment.prototype.is_classified = function is_classified() {
    return (this.classified !== 0);
};

ce4.achievement.Achievment.prototype.url_icon = function url_icon() {
    return ce4.assets.achievement[this.icon];
};

ce4.achievement.Achievment.prototype.hasBeenViewed = function() {
    return this.viewed_at !== null;
};

ce4.achievement.Achievment.prototype.markViewed = function() {
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

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.achievement.AchievmentCollection = function AchievmentCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.achievement.AchievmentCollection, lazy8.chips.Collection);

/** @override */
ce4.achievement.AchievmentCollection.prototype.model_constructor = ce4.achievement.Achievment;
