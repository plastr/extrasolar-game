// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.rover contains the Rover model.
goog.provide("ce4.rover.Rover");
goog.provide("ce4.rover.RoverCollection");

goog.require('ce4.util');
goog.require('ce4.geometry');
goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');
goog.require('ce4.target.TargetCollection');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.rover.Rover = function Rover(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.rover.Rover, lazy8.chips.Model);

/** @override */
ce4.rover.Rover.prototype.fields = {
    rover_id: new lazy8.chips.Field({id_field:true}),
    rover_key: new lazy8.chips.Field({required:true}),
    rover_chassis: new lazy8.chips.Field({required:true}),
    activated_at: new lazy8.chips.Field({required:true}),
    active: new lazy8.chips.Field({required:true}),
    lander: new lazy8.chips.Field({required:true}),
    max_unarrived_targets: new lazy8.chips.Field({required:true}),
    min_target_seconds: new lazy8.chips.Field({required:true}),
    max_target_seconds: new lazy8.chips.Field({required:true}),
    max_travel_distance: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

/** @override */
ce4.rover.Rover.prototype.collections = {
    targets: ce4.target.TargetCollection
};

// Get an array of targets, sorted by arrival time.
ce4.rover.Rover.prototype.all_targets = function(opt_descend) {
    return this.targets.sorted('arrival_time', opt_descend);
};

// Get an array of processed targets, sorted by arrival time.
ce4.rover.Rover.prototype.processed_targets = function(opt_descend) {
    var processed = this.targets.filter(function(target) {
        // This handles the case when the target is being reprocessed but an old image exists.
        return target.processed || target.images.PHOTO !== undefined;
    });
    return ce4.util.sortBy(processed, 'arrival_time', opt_descend);
};

// Get an array of unprocessed targets, sorted by arrival time.
ce4.rover.Rover.prototype.unprocessed_targets = function(opt_descend) {
    var unprocessed = this.targets.filter(function(target) {
        return !target.processed && target.images.PHOTO === undefined;
    });
    return ce4.util.sortBy(unprocessed, 'arrival_time', opt_descend);
};

// Returns true if this rover is a special 'hidden' rover, false otherwise.
ce4.rover.Rover.prototype.is_hidden = function() {
    if (this.rover_key === "RVR_S1_NEW_ISLAND") return true;
    else return false;
};

ce4.rover.Rover.prototype.createTarget = function(lat, lng, yaw, pitch, arrival_delta, metadata, success, failure) {
    // These are the required fields by the server to create the target.
    var fields = {
        lat: lat,
        lng: lng,
        pitch: pitch,
        yaw: yaw,
        arrival_delta: arrival_delta,
        metadata: metadata
    };

    // Issue the request to the server to create the new target. The response will comeback
    // via a chip which will update the newly created target.
    ce4.util.json_post({
        url: this.urls.target,
        data: fields,
        success: function(data) {
            if (success !== undefined) {
                success();
            }
        },
        error: function() {
            console.error("Error in rover.createTarget.");
            if (failure !== undefined) {
                failure();
            }
        }
    });
};

ce4.rover.Rover.prototype.getCoords = function() {
    // The last element of the sorted processed targets array is the most recent.
    var processed = this.processed_targets();
    var last_processed_target = processed[processed.length - 1];
    return [last_processed_target.lat, last_processed_target.lng];
};

ce4.rover.Rover.prototype.getFirstUnprocessedTarget = function() {
    var all_targets = this.all_targets();
    for (var i=0; i<all_targets.length; i++) {
        if (!all_targets[i].processed) {
            return all_targets[i];
        }
    }
    return null;
};

ce4.rover.Rover.prototype.getLastProcessedTarget = function() {
    var all_targets = this.all_targets();
    for (var i=all_targets.length - 1; i>=0; i--) {
        if (all_targets[i].processed) {
            return all_targets[i];
        }
    }
    return null;
};

// Interpolate between active targets to the the anticipated rover position.
ce4.rover.Rover.prototype.getCoordsProjected = function() {
    // Search the list to find the last arrived-at and next unarrived-at targets.
    var all_targets = this.all_targets();
    var last_arrived = null;
    var first_unarrived = null;
    for (var i=0; i<all_targets.length; i++) {
        if (all_targets[i].has_arrived()) {
            last_arrived = all_targets[i];
        } else if (first_unarrived === null) {
            first_unarrived = all_targets[i];
        }
    }
    // If first_unarrived_at did not come from the server, then the start_time will be undefined.
    if (last_arrived && first_unarrived) {
        var interp =(ce4.gamestate.user.epoch_now() - first_unarrived.start_time)/
            (first_unarrived.arrival_time - first_unarrived.start_time);
        if (interp <= 0.0) {
            return [last_arrived.lat, last_arrived.lng];
        } else if (interp >= 1.0) {
            return [first_unarrived.lat, first_unarrived.lng];
        } else {
            return [last_arrived.lat + interp*(first_unarrived.lat - last_arrived.lat), last_arrived.lng + interp*(first_unarrived.lng - last_arrived.lng)];
        }
    }
    else if (last_arrived) {
        return [last_arrived.lat, last_arrived.lng];
    }
    return [first_unarrived.lat, first_unarrived.lng];
};

ce4.rover.Rover.prototype.getLastTarget = function() {
    var lastTarget = this.targets.max('arrival_time');
    ce4.util.assert(lastTarget !== undefined);
    return lastTarget;
};

ce4.rover.Rover.prototype.isAtLastTarget = function() {
    return (this.getLastTarget().has_arrived() === true);
};

ce4.rover.Rover.prototype.canCreateTarget = function() {
    return this.unprocessed_targets().length < this.max_unarrived_targets;
};

ce4.rover.Rover.prototype.getMaxTargets = function() {
    return this.max_unarrived_targets;
};

ce4.rover.Rover.prototype.getAllPictures = function() {
    var all_targets = this.all_targets(true);
    // Only return targets with pictures.
    return ce4.util.filter(all_targets, function(target) {
        return target.picture;
    });
};

ce4.rover.Rover.prototype.getProcessedPictures = function() {
    var processed = this.processed_targets(true);
    // Only return targets with pictures.
    return ce4.util.filter(processed, function(target) {
        return target.picture;
    });
};

ce4.rover.Rover.prototype.getUnprocessedPictures = function() {
    var unprocessed = this.unprocessed_targets(true);
    // Only return targets with pictures.
    return ce4.util.filter(unprocessed, function(target) {
        return target.picture;
    });
};

// Returns the total distance, in meters, this rover has traveled so far.
// This method only considers targets which have been arrived at as of the current gametime.
ce4.rover.Rover.prototype.distance_traveled = function() {
    var total_distance = 0;
    var sorted_targets = this.processed_targets();
    for (var i=1; i<sorted_targets.length; i++) {
        if (sorted_targets[i].has_arrived() === true) {
            var t0 = sorted_targets[i-1];
            var t1 = sorted_targets[i];
            total_distance += ce4.geometry.distCanonical([t0.lat, t0.lng], [t1.lat, t1.lng]);
        }
    }
    return total_distance;
}

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.rover.RoverCollection = function RoverCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.rover.RoverCollection, lazy8.chips.Collection);

/** @override */
ce4.rover.RoverCollection.prototype.model_constructor = ce4.rover.Rover;
