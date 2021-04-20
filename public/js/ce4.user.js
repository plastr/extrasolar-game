// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.user contains the User model.
goog.provide("ce4.user.User");

goog.require('lazy8.chips.RootModel');
goog.require('lazy8.chips.Field');

goog.require('ce4.shop.Shop');
goog.require('ce4.rover.RoverCollection');
goog.require('ce4.mission.MissionCollection');
goog.require('ce4.message.MessageCollection');
goog.require('ce4.species.SpeciesCollection');
goog.require('ce4.region.RegionCollection');
goog.require('ce4.progress.ProgressCollection');
goog.require('ce4.achievement.AchievmentCollection');
goog.require('ce4.capability.CapabilityCollection');
goog.require('ce4.voucher.VoucherCollection');
goog.require('ce4.map_tile.MapTileCollection');
goog.require('ce4.invite.InviteCollection');
goog.require('ce4.tutorial.Tutorial');

goog.require('ce4.util');
goog.require('ce4.util.EpochDateField');
goog.require('ce4.util.TimestampDateField');

/**
 * @constructor
 * @extends {lazy8.chips.RootModel}
 */
ce4.user.User = function User(chip_struct) {
    lazy8.chips.RootModel.call(this, chip_struct);
    this.wire_up_missions_hierarchy();
    this.tutorial = new ce4.tutorial.Tutorial({user: this, createKey: ce4.progress.create_key});
};
goog.inherits(ce4.user.User, lazy8.chips.RootModel);

/** @override */
ce4.user.User.prototype.fields = {
    // The Shop object.
    shop: new lazy8.chips.Field({required:true, model_constructor:ce4.shop.Shop}),

    // The remaining plain User fields.
    email: new lazy8.chips.Field({required:true}),
    first_name: new lazy8.chips.Field({required:true}),
    last_name: new lazy8.chips.Field({required:true}),
    // Provides epoch_date function, epoch as a Date object.
    epoch: new ce4.util.TimestampDateField({required:true}),
    dev: new lazy8.chips.Field({required:true}),
    auth: new lazy8.chips.Field({required:true}),
    valid: new lazy8.chips.Field({required:true}),
    activity_alert_frequency: new lazy8.chips.Field({required:true}),
    viewed_alerts_at: new ce4.util.EpochDateField({required:true}),
    invites_left: new lazy8.chips.Field({required:true}),
    inviter_id: new lazy8.chips.Field({required:true}),
    // Object value, possibly containing url_public_profile if inviter_id is not null.
    inviter: new lazy8.chips.Field({required:true}),
    // String value or null. If not null this is a voucher_key.
    current_voucher_level: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

/** @override */
ce4.user.User.prototype.root_id = "user";

/** @override */
ce4.user.User.prototype.collections = {
    rovers: ce4.rover.RoverCollection,
    missions: ce4.mission.MissionCollection,
    messages: ce4.message.MessageCollection,
    species: ce4.species.SpeciesCollection,
    regions: ce4.region.RegionCollection,
    progress: ce4.progress.ProgressCollection,
    achievements: ce4.achievement.AchievmentCollection,
    capabilities: ce4.capability.CapabilityCollection,
    vouchers: ce4.voucher.VoucherCollection,
    map_tiles: ce4.map_tile.MapTileCollection,
    invitations: ce4.invite.InviteCollection
};

// Returns the number of seconds that have elapsed since user.epoch.
// This is a 'now' value that can be used in comparison to the after epoch values in the
// the gamestate, e.g. target.arrival_time etc.
ce4.user.User.prototype.epoch_now = function() {
    var now = ce4.util.utc_now_in_ms()/1000;
    var seconds_past_epoch = now - this.epoch;
    return seconds_past_epoch;
};

// Convert from a date expressed as seconds-since-epoch into a Javascript Date.
ce4.user.User.prototype.epoch_to_date = function(seconds_since_epoch) {
    var seconds = seconds_since_epoch + this.epoch;
    return ce4.util.from_ts(seconds);
}

// Update the viewed_alerts_at field on the server and this object to 'now'.
ce4.user.User.prototype.update_viewed_alerts_at = function() {
    ce4.util.json_post({
        url: this.urls.update_viewed_alerts_at,
        data: {},
        error: function() {
            console.error("Error in update_viewed_alerts_at.");
        }
    });
};

// Whenever the missions Collection changes, the parent child relationship between
// Missions needs to be reestablished.
// TODO JLP: This method can be improved, most likely by having a Mission do this itself.
ce4.user.User.prototype.wire_up_missions_hierarchy = function() {
    var user = this;
    // First wire up the child/parent relationships
    user.missions.forEach(function(mission) {
        if (mission.parent_id !== null) {
            var parent = user.missions.get(mission.parent_id);
            mission.parent = parent;
            if (parent.parts === undefined) {
                parent.parts = [];
            }
            if ($.inArray(mission, parent.parts) === -1) {
                parent.parts.push(mission);
            }
        }
    });

    // Then be sure the parts (child) property is sorted.
    user.missions.forEach(function(mission) {
        if (mission.parts && mission.parts.length > 0) {
            ce4.util.sortBy(mission.parts, 'sort', true);
        }
    });
};

// Get the list of done missions as an array. Pass 'root' as opt_root_only if only the root
// parent missions should be returned.
ce4.user.User.prototype.done_missions = function(opt_root_only) {
    var done = this.missions.filter(function(mission) {
        if (opt_root_only === "root") {
            return mission.done && mission.parent_id === null;
        } else {
            return mission.done;
        }
    });
    return ce4.util.sortBy(done, 'done_at', true);
};

// Get the list of incomplete missions as an array. Pass 'root' as opt_root_only if only the root
// parent missions should be returned.
ce4.user.User.prototype.notdone_missions = function(opt_root_only) {
    var notdone = this.missions.filter(function(mission) {
        if (opt_root_only === "root") {
            return !mission.done && mission.parent_id === null;
        } else {
            return !mission.done;
        }
    });
    return ce4.util.sortBy(notdone, 'sort', true);
};

// Return all the Species known to this user sorted by species_id.
ce4.user.User.prototype.species_list = function() {
    var species_sorted = this.species.sorted('detected_at', true);
    // Remove from the list any species IDs that are reserved for species that are too far for accurate ID.
    var species_pruned = [];
    for (var i in species_sorted) {
        if (!ce4.species.is_too_far_for_id(species_sorted[i].species_id)) {
            species_pruned.push(species_sorted[i]);
        }
    }
    return species_pruned;
};

// Return all the messages received by this user sorted in descending order by sent_at.
ce4.user.User.prototype.messages_list = function() {
    return this.messages.sorted('sent_at', true);
};

// Returns true if this user has any Messages.
ce4.user.User.prototype.has_messages = function() {
    return !this.messages.isEmpty();
};

// Return all the targets with pictures created by this user sorted in ascending order by arrival_time.
ce4.user.User.prototype.picture_targets_list = function() {
    var all_targets = [];
    ce4.util.forEach(this.sorted_rovers(true), function(rover) {
        all_targets = all_targets.concat(rover.getAllPictures());
    });
    return all_targets;
};

// Return only the processed targets sorted in ascending order by arrival_time.
ce4.user.User.prototype.processed_picture_targets_list = function() {
    var all_targets = this.picture_targets_list();
    var processed_targets = [];
    for (var i=0; i<all_targets.length; i++) {
        if (all_targets[i].processed === 1) {
            processed_targets.push(all_targets[i]);
        }
    }
    return processed_targets;
};

// Return a list of all image rects.
ce4.user.User.prototype.image_rect_list = function() {
    var all_image_rects = [];
    var picture_targets = this.picture_targets_list();
    ce4.util.forEach(picture_targets, function(pic) {
        all_image_rects = all_image_rects.concat(pic.image_rects.unsorted());
    });
    return all_image_rects;
};

// Loop over all rovers to count the number of unviewed photos.
ce4.user.User.prototype.unviewed_photo_count = function() {
    var count = 0;
    this.rovers.forEach(function(rover) {
        var rover_pictures = rover.getProcessedPictures();
        ce4.util.forEach(rover_pictures, function(target) {
            if (!target.hasBeenViewed()) {
                count++;
            }
        });
    });
    return count;
};

// Count the number of unviewed tasks
ce4.user.User.prototype.unviewed_task_count = function() {
    var count = 0;
    this.notdone_missions("root").forEach(function(item) {
        if(!item.hasBeenViewed()) count++;
    });

    this.done_missions("root").forEach(function(item) {
        if(!item.hasBeenViewed()) count++;
    });
    return count;
};

// Count the number of unviewed species
ce4.user.User.prototype.unviewed_species_count = function() {
    var count = 0;
    this.species_list().forEach(function(item) {
        if(!item.hasBeenViewed()) {
            count++;
        }
    });
    return count;
};

// Count the number of unread messages.
ce4.user.User.prototype.unread_message_count = function() {
    var count = 0;
    this.messages.forEach(function(message) {
        if(!message.is_read()) {
            count++;
        }
    });
    return count;
};

// Count new alerts on Home tab
ce4.user.User.prototype.unviewed_alerts = function(include_viewed) {
    var unviewed = [];
    var home_viewed_at = this.viewed_alerts_at_ms();
    include_viewed = typeof include_viewed !== 'undefined' ? include_viewed : false;

    // New Missions
    var notdone_missions = ce4.gamestate.user.notdone_missions("root");
    if(notdone_missions.length > 0){
        $.each(notdone_missions, function(i, mission){
            if(include_viewed || !mission.hasBeenViewed() && mission.started_at_ms() > home_viewed_at) unviewed.push({type: ce4.ui.ALERT_MISSION, object: mission, time: mission.started_at_ms()});
        });
    }

    // Done Missions
    var done_missions = ce4.gamestate.user.done_missions("root");
    if(done_missions.length > 0){
        $.each(done_missions, function(i, mission){
            if(include_viewed || mission.done_at_ms() > home_viewed_at) unviewed.push({type: ce4.ui.ALERT_MISSION_DONE, object: mission, time: mission.started_at_ms()});
        });
    }

    // New Mail
    this.messages.forEach(function(message) {
        if(include_viewed || !message.is_read() && message.sent_at_ms() > home_viewed_at) unviewed.push({type: ce4.ui.ALERT_MESSAGE, object: message, time: message.sent_at_ms()});
    });

    // New Pictures
    this.rovers.forEach(function(rover) {
        ce4.util.forEach(rover.getProcessedPictures(), function(target) {
            if (include_viewed || !target.hasBeenViewed() && target.arrival_time_ms() > home_viewed_at) unviewed.push({type: ce4.ui.ALERT_PICTURE, object: target, time: target.arrival_time_ms()});
        });
    });

    // New Discoveries
    ce4.util.forEach(this.species_list(), function(discovery) {
        if(include_viewed || !discovery.hasBeenViewed() && discovery.available_at_ms() > home_viewed_at && discovery.isFullyAvailable()) unviewed.push({type: ce4.ui.ALERT_DISCOVERY, object: discovery, time: discovery.available_at_ms()});
    });

    // New Achievements
    this.achievements.forEach(function(achievement) {
        if (include_viewed && achievement.was_achieved() || !achievement.hasBeenViewed() && achievement.achieved_at_ms() > home_viewed_at) unviewed.push({type: ce4.ui.ALERT_ACHIEVEMENT, object: achievement, time: achievement.achieved_at_ms()});
    });

    // Return total
    return unviewed.sort(function(a,b){return a.time - b.time});
};

// Given a target ID, return the Target object or null if not found.
ce4.user.User.prototype.find_target = function(target_id) {
    // Find the first rover that has this target, if any.
    var rover = this.rovers.find(function(rover) {
        return rover.targets.contains(target_id);
    });
    // If a rover was found, return the Target object.
    if (rover !== undefined) {
        return rover.targets.get(target_id);
    } else {
        return null;  // Not found.
    }
};

/**
 * Returns a list of rovers, sorted by the date of their last target's arrival time.
 * Optionally, opt_descend can be set to true and the rovers will be sorted in descending
 * order.  For sorting of other member collections, the Collection.sorted() function
 * is usually suitable.
 *
 * @param {boolean=} opt_descend If true, sort in descending order.
 */
ce4.user.User.prototype.sorted_rovers = function(opt_descend) {
    var models_array = this.rovers.unsorted();
    var compareFn;

    if (opt_descend === true) {
        compareFn = function(a, b) {
            return a.getLastTarget().arrival_time < b.getLastTarget().arrival_time ? 1
            : a.getLastTarget().arrival_time > b.getLastTarget().arrival_time ? -1 : 0;
        };
    } else {
        var compareFn = function(a, b) {
            return a.getLastTarget().arrival_time > b.getLastTarget().arrival_time ? 1
            : a.getLastTarget().arrival_time < b.getLastTarget().arrival_time ? -1 : 0;
        };
    }
    models_array.sort(compareFn);
    return models_array;
};

/**
 * Returns a list of achievements, sorted in a manner that puts achieved items first,
 * sorted by achieved_at, with other ambiguity resolved alphabetically by title.
 */
ce4.user.User.prototype.sorted_achievements = function() {
    var models_array = this.achievements.unsorted();
    // Sort primarily by achieved_at and next by title.
    var compareFn = function(a, b) {
        if (a.achieved_at === b.achieved_at) {
            return a.title > b.title ? 1 : -1
        }
        if (a.achieved_at === null) return 1;
        if (b.achieved_at === null) return -1;
        return a.achieved_at > b.achieved_at ? 1 : -1;
    };
    models_array.sort(compareFn);
    return models_array;
};

/**
 * Get the sorted achievement list, as above, but filter it to only include
 * visible nonclassified achievements.
 */
ce4.user.User.prototype.visible_nonclassified_achievements = function() {
    var achievements = this.sorted_achievements();
    var models_array = [];
    ce4.util.forEach(achievements, function(ach) {
        if (!ach.is_classified() && (ach.was_achieved() || !ach.is_secret())) {
            models_array.push(ach);
        }
    });
    return models_array;
};

/**
 * Get the sorted achievement list, as above, but filter it to only include
 * visible classified achievements.
 */
ce4.user.User.prototype.visible_classified_achievements = function() {
    var achievements = this.sorted_achievements();
    var models_array = [];
    ce4.util.forEach(achievements, function(ach) {
        if (ach.is_classified() && (ach.was_achieved() || !ach.is_secret())) {
            models_array.push(ach);
        }
    });
    return models_array;
};

//-----------------------------------------------------------------------------
// Helper functions for displaying the player's private account data.

ce4.user.User.prototype.profile_account_activation_date = function() {
    var epoch_created = this.progress.get("PRO_USER_CREATED").achieved_at;
    var date_created = this.epoch_to_date(epoch_created);
    return date_created.toString("MMMM dd, yyyy");
};

ce4.user.User.prototype.profile_time_since_activated = function() {
    var epoch_created = this.progress.get("PRO_USER_CREATED").achieved_at;
    var epoch_delta = this.epoch_now() - epoch_created;
    return ce4.util.format_time_approx(epoch_delta*1000);
};

// Return the sum distance traveled by all rovers, not including pending targets.
ce4.user.User.prototype.profile_distance_traveled = function() {
    var total_distance = 0;
    this.rovers.forEach(function(rover) {
        total_distance += rover.distance_traveled();
    });
    return total_distance.toFixed(1);
};

// Get a count of all processed pictures.
ce4.user.User.prototype.profile_pictures_taken = function() {
    var processed_count = 0;
    var all_pictures = this.picture_targets_list();
    ce4.util.forEach(all_pictures, function(pic) {
        if (pic.processed === 1) {
            processed_count += 1;
        }
    });
    return processed_count;
};

// Get a count of all image tags with a successfully identified species.
ce4.user.User.prototype.profile_successful_image_tags = function() {
    var count = 0;
    var image_rects = this.image_rect_list();
    ce4.util.forEach(image_rects, function(rect) {
        if (rect.has_species())
            count += 1;
    });
    return count;
};

// Get a count of all unique species matching the given type (e.g. "PLANT").
ce4.user.User.prototype.profile_species_count_of_type = function(type) {
    var count = 0;
    ce4.util.forEach(this.species, function(s) {
        if (s.type === type && !ce4.species.is_too_far_for_id(s.species_id)) {
            count += 1;
        }
    });
    return count;
};

// Returns a recent point on the map as a fallback safe location to center on by default.
// Currently this is newest, non-hidden rover's last location.
ce4.user.User.prototype.get_recent_map_point = function() {
    // Find the all the non hidden rovers, searching newest first.
    var non_hidden = ce4.util.filter(this.sorted_rovers(true), function(rover) {
        return !rover.is_hidden();
    });
    if (non_hidden.length > 0) {
        return non_hidden[0].getLastProcessedTarget().getCoords();
    } else {
        // Fallback on the first rover's lander.
        var first_lander = this.sorted_rovers()[0].lander;
        return [first_lander.lat, first_lander.lng];
    }
};

//-----------------------------------------------------------------------------
// Helper functions for specifying which display elements are visible.

ce4.user.User.prototype.is_store_enabled = function() {
    return (this.auth !== 'EDMO');
};

ce4.user.User.prototype.is_social_enabled = function() {
    return (ce4.gamestate.config.use_social_networks && this.auth !== 'EDMO');
};

