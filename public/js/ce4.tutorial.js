// Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.tutorial contains the Tutorial model
goog.provide("ce4.tutorial.Tutorial");
goog.provide("ce4.tutorial.ids");
goog.require("ce4.util");
goog.require("ce4.ui");

// Tutorial ID strings
ce4.tutorial.ids.TUT01        = "PRO_TUT_01";         // Simulator: Controls Wizard Tutorial
ce4.tutorial.ids.TUT01_STEP09 = "PRO_TUT_01_STEP_09"; // Simulator: Checkpoint for TUT01 STEP09
ce4.tutorial.ids.TUT02        = "PRO_TUT_02";         // Mission 1: Controls Tutorial
ce4.tutorial.ids.TUT03        = "PRO_TUT_03";         // Simulator: Photo Tagging Tutorial (Home, Gallery)
ce4.tutorial.ids.TUT04        = "PRO_TUT_04";         // Simulator: Photo Tagging Tutorial (Photo)

// Tutorial Dependencies
// TODO?: Add support for multiple dependencies if we ever need them
ce4.tutorial.deps = [];
ce4.tutorial.deps[ce4.tutorial.ids.TUT02] = ce4.tutorial.ids.TUT01;
ce4.tutorial.deps[ce4.tutorial.ids.TUT04] = ce4.tutorial.ids.TUT01_STEP09;

// Default Constants
if(!ce4.ui.is_mobile)
{
    ce4.tutorial.defaults = { DIALOG_WIDTH_NARROW:    350,
                              DIALOG_WIDTH_STANDARD:  550,
                              DIALOG_WIDTH_WIDE:      750,
                              DIALOG_OFFSET:          'left+25 top+80'};
}
else
{
    ce4.tutorial.defaults = { DIALOG_WIDTH_NARROW:    '50%',
                              DIALOG_WIDTH_STANDARD:  '70%',
                              DIALOG_WIDTH_WIDE:      '88%',
                              DIALOG_OFFSET:          'left+5% top+70'};
}

//------------------------------------------------------------------------------
// Constructor
ce4.tutorial.Tutorial = function (options)
{
    // Prepare the dialog ui element
    this.dialogDiv = $('<div></div>');
    this.dialogDiv.dialog({
            width: ce4.tutorial.defaults.DIALOG_WIDTH,
            autoOpen: false,
                        dialogClass: 'tutorial-theme',
            modal: false,
            closeOnEscape: false,
            draggable: false,
            resizable: false,
            open: function(event, ui) { $(".ui-dialog-titlebar-close").hide(); }})
        .dialogExtend({
      closable : false,
      maximizable : false,
      minimizable : false,
      collapsable : false,
      icons : {  restore : "ui-icon-circle-arrow-s" },
      beforeMinimize : $.proxy(function (){this.dialogDiv.parent().toggleClass('tutorial-theme-minimized');}, this),
      beforeRestore  : $.proxy(function (){this.dialogDiv.parent().toggleClass('tutorial-theme-minimized');}, this)
    });
    this.dialogDiv.dialog('widget').css({'max-height': 800, 'overflow-y': 'auto'});

    // Option defaults
    this.user             = options && options.user || ce4.gamestate.user; // FUTU: remove the || ce4.gamestate.user
    this.offsetDiv        = options && options.offsetDiv || '#xri-wrapper';
    this.createKey        = options && options.createKey || function(){};
    this.advanceCallbacks = options && options.advanceCallbacks || {};

    // Default last position
    this.lastPositionOffset = ce4.tutorial.defaults.DIALOG_OFFSET;

    // Whether or not the abort function will interrupt the tutorial
    this.abortAllowed = true; // USE CAREFULLY

    // Client side tracking for completed tutorials in case server hasn't updated yet
    this.justCompleted = [];
};

//------------------------------------------------------------------------------
// Adjust settings for the dialog
ce4.tutorial.Tutorial.prototype.onWindowResize = function(params)
{
    params.data.viewer.dialogSet({offset: params.data.viewer.lastPositionOffset});
};


//------------------------------------------------------------------------------
// Adjust settings for the dialog
ce4.tutorial.Tutorial.prototype.dialogSet = function(params)
{
    if(params.html !== undefined)   this.dialogDiv.html(params.html);
    if(params.width !== undefined)  this.dialogDiv.dialog('option', 'modal', params.modal);
    if(params.width !== undefined)  this.dialogDiv.dialog('option', 'width', params.width);
    if(params.title !== undefined)  this.dialogDiv.dialog('option', 'title', params.title);
    if(params.offset !== undefined) this.lastPositionOffset = params.offset;

    this.dialogDiv.dialog("option", "position", {my: 'left top', at: this.lastPositionOffset, of: $(this.offsetDiv), collision: 'none'});
};


//------------------------------------------------------------------------------
// Reset all settings for the dialog to passed in values, or defaults
ce4.tutorial.Tutorial.prototype.dialogReset = function(params)
{
    this.dialogSet({
            html: params.html || "",
            modal: params.modal || false,
            width: params.width || ce4.tutorial.defaults.DIALOG_WIDTH_NARROW,
            title: params.title, // No default title
            offset: params.offset || ce4.tutorial.defaults.DIALOG_OFFSET});
};


//------------------------------------------------------------------------------
// Opens the dialog
ce4.tutorial.Tutorial.prototype.dialogOpen = function(params)
{
    this.dialogDiv.dialog('open');
};


//------------------------------------------------------------------------------
// Closes the dialog
ce4.tutorial.Tutorial.prototype.dialogClose = function(params)
{
    this.dialogDiv.dialog('close');
};


//------------------------------------------------------------------------------
// Minimize the dialog
ce4.tutorial.Tutorial.prototype.dialogMinimize = function(params)
{
    this.dialogDiv.dialogExtend('minimize');
};


//------------------------------------------------------------------------------
// Restore the dialog
ce4.tutorial.Tutorial.prototype.dialogRestore = function(params)
{
    if(this.dialogDiv.dialogExtend('state') == "minimized") this.dialogDiv.dialogExtend('restore');
};


//------------------------------------------------------------------------------
// Begin a tutorial
ce4.tutorial.Tutorial.prototype.minimize = function()
{
    this.dialogMinimize();
};


//------------------------------------------------------------------------------
// Begin a tutorial
ce4.tutorial.Tutorial.prototype.begin = function(id, params)
{
    // Abort the tutorial if already complete, doesn't exist, dependencies not met, or a tutorial is currently active
    if(this.is_completed(id) || ce4.tutorial.begin[id] === undefined || (ce4.tutorial.deps[id] !== undefined && !this.is_completed(ce4.tutorial.deps[id])) || this.activeTutorial !== undefined)
    {
        return false;
    }
    else {

        // Set active tutorial
        this.activeTutorial = id;

        // cache parameters
        this.params = params;

        // Activate the tutorial
        ce4.tutorial.begin[id].call(this, this.params);

        // Handle window resizing
        $(window).bind('resize', {viewer: this}, this.onWindowResize);

        // The tutorial was activated
        return true;
    }
};

//------------------------------------------------------------------------------
// Advance a tutorial to a specified step
// Note: this can be called at any time, even if tutorials are not active
ce4.tutorial.Tutorial.prototype.advance = function(id, step, sparams)
{
    // Make sure it is the active tutorial
    if(this.is_active(id))
    {
        // If the tutorial advance function doesn't exist or it fails, just toggle the step
        if(ce4.tutorial.advance[id] === undefined || !ce4.tutorial.advance[id].call(this, step, sparams, this.params))
        {
            this.dialogRestore();
            ce4.util.toggleView('tut', step, 2);
        }

        // Custom callbacks
        if(this.advanceCallbacks[id] && this.advanceCallbacks[id][step]) this.advanceCallbacks[id][step].call(this);

        return true;
    }
    else
    {
        return false;
    }
};


//------------------------------------------------------------------------------
// Abort a tutorial, should completely cancel it and clean up related code
ce4.tutorial.Tutorial.prototype.abort = function(id)
{
    // Abort active tutorial if the id matches or is not defined
    if(this.abortAllowed && (this.is_active(id) || (this.activeTutorial !== undefined && id === undefined )))
    {
        if(ce4.tutorial.abort[this.activeTutorial] !== undefined)
        {
           ce4.tutorial.abort[this.activeTutorial].call(this, this.params);
        }
        if(this.activeTutorial) delete this.activeTutorial;
        if(this.params)         delete this.params;
        if(this.scheduledStep)  delete this.scheduledStep;

        $(window).unbind('resize', this.onWindowResize);

        return true;
    }
    else
    {
       return false;
    }
};


//------------------------------------------------------------------------------
// Checkes if a tutorial is completed
ce4.tutorial.Tutorial.prototype.is_completed = function(id)
{
    return ce4.gamestate.user.progress.contains(id) || this.justCompleted[id];
};


//------------------------------------------------------------------------------
// Determine if the tutorial is active
ce4.tutorial.Tutorial.prototype.is_active = function(id)
{
    return (id !== undefined && this.activeTutorial !== undefined && this.activeTutorial === id);
};


//------------------------------------------------------------------------------
// Marks a tutorial as completed
ce4.tutorial.Tutorial.prototype.complete = function(id)
{
    if (!this.is_completed(id)) {
        this.createKey(id);
        this.justCompleted[id] = true;
    }
};


//------------------------------------------------------------------------------
// Creates a button for advancing the tutorial
// all parameters MUST BE STRINGS, including params
ce4.tutorial.Tutorial.prototype.advanceButton = function(id, step, text, params)
{
    return "<table width=100%><tr><td width=50% style=\"text-align:right;\">\
                <button class=\"gradient-button gradient-button-tutorial\" onclick=\"ce4.gamestate.user.tutorial.advance('"+id+"', '"+step+"', '"+(params || {})+"');\">"+(text || "Continue")+"</button>\
             </td></tr></table>";
};


//------------------------------------------------------------------------------
// Creates a button for minimizing the tutorial
// all parameters MUST BE STRINGS, including params
ce4.tutorial.Tutorial.prototype.minimizeButton = function(id, step, text, params)
{
    if(ce4.ui.is_mobile)
    {
        return "<table width=100%><tr><td width=50% style=\"text-align:right;\">\
                    <button class=\"gradient-button gradient-button-tutorial\" onclick=\"ce4.gamestate.user.tutorial.minimize();\">"+(text || "Okay")+"</button>\
                 </td></tr></table>";
    }
    else
    {
        return "";
    }
};

// ==================== Tutorial Helper Funtions ====================
ce4.tutorial.abort = [];    // aborts tutorial when it becomes inactive
ce4.tutorial.begin = [];    // initializes tutorial when it becomes active
ce4.tutorial.advance = [];  // advances tutorial a step, return true for custom advance or false for auto advance


// ==================== Tutorial 01 Helper Funtions ====================

//------------------------------------------------------------------------------
// Tutorial 01 - Abort
ce4.tutorial.abort[ce4.tutorial.ids.TUT01] = function (params)
{
    // Clean up map markers, position, and settings
    params.map.leafletMap.options.minZoom = params.optionsMinZoom;
    params.map.leafletMap.dragging.enable();
    params.map.leafletMap.doubleClickZoom.enable();
    params.map.leafletMap.scrollWheelZoom.enable();
    params.map.leafletMap.zoomControl.addTo(params.map.leafletMap);
    params.map.tasksShowControl.addTo(params.map.leafletMap);
    params.map.roverControl.addTo(params.map.leafletMap);
    params.map.fullscreenEnter.addTo(params.map.leafletMap);
    if(params.roverMarker !== undefined) params.map.leafletMap.removeLayer(params.roverMarker);
    if(params.destinationMarker !== undefined) params.map.leafletMap.removeLayer(params.destinationMarker);
    if(params.targetCircle !== undefined) params.map.leafletMap.removeLayer(params.targetCircle);
    if(params.path !== undefined) params.map.leafletMap.removeLayer(params.path);
    params.map.leafletMap.setView(params.startCenter, 20);
    params.map.leafletMap.setMaxBounds(params.map.bounds);

    params.map.displayRegion(params.objectiveRegion);
    ce4.gamestate.user.regions.remove(params.objectiveRegion.region_id);
    if(params.map.markers.regions["TUT01_OBJECTIVE"]) delete params.map.markers.regions["TUT01_OBJECTIVE"];

    if(params.tutorialRover.wizard !== undefined) params.tutorialRover.wizard.dismiss();
    if(params.map.markers.drag_markers[params.tutorialRover.rover_id] !== undefined)
    {
        params.map.markers.drag_markers[params.tutorialRover.rover_id].remove();
        delete params.map.markers.drag_markers[params.tutorialRover.rover_id];
    }

    // Close the tutorial dialog
    this.dialogClose();
};


//------------------------------------------------------------------------------
// Tutorial 01 - Begin
ce4.tutorial.begin[ce4.tutorial.ids.TUT01] = function (params)
{
    // Exit fullscreen if necessary
    // TODO: Allow fullscreen for tutorial?
    if(ce4.ui.is_fullscreen) ce4.ui.leaflet.exitFullscreen();

    // Initialize map position and settings for tutorial
    params.optionsMinZoom = params.map.leafletMap.options.minZoom;
    params.map.leafletMap.options.minZoom = ce4.leaflet.MAX_ZOOM - 1;
    params.rover_coords =     [-0.0006075203418584118, -179.99932676553726];
    params.objective_coords = [-0.0007858872413378918, -179.9990639090538];
    params.view_coords = [-0.00067, -179.99933];
    params.createdTutorialTargets = 0;
    if(!ce4.ui.is_mobile) params.map.leafletMap.dragging.disable();
    params.map.leafletMap.doubleClickZoom.disable();
    params.map.leafletMap.scrollWheelZoom.disable();
    params.map.leafletMap.zoomControl.removeFrom(params.map.leafletMap);
    params.map.fullscreenEnter.removeFrom(params.map.leafletMap);
    params.map.roverControl.removeFrom(params.map.leafletMap);
    params.map.tasksShowControl.removeFrom(params.map.leafletMap);
    params.startBounds = params.map.leafletMap.getBounds();
    params.startCenter = params.map.leafletMap.getCenter();
    params.map.leafletMap.zoomIn();
    params.map.leafletMap.setView(params.view_coords, ce4.ui.is_mobile ? (ce4.leaflet.MAX_ZOOM - 1) : ce4.leaflet.MAX_ZOOM);
    params.map.leafletMap.setMaxBounds([[-0.00000, -180.00000], [-0.00137, -179.99863]]);


    // Create objective point
    params.objectiveRegion = {
        visible:      true,
        marker_icon:  null,
        region_icon:  null,
        region_id:    "TUT01_OBJECTIVE",
        restrict:     ce4.region.RESTRICT_OUTSIDE,
        title:        "Rover Objective",
        description:  "Direct your rover closer and schedule a photo of the objective.",
        style:        ce4.region.styles.WAYPOINT,
        shape:        ce4.region.SHAPE_POINT,
        verts:        [],
        center:       params.objective_coords,
        radius:       4
    }
    params.map.displayRegion(params.objectiveRegion);
    ce4.gamestate.user.regions.add(params.objectiveRegion);

    // Create rover Marker
    params.roverMarker = new L.Marker(params.rover_coords, {
        icon: ce4.leaflet.assets.icons.PLAYER_ROVER,
        title:"Training Rover",
        draggable: false,
        zIndexOffset: 0
    });
    params.map.leafletMap.addLayer(params.roverMarker);

    // Simulated tutorial rover data
    params.tutorialRover = {
            rover_id: 99999,
            active: true,
            max_target_seconds: 1 * 60 * 60,
            min_target_seconds: 4 * 60 * 60,
            max_travel_distance: 50.0,
            getCoordsProjected: function () {return params.rover_coords;},
            canCreateTarget: function () {return (params.createdTutorialTargets < 2);},
            createTarget: function() {
                params.createdTutorialTargets += 1;
                if (params.createdTutorialTargets == 1) {
                    ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step07',  {});
                }
                else {
                    ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step08',  {});
                }
            },
            getLastTarget: function() {return {
                    processed: true,
                    arrival_time_ms: function() {return ce4.util.utc_now_in_ms();},
                    has_arrived: function() { return true; },
                    getCoords: function() {return params.createdTutorialTargets > 0 ? params.destination_coords : params.rover_coords;}};}}
    params.tutorialRover.getLastProcessedTarget = params.tutorialRover.getLastTarget;

    // Create the drag marker for the tutorial rover
    params.map.initDragMarker(params.tutorialRover);

    // Tutorial Dialog HTML
    var tutorialHTML = "<div class=\"tutorial-text\">"
    // Step 1
    + "   <div id=\"tutorial01-step01\" style=\"display:none;\">\
            <p>Hello, and welcome to Extrasolar!</p>\
            <p>This short training simulator will give you an introduction to the interface used to conduct research on Epsilon Eridani <em>e</em>, which we usually refer to internally as Epsilon Prime.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT01, 'tutorial01-step02') + "\
          </div>"
    // Step 2
    + "   <div id=\"tutorial01-step02\" style=\"display:none;\">\
            <p>Welcome to the rover simulator.</p>\
            <p>Let's begin by moving your <b>rover</b> <img src=\""+ce4.leaflet.assets.icons.PLAYER_ROVER.options.iconUrl+"\"> towards the <b>marker</b> <img src=\""+ce4.leaflet.assets.icons.WAYPOINT.options.iconUrl+"\"> to schedule a photo at the location.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT01, 'tutorial01-step03') + "\
          </div>"
    // Step 3 - DW Destination
    + "   <div id=\"tutorial01-step03\" style=\"display:none;\">\
            <p><b>1. Set a destination for your rover.</b></p>\
            <p>Drag the <b>control arrows</b> <img src=\""+ce4.leaflet.assets.styles.DRAG_CONTROL.icon.options.iconUrl+"\"> towards the <b>marker</b> <img src=\""+ce4.leaflet.assets.icons.WAYPOINT.options.iconUrl+"\"> on the map.</p>\
            <p>Then release to set the destination.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 4 - DW Destination - fail
    + "   <div id=\"tutorial01-step04-fail\" style=\"display:none;\">\
            <p><b>1. Set a destination for your rover.</b></p>\
            <p>Too far away! Try placing the destination within the <b>circle</b> <img src=\""+ce4.util.url_static("/img/circle_tutorial.png")+"\"> close enough to the <b>marker</b> <img src=\""+ce4.leaflet.assets.icons.WAYPOINT.options.iconUrl+"\"> to get a clear photo.</p>\
            " + this.minimizeButton() + "\
         </div>"
    // Step 4 - DW Direction
    + "   <div id=\"tutorial01-step04\" style=\"display:none;\">\
            <p><b>2. Set the camera direction</b></p>\
            <p>Drag the <b>direction arrow</b> <img src=\""+ce4.util.url_static("/img/dw/direction_pointer.png")+"\"> to aim the rover camera at the <b>marker</b> <img src=\""+ce4.leaflet.assets.icons.WAYPOINT.options.iconUrl+"\">.</p>\
            <p>Press [Next] to continue.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 5 - DW Direction - fail
    + "   <div id=\"tutorial01-step05-fail\" style=\"display:none;\">\
            <p><b>2. Set the camera direction</b></p>\
            <p>Not quite! Set the direction so that the <b>marker</b> <img src=\""+ce4.leaflet.assets.icons.WAYPOINT.options.iconUrl+"\"> falls within the <b>field-of-view wedge</b> <img src=\""+ce4.util.url_static("/static/img/tutorial/groundIndicator.png")+"\"> of the camera.</p>\
            <p>Press [Next] to continue.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 5 - DW Delay
    + "   <div id=\"tutorial01-step05\" style=\"display:none;\">\
            <p><b>3. Choose time of day</b></p>\
            <p>Drag the <b>time indicator</b> <img src=\""+ce4.util.url_static("/img/simulator/target_time_selector.png")+"\"> to set the time of day you want your photo taken.</p>\
            <p>Press [Next] to continue.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 6 - DW Options
    + "   <div id=\"tutorial01-step06\" style=\"display:none;\">\
            <p><b>4. Options</b></p>\
            <p>Some rover models have additional capabilities which can be selected here.</p>\
            <p> Press [Done] to continue.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 7
    + "   <div id=\"tutorial01-step07\" style=\"display:none;\">\
            <p><b>5. Done!</b></p>\
            <p>You have set a <b>destination</b> <img src=\""+ce4.leaflet.assets.styles.TARGET_PENDING.icon.options.iconUrl+"\">.</p>\
            <p>You may drag the <b>control arrows</b> <img src=\""+ce4.leaflet.assets.styles.DRAG_CONTROL.icon.options.iconUrl+"\"> to queue a second destination.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT01, 'tutorial01-step08') + "\
          </div>"
    // Step 8
    + "   <div id=\"tutorial01-step08\" style=\"display:none;\">\
            <p>Your <b>rover</b> <img src=\""+ce4.leaflet.assets.icons.PLAYER_ROVER.options.iconUrl+"\"> has now moved to the new destination and sent back a photo.</p>\
            <p>For the purposes of this simulation we have shortened the time this would normally take.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT01, 'tutorial01-step09') + "\
          </div>"
    // Step 9
    + "   <div id=\"tutorial01-step09\" style=\"display:none;\">\
            <p><b>New photo!</b></p>\
            <p>The photo from the new destination has been added to your gallery.</p>\
            <p>The next step is to submit the photo to the XRI science team for analysis.</p>\
            <p>Visit the Photo <a href='#gallery'>Gallery</a> to continue.</p>\
          </div>"
    + " </div>";

    // Initialize the tutorial dialog
    this.dialogOpen();
    this.dialogReset({title: 'Training: Controls', html: tutorialHTML});

    // Display tutorial step 2 (Step 1 has been cut)
    if(this.is_completed(ce4.tutorial.ids.TUT01_STEP09))
    {
        ce4.util.toggleView('tut', 'tutorial01-step09', 1);
    }
    else
    {
        ce4.util.toggleView('tut', 'tutorial01-step02', 1);
    }
};

//------------------------------------------------------------------------------
// Tutorial 01 - Advance
// Return true if we want to cancel the request, false otherwise.
ce4.tutorial.advance[ce4.tutorial.ids.TUT01] = function (step, sparams, params)
{
    // Step 3
    if(step === "tutorial01-step03")
    {
        // If we're creating a second target, don't modify the tutorial step.
        if (params.createdTutorialTargets >= 1)
            return true;
    }
    // Step 4
    else if (step === "tutorial01-step04")
    {
        // If we're creating a second target, don't do any checks or modify the tutorial step.
        if (params.createdTutorialTargets >= 1)
            return true;

        // Clean up the circle if we made one
        if(params.targetCircle !== undefined)
        {
            params.map.leafletMap.removeLayer(params.targetCircle);
            delete params.targetCircle;
        }

        // Cache the control if we made a new one
        if(sparams.control !== undefined) params.control = sparams.control;

        // If the destination is too far from the objective, fail the tutorial
        if(params.createdTutorialTargets==0 && params.control.marker.getLatLng().distanceTo(params.objective_coords) > 15)
        {
            // Create a circle to show them where to target
            params.targetCircle = new L.Circle(params.objective_coords, 15, ce4.leaflet.region.styles[ce4.region.styles.TUTORIAL]);
            params.map.leafletMap.addLayer(params.targetCircle);

            // Close the control popup and reset the view in case the popup moved the map
            params.control.dismiss();
            params.map.leafletMap.setView(params.view_coords, 20);

            // Display failure step
            ce4.util.toggleView('tut', step+'-fail', 2);
            this.dialogRestore();
            return true;
        }
    }
    // Step 5
    else if (step === "tutorial01-step05")
    {
        // If we're creating a second target, don't do any checks or modify the tutorial step.
        if (params.createdTutorialTargets >= 1)
            return true;

        // Coords to for the objective and the destination
        var target = params.objective_coords;
        var control = params.control.marker.getLatLng();

        // Camera angle is directed toward objective
        if(ce4.util.angle_closeness(Math.atan2(target[1] - control.lng, target[0] - control.lat), params.control.tdisplay.new_target_fields.yaw, 0.70))
        {
            // Cache destination
            params.destination_coords = [control.lat, control.lng];
        }
        // Camera not directed at objective
        else
        {
            // Fail tutorial, and go back a step on control
            ce4.util.toggleView('direction-controls', 'direction-controls1', 2);
            ce4.util.toggleView('tut', step+'-fail', 2);
            this.dialogRestore();
            return true;
        }
    }
    // Step 6
    else if (step === "tutorial01-step06")
    {
        // If we're creating a second target, don't modify the tutorial step.
        if (params.createdTutorialTargets >= 1)
            return true;
    }
    // Step 7
    else if (step === "tutorial01-step07")
    {
        // We expect that the wizard will be in a "sending data" state.  Dismiss it now.
        if(params.tutorialRover.wizard !== undefined) {
            params.tutorialRover.wizard.dismiss();
        }

        // Add destination Marker
        params.destinationMarker = new L.Marker(params.destination_coords, {
            icon: ce4.leaflet.assets.icons.TARGET_PENDING,
            title:"Rover Waypoint",
            draggable: false,
            zIndexOffset: 0,
            iconAngle: params.control.tdisplay.new_target_fields.yaw/Math.PI*180
        });
        params.map.leafletMap.addLayer(params.destinationMarker);

        // Add path to destination Marker
        params.path = new L.Polyline([params.rover_coords, params.destination_coords], ce4.leaflet.region.styles[ce4.region.styles.PENDING_LINE]);
        params.map.leafletMap.addLayer(params.path);
    }
    // Step 8
    else if (step === "tutorial01-step08")
    {
        // If we just created a second target, the wizard will be in a "sending data" state.  Dismiss it now.
        if(params.tutorialRover.wizard !== undefined) {
            params.tutorialRover.wizard.dismiss();
        }

        // Remove the move control
        if(params.map.markers.drag_markers[params.tutorialRover.rover_id] !== undefined) params.map.markers.drag_markers[params.tutorialRover.rover_id].remove();

        // Change line color, reuse the destination marker as origin marker, and move rover
        params.path.setStyle(ce4.leaflet.region.styles[ce4.region.styles.PROCESSED_LINE]);
        params.destinationMarker.setLatLng(params.roverMarker.getLatLng());
        params.destinationMarker.setIcon(ce4.leaflet.assets.icons.TARGET_DONE);
        params.roverMarker.setLatLng(params.destination_coords);
    }
    // Step 9
    else if (step === "tutorial01-step09")
    {
        // Mark tutorial step 09 checkpoint complete
        this.complete(ce4.tutorial.ids.TUT01_STEP09);
    }

    // Auto advance to step
    return false;
};


// ==================== Tutorial 02 Helper Funtions ====================

//------------------------------------------------------------------------------
// Tutorial 02 - Abort
ce4.tutorial.abort[ce4.tutorial.ids.TUT02] = function (params)
{
    if (params.circle) ce4.ui.leaflet.leafletMap.removeLayer(params.circle);
};


//------------------------------------------------------------------------------
// Tutorial 02 - Begin
ce4.tutorial.begin[ce4.tutorial.ids.TUT02] = function (params)
{
    params.rover = ce4.gamestate.user.rovers.get(params.mission.specifics.rover_id);

    // Add popup to lander
    ce4.ui.leaflet.markers.landers[params.rover.rover_id].bindPopup("<p>This is where the lander is!</p>\
                      <p>Drag the rover over within the green circle to start taking a picture.</p>"
        , {className: 'standard-leaflet-popup', offset: new L.Point(0,-40)}).openPopup();

    params.circle = new L.Circle([params.rover.lander.lat, params.rover.lander.lng],
        params.mission.specifics.distance*ce4.geometry.getMapScaleFactor(params.rover.lander.lat),
        ce4.leaflet.region.styles[ce4.region.styles.TUTORIAL]);
    ce4.ui.leaflet.leafletMap.addLayer(params.circle);
};


//------------------------------------------------------------------------------
// Tutorial 02 - Advance
ce4.tutorial.advance[ce4.tutorial.ids.TUT02] = function (step, sparams, params)
{
    // Step 1
    if (step === "tutorial02-step01")
    {
        var rover = params.rover;
        var target_struct = sparams.target_struct;
        var mission = sparams.mission;
        var dist = ce4.geometry.distCanonical([rover.lander.lat, rover.lander.lng], [target_struct.lat, target_struct.lng]);

        // Force the player to be at a minimum distance from the lander.
        if(dist > mission.specifics.distance) {
            sparams.wizard.setMissionContent("The destination target isn't close enough to the lander to get a good picture. Click [Back] to try again.", false);
            //sparams.wizard.setNextButtonDisabled(true);
        } else {
            // TODO horrible constant derived from experimentation; need to develop an actual conversion function
            var angle = Math.atan2(rover.lander.lng - target_struct.lng, rover.lander.lat - target_struct.lat)
            if(!ce4.util.angle_closeness(angle, target_struct.yaw, 0.70)) {
                sparams.wizard.setMissionContent("Click and drag the direction indicator so that the picture looks at the lander.", false);
                //sparams.wizard.setNextButtonDisabled(true);
            } else {
                sparams.wizard.setMissionContent("Great!  You're set to take a picture of the lander! Now click [Next].", true);
                //sparams.wizard.setNextButtonDisabled(false);
            }
        }
    }
    // Step 2
    else if (step === "tutorial02-step02")
    {
        sparams.wizard.setMissionContent("Use this to set the time at which the\
            picture will be taken.  The earliest possible time has already\
            been selected for you.  Then click [Done]", true);
    }
    // Step 3
    else if (step === "tutorial02-step03")
    {
        // Mark tutorial complete
        this.complete(ce4.tutorial.ids.TUT02);
        this.abort(ce4.tutorial.ids.TUT02);
    }

    return true;
};


// ==================== Tutorial 03 Helper Funtions ====================

//------------------------------------------------------------------------------
// Tutorial 03 - Abort
ce4.tutorial.abort[ce4.tutorial.ids.TUT03] = function (params)
{
    if(params.page == 'home')
    {
        // Remove the tutorial dialog
       this.dialogClose();
    }
};


//------------------------------------------------------------------------------
// Tutorial 03 - Begin
ce4.tutorial.begin[ce4.tutorial.ids.TUT03] = function (params)
{
    // Don't show any images until TUT01_STEP09 is done
    if(this.is_completed(ce4.tutorial.ids.TUT01_STEP09))
    {
        // Create a dummy thumbnail for the simulator photo.
        var thumb = xri.ui.makeThumbnail(ce4.util.url_static("/img/scenes/simulator_photo.jpg"), {
                        link: "#picture,simulator",
                        lazy: false,
                        news: true,
                        sound: false,
                        infrared: false,
                        tags: 0,
                        desc: "Simulator example image"});

        if(params.page == 'home')
        {
            thumb.addClass("bigger");

            // Tutorial Dialog HTML
            var tutorialHTML = ""
            // Step 1
            + "   <div id=\"tutorial03-step01\" style=\"display:none;\">\
                    <p>The Home tab is an overview of your work with the Extrasolar Program. This is where you will receive messages, track the tasks assigned to you, and more.</p>\
                    " + this.advanceButton(ce4.tutorial.ids.TUT03, 'tutorial03-step02') + "\
                  </div>"
            // Step 2
            + "   <div id=\"tutorial03-step02\" style=\"display:none;\">\
                    <p><img src=\""+ce4.util.url_static("/img/left_arrow_filled.png")+"\"> Click the new photo in the <b>Newest Photos</b> section to continue.</p>\
                  </div>"
                  +"";

            // Initialize the tutorial dialog
            this.dialogOpen();
            this.dialogReset({title: 'Training: Photos', html: tutorialHTML, offset: 'left+110 top+200', width: ce4.tutorial.defaults.DIALOG_WIDTH_STANDARD});

            // Display tutorial step 1
            ce4.util.toggleView('tut', 'tutorial03-step01', 1);
        }
        $("#gallery-thumbnails").append(thumb);
    }
};


//------------------------------------------------------------------------------
// Tutorial 03 - Advance
ce4.tutorial.advance[ce4.tutorial.ids.TUT03] = function (step, sparams, params)
{

    // Step 2
    if (step === "tutorial03-step02")
    {
        this.dialogSet({offset: 'left+400 top+450', width: ce4.tutorial.defaults.DIALOG_WIDTH_NARROW});
    }

    // Auto advance to step
    return false;
};


// ==================== Tutorial 04 Helper Funtions ====================

//------------------------------------------------------------------------------
// Tutorial 04 - Abort
ce4.tutorial.abort[ce4.tutorial.ids.TUT04] = function (params)
{
    // Remove the tutorial dialog
    this.dialogClose();

    // Remove the override functions
    $('#id-species-submit').unbind("click", params.submit_override);
    $('#id-add-tag').unbind("click", params.add_override);
    if(params.page == 'picture')
    {
        params.bocks.off('cancelSelection', params.cancelSelectionCallback);
    }
    else if(params.page == 'mobile_picture')
    {
        params.bocks.cbCancelSelection = undefined;
    }
};


//------------------------------------------------------------------------------
// Tutorial 04 - Begin
ce4.tutorial.begin[ce4.tutorial.ids.TUT04] = function (params)
{
    // Callback to decrement selection box count
    params.cancelSelectionCallback = $.proxy(function () {this.params.countStep04 -= 1;}, this);

    if(params.page == 'picture')
    {
        // Hide the social media section.
        $('#id-picture-social').hide();

        // Hide the fullscreen button
        $('.fullscreen-control').hide();

        // Add callback (bocks)
        params.bocks.on('cancelSelection', params.cancelSelectionCallback);
    }
    else if(params.page == 'mobile_picture')
    {
        // Add callback (boxTagger)
        params.bocks.cbCancelSelection = params.cancelSelectionCallback;
    }

    // ADD TAG button override function
    params.add_override = $.proxy( function(event)
    {
                // Maximum of 3 tags
                if(params.countStep04 && params.countStep04 > 2)
                {
                        // Stop the normal add tag function from being called
                        event.stopImmediatePropagation();
                }
                else
                {
                        // Advance the tutorial to the next step
                        ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT04, 'tutorial04-step04',  {});
                }
    }, this);
    $('#id-add-tag').click(params.add_override);

    // SUBMIT button override function
    params.submit_override = $.proxy( function(event)
    {
        // Stop the normal submit ID function from being called
        event.stopImmediatePropagation();

       // Advance the tutorial to the next step if we have 3 tags
                if(params.countStep04 >= 3)
                {
                        $('#species-tags').hide();

                        $("#id-species-identified #species-ids").append(ce4.ui.create_catalog_item($.extend({}, ce4.ui.DISCOVERY_NONE, {name: "Creature GN893"}), {tabid: '1'}));
                        $("#id-species-identified #species-ids").append(ce4.ui.create_catalog_item($.extend({}, ce4.ui.DISCOVERY_NONE, {name: "XRI A1 Rover"}), {tabid: '2'}));
                        $("#id-species-identified #species-ids").append(ce4.ui.create_catalog_item($.extend({}, ce4.ui.DISCOVERY_NONE, {name: "Plant GN746"}), {tabid: '3'}));

                        // Disable the submit button.
                        $('#id-species-submit').attr('disabled', true);

                        // advance tutorial
                        ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT04, 'tutorial04-step09',  {})
                }
    }, this);
    $('#id-species-submit').click(params.submit_override);

    // Tutorial Dialog HTML
    var tutorialHTML = ""
    // Step 1
    + "   <div id=\"tutorial04-step01\" style=\"display:none;\">\
            <p>To submit a photo for analysis you must first tag the items of relevant interest in the photo.</p><p>The high-resolution, full-spectrum data from your selected regions will be sent to our science team for analysis.</p>\
            <p>(<a href=\"#\" onclick=\"ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT04, 'tutorial04-step02', {}); return false;\"> Learn more</a>)</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT04, 'tutorial04-step03') + "\
          </div>"
    // Step 2
    + "   <div id=\"tutorial04-step02\" style=\"display:none;\">\
            <p><b>How Image Data is Processed</b></p>\
            <p>Because sending data across the trillions of miles between Earth and Epsilon Prime is both costly and difficult, your rover only transmits the visible spectrum data and keeps a copy of the full-spectrum data in its internal memory.  It is the job of the rover driver to identify the objects of highest interest in each photo.  The system will then download the full-spectrum data for those parts of the photo and send them to XRI's servers for automatic analysis (or, in the case of a new discovery, in-depth analysis by the science team).</p>\
            <p>If you wish to get unlimited access to features like 360&deg; panoramas and infrared photographs, you may upgrade your account to obtain priority access to our limited bandwidth.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT04, 'tutorial04-step03') + "\
          </div>"
    // Step 3
    + "   <div id=\"tutorial04-step03\" style=\"display:none;\">\
            <p>Alert the science team about potential discoveries by tagging them in the photo (<a href=\"#\" onclick=\"ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT04, 'tutorial04-step02', {}); return false;\">learn more</a>).</p>\
            <p>Press the [Add Tag] button to continue.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 4
    + "   <div id=\"tutorial04-step04\" style=\"display:none;\">\
            <p>Move the tagging rectangle over something interesting in your photo.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 4 - more needed
    + "   <div id=\"tutorial04-step04-more\" style=\"display:none;\">\
            <p>Continue adding tags until you’ve tagged three different items of interest.</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 4 - done
    + "   <div id=\"tutorial04-step04-done\" style=\"display:none;\">\
            <p>You can add up to 3 tags per photo, so we encourage you to choose your regions carefully.  If you create fewer than 3 tags, you can always come back later to add more.</p>\
            <p>(<a href=\"#\" onclick=\"ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT04, 'tutorial04-step07', {}); return false;\"> Learn more</a>)</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT04, 'tutorial04-step08') + "\
          </div>"
    // Step 7
    + "   <div id=\"tutorial04-step07\" style=\"display:none;\">\
            <p>We limit each photo to 3 tags due to the high bandwidth cost of transferring high-resolution, full-spectrum data for each region.</p>\
            <p>We encourage you to choose your regions carefully. If you create fewer than 3 tags, you can always come back later to add more.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT04, 'tutorial04-step08') + "\
          </div>"
    // Step 8
    + "   <div id=\"tutorial04-step08\" style=\"display:none;\">\
            <p>4. Once all targets are tagged, click the [Submit] button. (<a href=\"#\" onclick=\"ce4.gamestate.user.tutorial.advance(ce4.tutorial.ids.TUT04, 'tutorial04-step07', {}); return false;\">learn more</a>)</p>\
            " + this.minimizeButton() + "\
          </div>"
    // Step 9
    + "   <div id=\"tutorial04-step09\" style=\"display:none;\">\
            <p>The complete, full resolution data for the areas you've tagged will now be downloaded from the rover and sent to the XRI science team.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT04, 'tutorial04-step10') + "\
          </div>"
    // Step 10
    + "   <div id=\"tutorial04-step10\" style=\"display:none;\">\
            <p><b>Training Complete!</b></p>\
            <p>You will now be connected to the rover assigned to you on the surface of Epsilon Prime.</p>\
            <p>Please see the Messages or Tasks list for your first assignment.</p>\
            " + this.advanceButton(ce4.tutorial.ids.TUT04, 'tutorial04-step11', 'Close') + "\
          </div>"

          +"";

    // Initialize the tutorial dialog
    this.dialogOpen();
    this.dialogReset($.extend({title: 'Training: Photos', html: tutorialHTML}, ce4.ui.is_mobile ? {} : {offset: 'left+150 top+80'}));

   // Display tutorial step 3 (step 1 and 2 cut)
   ce4.util.toggleView('tut', 'tutorial04-step03', 1);
};


//------------------------------------------------------------------------------
// Tutorial 04 - Advance
ce4.tutorial.advance[ce4.tutorial.ids.TUT04] = function (step, sparams, params)
{
    // Cancel any scheduled steps
    if(this.scheduledStep) delete this.scheduledStep;

    // Step 2, Step 7
    if (step === "tutorial04-step02" || step === "tutorial04-step07")
    {
        this.dialogSet({width: ce4.tutorial.defaults.DIALOG_WIDTH_WIDE});
    }
    // Step 3, Step 8
    else if (step === "tutorial04-step03" || step === "tutorial04-step08")
    {
        this.dialogSet({width: ce4.tutorial.defaults.DIALOG_WIDTH_NARROW});
    }
    // Step 4
    else if (step === "tutorial04-step04")
    {
        // Keep track of how many region boxes they've added
        params.countStep04 = params.countStep04 || 0;
        params.countStep04 += 1;

        if(params.countStep04 === 1)
        {
            // Give them a few seconds to set the region box(es) then advance tutorial
            setTimeout($.proxy(function() { if(this.scheduledStep === step+'-more') ce4.util.toggleView('tut', step+'-more', 2); this.dialogRestore();}, this), 8000);
            this.scheduledStep = step+'-more';
            return false;
        }
        else if(params.countStep04 === 2)
        {
            ce4.util.toggleView('tut', step+'-more', 2);
        }
        else if(params.countStep04 === 3)
        {
            // Give them a few seconds to set the region box(es) then advance tutorial
            setTimeout($.proxy(function() {if(this.scheduledStep === "tutorial04-step08") ce4.util.toggleView('tut', "tutorial04-step08", 2); this.dialogRestore();}, this), 8000);
            //this.scheduledStep = step+'-done';
            this.scheduledStep = "tutorial04-step08";
        }
        return true;
    }
    // Step 9
    else if (step === "tutorial04-step09")
    {
         // stop the window reloading when the submit button is clicked from interrupting tutorial
//         this.abortAllowed = false;
    }
    // Step 11
    else if (step === "tutorial04-step11")
    {
        // Mark tutorial complete
//        this.abortAllowed = true;

        // Set tutorials complete, since they tagged images
        // TODO: consolidate these into a single flag
        this.complete(ce4.tutorial.ids.TUT01); // Mark the island simulator tutorial complete too
        this.complete(ce4.tutorial.ids.TUT03); // Mark the starter tutorial complete too
        this.complete(ce4.tutorial.ids.TUT04);

        // Remove the tutorial dialog
        this.abort(ce4.tutorial.ids.TUT04);

        // Send them back to the home page
        ce4.ui.load_page(ce4.ui.HOME, true);

        return true;
    }

    // Auto advance to step
    return false;
};
