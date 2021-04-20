// Copyright (c) 2012 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.leaflet contains the new map page built on top of the Leaflet API.
goog.provide('ce4.leaflet');
goog.provide('ce4.leaflet.ExtraSolarMap');

goog.require('ce4.util');
goog.require('ce4.gamestate');
goog.require('ce4.region');
goog.require('ce4.region.styles');

goog.require('ce4.map_tile');
goog.require('ce4.leaflet.assets.icons');
goog.require('ce4.leaflet.target.TargetDisplay');
goog.require('ce4.leaflet.region.MapRegion');
goog.require('ce4.leaflet.controls.CreateButton');

ce4.leaflet.MIN_ZOOM = 17.0;
ce4.leaflet.MAX_ZOOM = 20.0;

//------------------------------------------------------------------------------
// Constructor for a new ExtraSolarMap
ce4.leaflet.ExtraSolarMap = function(options)
{
    // Initialize and cache
    this.user = options.user;
    this.urls = options.urls;
    this.last_clip_region = null;
    this.last_forbidden_region = null;
    this.bounds = [[6.233402, -109.42932],[6.255239, -109.407353]];

    // Create leaflet map
    this.leafletMap = new L.Map('leaflet-container', {
        attributionControl: false,
        zoomControl: true,
        maxBounds: this.bounds
    });

    // Add debug map tools on keypress
    this.DebugControls();

    // Create tile layer
    this.ce4Map = new L.TileLayer.CE4('', {
        attribution: 'ce4',
        minZoom: ce4.leaflet.MIN_ZOOM,
        maxZoom: ce4.leaflet.MAX_ZOOM,
        tileURLCallback: $.proxy(ce4.leaflet.getTileURL,this)
    });
    this.leafletMap.addLayer(this.ce4Map);

    // Basic map setup
    this.roverControl     = ce4.leaflet.controls.CreateButton({context: this, onClick: this.centerRover, css: 'find-rover-button', title: 'Lost your rover?  Find it again!'});
    this.tasksShowControl = ce4.leaflet.controls.CreateButton({context: this, onClick: this.showTasks, css: 'show-tasks-button', title: 'Show task list!'});
    this.tasksHideControl = ce4.leaflet.controls.CreateButton({context: this, onClick: this.hideTasks, css: 'hide-tasks-button', title: 'Hide task list!', html: 'Active Tasks'});
    this.fullscreenEnter  = ce4.leaflet.controls.CreateButton({context: this, onClick: this.enterFullscreen, css: 'fullscreen-enter-button', title: 'Full screen', position: 'topleft'});
    this.fullscreenExit   = ce4.leaflet.controls.CreateButton({context: this, onClick: this.exitFullscreen, css: 'fullscreen-exit-button', title: 'Exit full screen', position: 'topleft'});
    this.tasksListControl = ce4.leaflet.controls.CreateButton({css: 'list-tasks-panel',  title: 'Task list'});
    this.leafletMap.addControl(this.tasksShowControl);
    this.leafletMap.addControl(this.roverControl);
    this.leafletMap.addControl(this.fullscreenEnter);
    this.leafletMap.on('popupopen',  this.toggleTasksOff, this);
    this.leafletMap.on('popupclose', this.toggleTasksOn,  this);
    this.fitRegions();
    this.refreshUserData();
    if(this.hasTasks()) this.showTasks();
};

//------------------------------------------------------------------------------
// Watch for a keypress to enable DebugControls (ctrl+alt+backspace)
ce4.leaflet.ExtraSolarMap.prototype.DebugControls = function(ev)
{
    var kp = function(ev)
    {
        if (ev.which === 8 && ev.altKey && ev.ctrlKey )
        {
            this.debugEnabled = true;

            this.debugDraw = new L.DrawMod(this.leafletMap);

            $(document).unbind('keydown', kp);
        }
    }
    $(document).keydown($.proxy(kp, this));
};

//------------------------------------------------------------------------------
// If the URL for a map tile has changed, update that tile now.
ce4.leaflet.ExtraSolarMap.prototype.updateMapTile = function(tile)
{
    this.ce4Map.updateTileUrl(new L.Point(tile.x, tile.y), tile.zoom);
};

//------------------------------------------------------------------------------
// Leaflet calls this function to construct at tile URL from its location and zoom parameters.
ce4.leaflet.getTileURL = function(tilePoint, zoom)
{
    var customTileKey = ce4.map_tile.make_tile_key(zoom, tilePoint.x, tilePoint.y);

    // If there is a custom map tile, use that.
    if (this.user.map_tiles && this.user.map_tiles.contains(customTileKey)) {
        var customTile = this.user.map_tiles.get(customTileKey);
        return customTile.to_url(this.urls.user_map_tile);

    // Use the default tile if there isn't a custom one
    } else {
        return [ this.urls.map_tile,
                 zoom,
                 ce4.util.pad_int(tilePoint.x, 7),
                 [ ce4.util.pad_int(tilePoint.x, 7),
                   ce4.util.pad_int(tilePoint.y, 7) + ".jpg"
                 ].join('-')
               ].join('/');
    }
};

//------------------------------------------------------------------------------
// Set up a timer to update the map every minute.
ce4.leaflet.ExtraSolarMap.prototype.onShow = function()
{
    // Map size might have changed so recalculate leaflet dimensions
    this.leafletMap.invalidateSize();

    var map = this;
    this.map_interval_id = setInterval(function() { map.updateMap(); }, 60000);
    this.updateMap();
};

//------------------------------------------------------------------------------
// Kill the update timer.
ce4.leaflet.ExtraSolarMap.prototype.onHide = function()
{
    clearInterval(this.map_interval_id);
};

//------------------------------------------------------------------------------
// Clear old user data.
ce4.leaflet.ExtraSolarMap.prototype.clearUserData = function()
{
    if (this.markers)
    {
        for (var rover_id   in this.markers.targets)
        for (var target_id  in this.markers.targets[rover_id])    this.markers.targets[rover_id][target_id].remove();
        for (var rover_id   in this.markers.rovers)               this.leafletMap.removeLayer(this.markers.rovers[rover_id]);
        for (var rover_id   in this.markers.landers)              this.leafletMap.removeLayer(this.markers.landers[rover_id]);
        for (var rover_id   in this.markers.drag_markers)         this.markers.drag_markers[rover_id].remove(true);
        for (var mission_id in this.markers.missions)             this.markers.missions[mission_id].remove();
        for (var region_id  in this.markers.regions)              this.markers.regions[region_id].remove();
    }
    this.markers = {drag_markers:{}, rovers:{}, targets:{}, landers:{}, missions:{}, regions:{}};
};

//------------------------------------------------------------------------------
// Clear the old user data and draw from scratch with new changes
ce4.leaflet.ExtraSolarMap.prototype.refreshUserData = function()
{
    // Clear old user data
    this.clearUserData();

    // Display the rovers
    this.user.rovers.forEach(
        function(rover) { this.displayRover(rover); }, this
    );

    // Draw visible regions
    this.user.regions.forEach(
        function(region){ if (region.visible) this.displayRegion(region); }, this
    );

    // Refresh Tasks List
    this.refreshTasks();
};

//------------------------------------------------------------------------------
// For missions with associated regions, show the regions
ce4.leaflet.ExtraSolarMap.prototype.displayRegion = function(region)
{
    this.markers.regions[region.region_id] = new ce4.leaflet.region.MapRegion(this.leafletMap, region);
};

//------------------------------------------------------------------------------
// Update minor changes on the map like the position of the rover moving along its route.
ce4.leaflet.ExtraSolarMap.prototype.updateMap = function()
{
    // Update the position of each rover on the map.
    this.user.rovers.forEach(
        function(rover)
        {
            // Update position of rover icon.
            this.markers.rovers[rover.rover_id].setLatLng(rover.getCoordsProjected());

            // Update position where line changes color.
            var target = rover.getFirstUnprocessedTarget();
            if (target && this.markers.targets[rover.rover_id][target.target_id]) this.markers.targets[rover.rover_id][target.target_id].update();

            // Update the drag marker.
            if (this.markers.drag_markers[rover.rover_id] != undefined) this.markers.drag_markers[rover.rover_id].update();
        }, this
    );
}

//------------------------------------------------------------------------------
// show the rover's targets, which will also show its path on the surface
ce4.leaflet.ExtraSolarMap.prototype.displayRover = function(rover)
{
    var targets = rover.all_targets();

    // If rover has no targets, don't display until it does (possibly supplied by forthcoming chips)
    if (targets.length !== 0)
    {
        // Clear marker targets
        this.markers.targets[rover.rover_id] = {};

        // Draw all targets and the lines between them.
        for(var i = 1; i < targets.length; i++)
        {
            var target = targets[i];
            this.markers.targets[rover.rover_id][target.target_id] = new ce4.leaflet.target.TargetDisplay(this, targets[i-1], rover, target);
        }

        // Show the rover if it's active
        this.markers.rovers[rover.rover_id] = new L.Marker(rover.getCoordsProjected(), {
            icon: ce4.leaflet.assets.icons.PLAYER_ROVER,
            title:"Active Rover",
            draggable: false,
            opacity: rover.active ? 1.0 : 0.0, // hide inactive rovers
            zIndexOffset: rover.active ? 0 : -10 // TODO: increase to 100?
        });
        this.leafletMap.addLayer(this.markers.rovers[rover.rover_id]);

        // Show the lander
        this.markers.landers[rover.rover_id] = new L.Marker([rover.lander.lat, rover.lander.lng], {
            icon: ce4.leaflet.assets.icons.MARKER_ICON_LANDER,
            title:"Lander",
            clickable: false,
            draggable: false,
            zIndexOffset: 0
        });
        this.leafletMap.addLayer(this.markers.landers[rover.rover_id]);

        // Create draggable control over the rover
        this.initDragMarker(rover);
    }
};

//------------------------------------------------------------------------------
// Indicates the single nearest region that a line is clipping against
ce4.leaflet.ExtraSolarMap.prototype.showClipRegion = function(region, coords)
{
    var id = region && region.region_id;
    if (id != this.last_clip_region)
    {
        // Hide the old region
        if (this.last_clip_region)
        {
            // Hide visible regions
            if(this.user.regions.get(this.last_clip_region).visible) this.markers.regions[this.last_clip_region].hide();;

            if (this.clipPopup) this.clipPopup._close();
            this.last_clip_region = null;
        }

        // Show the new SHOW_ON_CLIP region
        if (id && this.user.regions.get(id).style === ce4.region.styles.SHOW_ON_CLIP)
        {
            // Show visible regions
            if(this.user.regions.get(id).visible && this.markers.regions[id]) this.markers.regions[id].show();

            // Diplay a popup when clipping a region
            this.clipPopup = L.popup({className: 'standard-leaflet-popup', autoPan: false, closeButton: false, maxWidth: 200})
                 .setLatLng(coords)
                 .setContent((region.title ? ("<b>"+region.title+"</b></br>") : "")  + region.description)
                 .openOn(this.leafletMap);

            this.last_clip_region = id;
        }
    }
};

//------------------------------------------------------------------------------
// Display a restricted access region.
ce4.leaflet.ExtraSolarMap.prototype.showForbiddenRegion = function(region)
{
    var id = region && region.region_id;
    if (id != this.last_forbidden_region)
    {
        // Hide the old region
        if (this.last_forbidden_region)
        {
            // Hide visible regions
            this.markers.regions[this.last_forbidden_region].hide();
            this.last_forbidden_region = null;
        }

        // Show the new region
        if (id)
        {
            // If this region doesn't have a corresponding MapRegion, make one now.
            // For RESTRICT_OUTSIDE regions, override the style to have a red fill.
            if (!this.markers.regions[id]) {
                var styleOverride = undefined;
                if (region.restrict === ce4.region.RESTRICT_OUTSIDE)
                    styleOverride = ce4.region.styles.FORBIDDEN;
                this.markers.regions[id] = new ce4.leaflet.region.MapRegion(this.leafletMap, region, styleOverride);
            }
            this.markers.regions[id].show();
            this.last_forbidden_region = id;
        }
    }
}

//------------------------------------------------------------------------------
// Fits the map view to important regions
ce4.leaflet.ExtraSolarMap.prototype.fitRegions = function(region)
{
    var points = [];

    // Include active rovers
    this.user.rovers.forEach(function(rover) {
        if (rover.active) points.push(rover.getCoords());
    });

    // Include visible mission regions
    $.each(this.user.notdone_missions("root"), $.proxy(function(i, mission) {
        $.each(mission.allRegionIDs(), $.proxy(function(j, region_id){
            var region = this.user.regions.get(region_id);
            if(region.visible) {
                if(region.center.length != 0) points.push(region.center);
                points.push.apply(points, region.verts);
            }
        },this));
    },this));

    // If we have no points, get a useful point from the user
    if(points.length <= 0) points.push(this.user.get_recent_map_point());

    // Fit bounds to region
    this.leafletMap.fitBounds((new L.LatLngBounds(points)).pad(0.1), { animate: false});

    // Zoom out a little if we are at MAX_ZOOM
    // TODO: This breaks TUT01, figure out how to make it work without checking tutorial flags
    if(this.user.tutorial.is_completed(ce4.tutorial.ids.TUT04) && this.leafletMap.getZoom() == ce4.leaflet.MAX_ZOOM) this.leafletMap.zoomOut(1, {animate: false});
};

//------------------------------------------------------------------------------
// Center on the region
ce4.leaflet.ExtraSolarMap.prototype.centerRegion = function(region)
{
    if(this.markers.regions[region])
    {
        if(this.markers.regions[region].mapShapes[0].getBounds)
        {
            // Use fitBounds if we need to zoom out to see the entire region
            if(this.leafletMap.getBoundsZoom(this.markers.regions[region].mapShapes[0].getBounds()) < this.leafletMap.getZoom())
            {
                this.leafletMap.fitBounds(this.markers.regions[region].mapShapes[0].getBounds());
            }
            else
            {
                this.centerLatLng(this.markers.regions[region].mapShapes[0].getBounds().getCenter());
            }
        }
        else
        {
            this.centerLatLng(this.markers.regions[region].mapShapes[0].getLatLng());
        }
        this.markers.regions[region].mapShapes[0].openPopup();
    }
};

//------------------------------------------------------------------------------
// Center on the coordinates: [<lat>, <lng>]
ce4.leaflet.ExtraSolarMap.prototype.centerLatLng = function(coords)
{
    this.leafletMap.panTo(coords);
};

//------------------------------------------------------------------------------
// Center on the first active rover.
ce4.leaflet.ExtraSolarMap.prototype.centerRover = function()
{
    var rover = this.user.rovers.find(function(rover) { return rover.active === 1; });
    if (rover !== undefined)
       this.leafletMap.panTo(rover.getCoordsProjected());
};

//------------------------------------------------------------------------------
// Returns true if there are any tasks in the task list
ce4.leaflet.ExtraSolarMap.prototype.hasTasks = function()
{
    var has_tasks = false;

    // Find the first task in the list
    $.each(this.user.notdone_missions("root"), $.proxy(function(i, mission) {
        if(mission.allRegionIDs().length > 0) {
            has_tasks = true;
            return false;
        }
    }, this));

    return has_tasks;
};

//------------------------------------------------------------------------------
// Refresh the task list
ce4.leaflet.ExtraSolarMap.prototype.refreshTasks = function()
{
    var region_ids;
    var taskHTML = "";

    $.each(this.user.notdone_missions("root"), $.proxy(function(i, mission) {
        // all region ids
        region_ids = mission.allRegionIDs();

        // Any mission with regions
        if(region_ids.length > 0)
        {
            // Task Item Start
            taskHTML += "\
                <div class=\"list-tasks-panel-item\">\
                    <div class=\"list-tasks-panel-item-image\">";

            // Region Icons
            $.each(region_ids, $.proxy(function(j, region_id){
                var region = this.user.regions.get(region_id);
                if(region.visible)
                {
                    taskHTML += "\
                        <a href=\"#map\" onclick=\"ce4.ui.leaflet.centerRegion('"+region_id+"'); return false;\" \
                        title=\""+region.title+"\"><center><img src=\""+ce4.leaflet.region.MapIcon(region)+"\"></center></a>";
                }
            }, this));

            // Mission Details
            taskHTML += "\
                    </div>\
                    <div class=\"list-tasks-panel-item-mission\">\
                        <div class=\"list-tasks-panel-item-title\" title=\""+mission.title+"\"><div class=\"dwindle\">"+mission.title+"</div><a href='#task," + mission.mission_id + "'><img title=\"See more\" src=\""+ce4.util.url_static("/img/see-all-icon.png")+"\"></a></div>\
                        <div class=\"list-tasks-panel-item-description\">"+mission.summary;

            if(mission.parts)
                taskHTML += "<br> &bull; " + mission.get_first_incomplete_part().title;

            // Task Item End
            taskHTML += "\
                        </div>\
                    </div>\
                </div>";
        }
    }, this));

    // No tasks in list
    if(taskHTML == "")
    {
        taskHTML += "<div class=\"list-tasks-panel-item\"><div class=\"list-tasks-panel-item-mission\"><div class=\"list-tasks-panel-item-description\">There are no active map tasks.</div></div></div>";
    }

    this.tasksListControl.setHTML(taskHTML);
};

//------------------------------------------------------------------------------
// Toggles the task list on and off, used to temporarily hide the task list if open
ce4.leaflet.ExtraSolarMap.prototype.toggleTasksOff = function() { this.toggleTasks(false); };
ce4.leaflet.ExtraSolarMap.prototype.toggleTasksOn  = function() { this.toggleTasks(true);  };
ce4.leaflet.ExtraSolarMap.prototype.toggleTasks = function(toggle_on)
{
    if(this.tasksListControl._map != null && !toggle_on)
    {
        this.toggleTasksRestore = true;
        this.hideTasks();
    }
    else if(toggle_on && this.toggleTasksRestore && this.tasksListControl._map == null)
    {
        this.toggleTasksRestore = false;
        this.showTasks();
    }
};

//------------------------------------------------------------------------------
// Show the task list
ce4.leaflet.ExtraSolarMap.prototype.showTasks = function()
{
    // Set up controls
    this.leafletMap.removeControl(this.tasksShowControl);
    this.leafletMap.removeControl(this.roverControl);
    this.leafletMap.addControl(this.tasksHideControl);
    this.leafletMap.addControl(this.tasksListControl);
    this.leafletMap.addControl(this.roverControl);

    // Refresh Tasks List
    this.refreshTasks();
};

//------------------------------------------------------------------------------
// Hide the task list
ce4.leaflet.ExtraSolarMap.prototype.hideTasks = function()
{
    this.leafletMap.removeControl(this.tasksHideControl);
    this.leafletMap.removeControl(this.tasksListControl);
    this.leafletMap.removeControl(this.roverControl);
    this.leafletMap.addControl(this.tasksShowControl);
    this.leafletMap.addControl(this.roverControl);
};

//------------------------------------------------------------------------------
// Enter Fullscreen
ce4.leaflet.ExtraSolarMap.prototype.enterFullscreen = function()
{
    this.leafletMap.removeControl(this.fullscreenEnter);
    this.leafletMap.addControl(this.fullscreenExit);
    ce4.ui.fullscreen(true)
};

//------------------------------------------------------------------------------
// Exit Fullscreen
ce4.leaflet.ExtraSolarMap.prototype.exitFullscreen = function()
{
    this.leafletMap.removeControl(this.fullscreenExit);
    this.leafletMap.addControl(this.fullscreenEnter);
    ce4.ui.fullscreen(false)
};

//------------------------------------------------------------------------------
// Find TargetMarker for a target, center, zoom in, and display its info
ce4.leaflet.ExtraSolarMap.prototype.centerTarget = function(target)
{
    this.leafletMap.setView(target.getCoords(), ce4.leaflet.MAX_ZOOM);
    this.openTarget(target);
};

//------------------------------------------------------------------------------
// Find TargetMarker for a target and display its info
ce4.leaflet.ExtraSolarMap.prototype.openTarget = function(target, rover)
{
    for (var roverId in this.markers.targets)
    {
        if((!rover || roverId == rover.rover_id) && this.markers.targets[roverId][target.target_id])
        {
            this.markers.targets[roverId][target.target_id].marker.fire('click');
            break;
        }
    }
};

//------------------------------------------------------------------------------
// Initialize a dragable icon that hovers over the rover and can be dragged to create a new target.
ce4.leaflet.ExtraSolarMap.prototype.initDragMarker = function(rover)
{
    // If the wizard is open, reuse the drag marker
    if(rover.wizard) this.markers.drag_markers[rover.rover_id] = rover.wizard.tdisplay;

    // Set to same location as the active rover marker
    else if(rover.active) this.markers.drag_markers[rover.rover_id] = new ce4.leaflet.target.TargetDisplay(this, rover.getLastTarget(), rover);
};
