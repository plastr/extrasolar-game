// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.mission contains the Mission model.
goog.provide("ce4.mission");
goog.provide("ce4.mission.Mission");
goog.provide("ce4.mission.MissionCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util');
goog.require('ce4.util.EpochDateField');
goog.require('ce4.gamestate');
goog.require('ce4.mission.callbacks');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.mission.Mission = function Mission(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.mission.Mission, lazy8.chips.Model);

/** @override */
ce4.mission.Mission.prototype.fields = {
    mission_id: new lazy8.chips.Field({id_field:true}),
    mission_definition: new lazy8.chips.Field({required:true}),
    parent_id: new lazy8.chips.Field({required:true}),
    parent_definition: new lazy8.chips.Field({required:true}),
    type: new lazy8.chips.Field({required:true}),
    title: new lazy8.chips.Field({required:true}),
    summary: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    done_notice: new lazy8.chips.Field({required:true}),
    done: new lazy8.chips.Field({required:true}),
    done_at: new ce4.util.EpochDateField({required:true}),
    sort: new lazy8.chips.Field({required:true}),
    title_icon: new lazy8.chips.Field({required:true}),
    description_icon: new lazy8.chips.Field({required:true}),
    started_at: new ce4.util.EpochDateField({required:true}),
    viewed_at: new ce4.util.EpochDateField({required:true}),
    specifics: new lazy8.chips.Field({required:true}),
    region_ids: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

// TODO JLP: How to handle this. Ideally with a better listen/event system or KVO like.
ce4.mission.Mission.prototype.merge_chip_struct = function(chip_struct, opt_check_required) {
    if (this.done === 0 && chip_struct.done === 1) {
        // If this mission was just finished, call the appropriate hook.
        ce4.mission.callbacks.get_hook(this.mission_definition, 'done')();
    }

    // Call super.
    lazy8.chips.Model.prototype.merge_chip_struct.call(this, chip_struct, opt_check_required);
};

ce4.mission.Mission.prototype.icon = function() {
    var icon = ce4.mission.icons[this.type];
    if (icon !== undefined)
        return icon;
    return ce4.mission.icons['DEFAULT'];
};

ce4.mission.Mission.prototype.is_done = function() {
    return this.done;
};

ce4.mission.Mission.prototype.get_first_incomplete_part = function() {
    if (this.parts) {
        for (var i = 0; i < this.parts.length; i++) {
            if (!this.parts[i].done) {
                return this.parts[i];
            }
        }
    }
    if (!this.done) {
        return this;
    }
};

ce4.mission.Mission.prototype.get_done_notice = function() {
    return this.done_notice || "";
};

ce4.mission.Mission.prototype.get_hook = function(hookname) {
    return ce4.mission.callbacks.get_hook(this.mission_definition, hookname);
};

ce4.mission.Mission.prototype.mission_url = function() {
    return ce4.util.url_task(this.mission_id);
};

ce4.mission.Mission.prototype.title_icon_url = function(return_active) {
    var url = ce4.assets.task[this.title_icon] || ce4.assets.task.DEFAULT;
    return (!this.done || return_active ? url.active : url.done);
};

ce4.mission.Mission.prototype.description_icon_url = function(return_active) {
    // For subtask descriptions, return a special icon if the task is done.
    if (this.done)
        return ce4.assets.task['TASK_ICON_COMPLETED'].done
    var url = ce4.assets.task[this.description_icon] || ce4.assets.task.DEFAULT;
    return (!this.done || return_active ? url.active : url.done);
};

ce4.mission.Mission.prototype.get_status = function() {
    // Get the current status from the mission's callback.
    var status = this.get_hook('status')();
    if (status === undefined)
        return '';
    return '<strong>' + status + '</strong>';
}

ce4.mission.Mission.prototype.hasBeenViewed = function() {
    return this.viewed_at !== null;
};

// If this mission has parts, all those child parts will also be marked viewed by the server.
ce4.mission.Mission.prototype.markViewed = function() {
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

//------------------------------------------------------------------------------
// Return all region_ids for a mission and its submissions (parts)
ce4.mission.Mission.prototype.allRegionIDs = function() {
    var all_ids = [];
    all_ids.push.apply(all_ids, this.region_ids);
    if(this.parts) {
        for (var i = 0; i < this.parts.length; i++) {
            all_ids.push.apply(all_ids, this.parts[i].region_ids);
        }
    }
    return all_ids;
};

ce4.mission.icons = {
    'SURVEY':'survey',
    'MOVE':'move',
    'TAKE_PHOTO':'takephoto',
    'SPECIES_FIND':'speciesfind'
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.mission.MissionCollection = function MissionCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.mission.MissionCollection, lazy8.chips.Collection);

/** @override */
ce4.mission.MissionCollection.prototype.model_constructor = ce4.mission.Mission;

// Return a the first Mission object for the given mission_definition if it exists in the collection.
ce4.mission.MissionCollection.prototype.for_definition = function(mission_definition) {
    return this.find(function(mission) {
        return mission.mission_definition === mission_definition;
    });
};

// Returns true if there is at least one mission with the given mission_definition in the
// collection, false otherwise.
ce4.mission.MissionCollection.prototype.has_definition = function(mission_definition) {
    return this.for_definition(mission_definition) !== undefined;
};
