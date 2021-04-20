// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.leaflet.target contains the map target marker.
goog.provide('ce4.leaflet.target');
goog.provide('ce4.leaflet.target.TargetDisplay');

goog.require('ce4.leaflet.assets.icons');
goog.require('ce4.leaflet.assets.styles');
goog.require('ce4.leaflet.region.styles');
goog.require('ce4.leaflet.controls.DirectionWizard');


//------------------------------------------------------------------------------
// Constructor for a new map marker
// Handles icon, thumbnail, limit circlem and line from previous marker.
ce4.leaflet.target.TargetDisplay = function(extraSolarMap, prevTarget, rover, opt_target)
{
    this.extraSolarMap = extraSolarMap;
    this.leafletMap = this.extraSolarMap.leafletMap;
    this.rover = rover;
    this.marker = undefined;
    this.target = opt_target || undefined;

    // Build a new target to be initialized
    if (opt_target === undefined)
    {
        var roverLoc = rover.getCoordsProjected();
        this.new_target_fields = {
            lat: roverLoc[0],
            lng: roverLoc[1],
            pitch: 0.0,
            yaw: 0.0,
            arrival_time_date: null};
    }

    // Draw a line to the target from its anchor, new targets and moving rovers anchor target to rover
    var lineStart = this.isNewTarget() || (prevTarget.has_arrived() && this.target && !this.target.has_arrived())
            ? rover.getCoordsProjected()
            : prevTarget.getCoords();

    this.path = new L.Polyline([lineStart], ce4.leaflet.region.styles[(!this.isNewTarget() && this.target.has_arrived()) ? ce4.region.styles.PROCESSED_LINE : ce4.region.styles.PENDING_LINE]);
    this.leafletMap.addLayer(this.path);

    this.setLineEnd(this.getTargetLocation());

    // If the rover is traversing between the previous target and this target,
    // draw a second line from the previous target to the rover's current position.
    if (prevTarget.has_arrived() && this.target && !this.target.has_arrived())
    {
        this.pathFromPrev = new L.Polyline([prevTarget.getCoords(), rover.getCoordsProjected()], ce4.leaflet.region.styles[ce4.region.styles.PROCESSED_LINE]);
        this.leafletMap.addLayer(this.pathFromPrev);
    }

    // Drag Control Marker
    if(this.isNewTarget())
    {
        this.marker = new L.Marker(this.getLocation(), ce4.leaflet.assets.styles.DRAG_CONTROL);
        this.leafletMap.addLayer(this.marker);

        // Callbacks for dragging the marker
        this.marker.addEventListener('click', this.onClick, this);
        this.marker.addEventListener('dragstart', this.onDragStart, this);
        this.marker.addEventListener('drag', this.onDrag, this);
        this.marker.addEventListener('dragend', this.onDragEnd, this);

        // Create cursor distance label
        this.distLabel = L.DomUtil.create('div', 'distance-label');
    }
    // Picture Marker
    else if(this.target.picture)
    {
        this.marker = new L.Marker(this.getLocation(), $.extend({iconAngle: this.target.yaw/Math.PI*180}, this.target.has_arrived() ? ce4.leaflet.assets.styles.TARGET_DONE : ce4.leaflet.assets.styles.TARGET_PENDING));
        this.leafletMap.addLayer(this.marker);


        this.marker.bindPopup("", {className: 'standard-leaflet-popup', offset: new L.Point(0,-50)});

        // Show the yaw of the picture taken
        this.marker.addEventListener('popupopen', this.showPhotoAngle, this);
        this.marker.addEventListener('popupopen', this.populatePopupContent, this);
    }
};

//------------------------------------------------------------------------------
// Setup Picture popup
// FUTU: There should probably be a ce4.ui.makeThumbnail(target) function that can be called here, and in ce4.ui.js
ce4.leaflet.target.TargetDisplay.prototype.populatePopupContent = function()
{
    var content;

    // Photo is ready
    if (this.target.has_available_photo()) {
        content = $("<ul/>").append(xri.ui.makeThumbnail(this.target.images.THUMB || this.target.images.PHOTO, {
                link:  this.target.picture_url(),
                height:   "150px",
                width:    "200px",
                lazy:     false,
                news:     !this.target.hasBeenViewed(),
                sound:    this.target.has_sound(),
                infrared: this.target.has_infrared(),
                tags:     this.target.image_rects.getCount(),
                desc:     this.target.get_description()})).addClass("thumb-list").prop('outerHTML');
    }
    // Photo is overdue
    else if (this.target.has_arrived()) {
        content = "<p>Waiting for data.</p>";
    }
    // Photo is pending
    else {
        content = " <div id=\"pending-photo1\" style=\"width: 250px;\"><center><font class=\"direction-wizard-font\">" + ("Arriving in " + ce4.util.format_time_until(this.target.arrival_time_ms())).replace("in tomorrow", "tomorrow")
                + "<table><tr><td>" + (this.target.is_flash() ? "&nbsp;<div class=\"capability-flash\">&nbsp;</td><td>":"") + (this.target.is_panorama() ? "&nbsp;<div class=\"capability-panorama\">&nbsp;</td><td>" : "") + (this.target.is_infrared() ? "&nbsp;<div class=\"capability-infrared\">&nbsp;</td><td>" : "") + "</td></tr></table>"
                + (this.target.can_abort() ? "<br><button class=\"gradient-button gradient-button-overlay\" id=\"pending-photo-abort\">Abort</button>" : "")
                + "</font></center></div>"
                + " <div id=\"pending-photo2\" style=\"display:none;\"><center>\
                        <font class=\"direction-wizard-font\">uploading instructions</font><br><br>\
                        <img src=\"/img/XRI_logo_0001_satel-icn.png\">\
                        <img src=\"/img/xri-loader.gif\">\
                        <img src=\"/img/XRI_logo_0002_world-icn.png\">\
                        <img src=\"/img/xri-loader.gif\">\
                        <img src=\"/img/XRI_logo_0003_rover-icn.png\">\
                    </center></div>"
                + " <div id=\"pending-photo-fail\" style=\"display:none;\"><center>\
                        <font class=\"direction-wizard-font\">Error while aborting photo.  Please try again.</font><br><br>\
                        <button class=\"gradient-button gradient-button-overlay\" id=\"pending-photo-cancel\">OK</button>\
                    </center></div>";
    }
    this.marker.setPopupContent(content);

    $('#pending-photo-cancel').click($.proxy(function() { this.marker.closePopup(); }, this));
    $('#pending-photo-abort').click($.proxy(function() {
            this.target.abort(function(){}, function(){ce4.util.toggleView('pending-photo', 'pending-photo-fail', 2);});
            ce4.util.toggleView('pending-photo', 'pending-photo1', 0);
            ce4.util.toggleView('pending-photo', 'pending-photo2', 1);
    }, this));

};

//------------------------------------------------------------------------------
// Update the target display
ce4.leaflet.target.TargetDisplay.prototype.update = function()
{
    // Update the point where line changes color if rover is moving
    if (this.path && this.pathFromPrev)
    {
        var roverLatLng = this.rover.getCoordsProjected();
        this.path.spliceLatLngs(0, 1, roverLatLng);
        this.pathFromPrev.spliceLatLngs(1, 1, roverLatLng);
    }

    // If this is the drag marker and it's not active
    if (this.isNewTarget() && this.limitCircle == undefined)
    {
        var roverLatLng = this.rover.getCoordsProjected();
        this.path.spliceLatLngs(0, 1, roverLatLng);
        this.path.spliceLatLngs(1, 1, roverLatLng);

        // Update the marker position
        this.marker.setLatLng(roverLatLng);
    }
};

//------------------------------------------------------------------------------
// Check to see if we have a new target
ce4.leaflet.target.TargetDisplay.prototype.isNewTarget = function()
{
    return (this.target === undefined);
};

//------------------------------------------------------------------------------
// Get the path location
ce4.leaflet.target.TargetDisplay.prototype.getLocation = function()
{
    return this.path.getLatLngs()[1];
};

//------------------------------------------------------------------------------
// Set the line end
ce4.leaflet.target.TargetDisplay.prototype.setLineEnd = function(latlng_or_event)
{
    var latlng = latlng_or_event.latLng || latlng_or_event;

    // Coords should be a pair:  [start, end]
    this.path.spliceLatLngs(1, (this.path.getLatLngs().length > 1) ? 1 : 0, latlng);

    // For new targets
    if (this.isNewTarget())
    {
        this.new_target_fields.lat = latlng[0];
        this.new_target_fields.lng = latlng[1];
    }
};

//------------------------------------------------------------------------------
// Get target location
ce4.leaflet.target.TargetDisplay.prototype.getTargetLocation = function()
{
    return this.isNewTarget()
        ? [this.new_target_fields.lat, this.new_target_fields.lng]
        : this.target.getCoords();
};

//------------------------------------------------------------------------------
// Get the angle, in radians, of the path. 0=north, PI/2=east, etc.
ce4.leaflet.target.TargetDisplay.prototype.getPathDirection = function()
{
    return ce4.geometry.getDirection([this.path.getLatLngs()[0].lat, this.path.getLatLngs()[0].lng],
                                     [this.path.getLatLngs()[1].lat, this.path.getLatLngs()[1].lng]);
};

//------------------------------------------------------------------------------
// Restrict line from marker's anchor to edge of limit circle
ce4.leaflet.target.TargetDisplay.prototype.clipLine = function clipLine()
{
    var CLIP_EPSILON = 0.00001;

    // Clip the line against any regions that limit our motion
    var ray_start = ce4.util.latLngToArray(this.limitCircle.getLatLng());
    var ray_end   = ce4.util.latLngToArray(this.marker.getLatLng());

    // Restrict movement to the limit circle (calculations in meter-space)
    this.dist = ce4.geometry.distCanonical(ray_start, ray_end);     // used by distLabel
    this.direction = ce4.geometry.getDirection(ray_start, ray_end)*180.0/Math.PI; // used by distLabel
    if (this.direction < 0.0) this.direction += 360.0;
    var closestClip = this.rover.max_travel_distance/this.dist;

    // Sometimes, clipping against one taboo region can push us into another
    // Loop through regions, clipping line until closestClip doesn't change
    var max_passes = 3;
    var closest_region;
    do {
        var is_clipped = false;

        // Calculate the end point of the clipped line.
        if(closestClip < 1.0) {
            ray_end[0] = ray_start[0] + closestClip*(ray_end[0]-ray_start[0]);
            ray_end[1] = ray_start[1] + closestClip*(ray_end[1]-ray_start[1]);
            closestClip = 1.0;  // Time t [0,1] of the clip threshold in a parametric line equation
        }

        ce4.gamestate.user.regions.forEach(function(region)
        {
            if (region.restrict === ce4.region.RESTRICT_INSIDE || region.restrict === ce4.region.RESTRICT_OUTSIDE)
            {
                var clip = region.clip_line(ray_start, ray_end);
                if (clip < closestClip)
                {
                    // Note that we clip slightly shorter than the precise intersection to try to prevent
                    // mathematical disagreement between client and server.
                    closestClip = clip * (1.0 - CLIP_EPSILON);
                    is_clipped = true;
                    closest_region = region;
                }
            }
        });
        max_passes -= 1;
    } while (max_passes > 0 && is_clipped);


    // Update the endpoint of the clipped line
    this.setLineEnd(ray_end);

    // Show nearest clip region if it has SHOW_ON_CLIP style
    this.extraSolarMap.showClipRegion(closest_region, ray_end);
};

//------------------------------------------------------------------------------
// If the user starts in a forbidden region, display that region.
ce4.leaflet.target.TargetDisplay.prototype.showForbiddenStartRegion = function showForbiddenStartRegion()
{
    // If we somehow managed to get the starting point of our line in a restricted region, show
    // that region.
    var ray_start = this.rover.getLastTarget().getCoords();
    var forbidden_region = undefined
    ce4.gamestate.user.regions.forEach(function(region) {
        if (region.restrict === ce4.region.RESTRICT_INSIDE && !region.point_inside(ray_start)) {
            forbidden_region = region;
        }
        else if (region.restrict === ce4.region.RESTRICT_OUTSIDE && region.point_inside(ray_start)) {
            forbidden_region = region;
        }
    });

    if (forbidden_region != undefined) {
        this.extraSolarMap.showForbiddenRegion(forbidden_region);
    }
}

//------------------------------------------------------------------------------
// When user drags rover new target icon
ce4.leaflet.target.TargetDisplay.prototype.onClick = function onClick(e)
{
    ce4.ui.leaflet.openTarget(this.rover.getLastProcessedTarget(), this.rover);

};

//------------------------------------------------------------------------------
// When user drags rover new target icon
ce4.leaflet.target.TargetDisplay.prototype.onDragStart = function onDragStart(e)
{
    if (this.limitCircle == undefined) {
        var lastTargetLoc = this.rover.getLastTarget().getCoords();

        // Anchor target marker line to last target
        this.setLineEnd(this.marker.getLatLng());
        this.setPrevLocation(lastTargetLoc);

        // Add Circle map overlay to indicate max range
        this.limitCircle = new L.Circle(lastTargetLoc,
            this.rover.max_travel_distance*ce4.geometry.getMapScaleFactor(lastTargetLoc[0]),
            ce4.leaflet.region.styles[ce4.region.styles.ROVER_LIMIT]);
        this.leafletMap.addLayer(this.limitCircle);

        // Add distance label to drag marker
        this.leafletMap.getPanes().overlayPane.appendChild(this.distLabel);
    }

    // If the player starts in a forbidden zone (this may happen if we shift boundaries), display it.
    this.showForbiddenStartRegion();
};

//------------------------------------------------------------------------------
// When dragging the new target, limit the distance and update the line
ce4.leaflet.target.TargetDisplay.prototype.onDrag = function onDrag(e)
{
    this.clipLine();

    // Update label position and text
    L.DomUtil.setPosition(this.distLabel, this.leafletMap.latLngToLayerPoint(this.marker.getLatLng()));
    this.distLabel.innerHTML = '<span>' + Math.round(this.dist) + 'm, ' + Math.round(this.direction) + '&deg;</span>';

    // Update the tutorial text as you drag, etc.
    if (this.onDragCallback) this.onDragCallback();
};

//------------------------------------------------------------------------------
// When we end dragging, open the wizard
ce4.leaflet.target.TargetDisplay.prototype.onDragEnd = function onDragEnd(e)
{
    setTimeout($.proxy(function(){this.marker.setIcon(ce4.leaflet.assets.icons.TARGET_POINT);}, this),10); // FUTU: setIcon during the onDragEnd call triggers a 'click' event in Leaflet as of 0.6.x, this is a workaround
    this.clipLine();
    this.extraSolarMap.showClipRegion(null);  // Reset hidden clipping region.
    this.extraSolarMap.showForbiddenRegion(null);  // If necessary, hide the forbidden region.
    this.marker.setLatLng(this.getLocation());
    this.distLabel.innerHTML = '';
    this.leafletMap.getPanes().overlayPane.removeChild(this.distLabel);

    if (this.rover.canCreateTarget())
    {
        this.rover.wizard = new ce4.leaflet.controls.DirectionWizard(this.extraSolarMap, this.marker, this, this.rover);

        // Tutorial advance for step 4, and set hook for step 5
        ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT01, "tutorial01-step04",  {control: this.rover.wizard});
    }
    else
    {
        this.popup = L.popup({className: 'standard-leaflet-popup', offset: new L.Point(0,-40)});
        this.popup.setLatLng(this.marker.getLatLng());
        this.popup.setContent("<p>Sorry. You can only schedule "+this.rover.getMaxTargets()+" photos ahead. Please try later.</p>");
        this.popup.openOn(this.leafletMap);

        this.leafletMap.addEventListener('popupclose', this.onCancelCreate, this);
    }
};

//------------------------------------------------------------------------------
// Remove old rover drag icon and initialize a new one
ce4.leaflet.target.TargetDisplay.prototype.onCancelCreate = function onCancelCreate()
{
    this.remove();
    this.extraSolarMap.initDragMarker(this.rover);
};

//------------------------------------------------------------------------------
ce4.leaflet.target.TargetDisplay.prototype.getPrevLocation = function()
{
    return this.path.getLatLngs()[0];
};

//------------------------------------------------------------------------------
// Set location for target marker line anchor
ce4.leaflet.target.TargetDisplay.prototype.setPrevLocation = function(latlng_or_event)
{
    this.path.spliceLatLngs(0, 1, latlng_or_event.latLng || latlng_or_event);
};

//------------------------------------------------------------------------------
// Removes the target from the map entirely.
ce4.leaflet.target.TargetDisplay.prototype.remove = function(save_if_wizard)
{
    // Don't remove if the wizard is open and we want to save if wizard
    if(!save_if_wizard || !this.rover.wizard) // FUTU: Make sure target count is still the same, in case they created a target with another client
    {
        // Remove map listeners
        this.leafletMap.removeEventListener('popupclose', this.onCancelCreate, this);

        // Close the out of energy popup
        if(this.popup)          this.popup._close();

        // Close the wizard
        //if(this.rover.wizard)   this.rover.wizard.dismiss();

        // Remove map elements
        if (this.marker)        this.leafletMap.removeLayer(this.marker);
        if (this.path)          this.leafletMap.removeLayer(this.path);
        if (this.pathFromPrev)  this.leafletMap.removeLayer(this.pathFromPrev);
        if (this.limitCircle)   this.leafletMap.removeLayer(this.limitCircle);

        // Remove marker listeners
        this.marker.removeEventListener('dragstart', this.onDragStart, this);
        this.marker.removeEventListener('drag', this.onDrag, this);
        this.marker.removeEventListener('dragend', this.onDragEnd, this);
    }
};

//------------------------------------------------------------------------------
// Show the photo angle
ce4.leaflet.target.TargetDisplay.prototype.showPhotoAngle = function()
{
    if(!this.markerPhotoAngle) this.markerPhotoAngle = new L.Marker(this.getLocation(), $.extend({iconAngle: this.target.yaw/Math.PI*180}, ce4.leaflet.assets.styles.TARGET_ANGLE));
    this.leafletMap.addLayer(this.markerPhotoAngle);

    this.leafletMap.addEventListener('popupclose', this.hidePhotoAngle, this);
};

//------------------------------------------------------------------------------
// Hide the photo angle
ce4.leaflet.target.TargetDisplay.prototype.hidePhotoAngle = function()
{
    this.leafletMap.removeEventListener('popupclose', this.hidePhotoAngle, this);
    this.leafletMap.removeLayer(this.markerPhotoAngle);
};
