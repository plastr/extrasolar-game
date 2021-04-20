// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.progress contains the Progress model.
goog.provide("ce4.progress.Progress");
goog.provide("ce4.progress.ProgressCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util.EpochDateField');
goog.require('ce4.gamestate');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.progress.Progress = function Progress(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.progress.Progress, lazy8.chips.Model);

/** @override */
ce4.progress.Progress.prototype.fields = {
    key: new lazy8.chips.Field({id_field:true}),
    value: new lazy8.chips.Field({required:true}),
    achieved_at: new ce4.util.EpochDateField({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

ce4.progress.create_key = function(key, value) {
    // Issue the request to the server to create a new progress key. The response will comeback
    // via a chip which will add the key to the progress collection.
    if (value === undefined) {
        value = "";
    }
    ce4.util.json_post({
        url: ce4.util.url_api(ce4.gamestate.urls.create_progress),
        data: {'key':key, 'value':value},
        error: function(data) {
            console.error("Error when creating progress key.");
            console.error(data);
        }
    });
};

ce4.progress.Progress.prototype.reset_key = function() {
    // Issue the request to the server to reset this key. The response will comeback
    // via a chip which will delete the key from the progress collection.
    ce4.util.json_post({
        url: ce4.util.url_api(this.urls.reset),
        error: function(data) {
            console.error("Error when reseting progress key.");
            console.error(data);
        }
    });
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.progress.ProgressCollection = function ProgressCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.progress.ProgressCollection, lazy8.chips.Collection);

/** @override */
ce4.progress.ProgressCollection.prototype.model_constructor = ce4.progress.Progress;
