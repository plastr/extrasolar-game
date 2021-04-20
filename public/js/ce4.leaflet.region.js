// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.leaflet.region contains the map region display.
goog.provide('ce4.leaflet.region');
goog.provide('ce4.leaflet.region.MapRegion');
goog.provide('ce4.leaflet.region.MapIcon');
goog.provide('ce4.leaflet.region.styles');

goog.require('ce4.region');
goog.require('ce4.region.styles');
goog.require('ce4.leaflet.assets.icons');
goog.require('ce4.assets');

// Region Styles
ce4.leaflet.region.styles[ce4.region.styles.HAZARD_FILL] = {
    color: "#ff2222",
    opacity: 0.8,
    weight: 3,
    fillColor: "#aa2222",
    fillOpacity: 0.15,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.DEFAULT_FILL] = {
    color: "#aa44aa",
    opacity: 0.8,
    weight: 3,
    fillColor: "#4444aa",
    fillOpacity: 0.15,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.FORBIDDEN] = {
    color: "#aa0000",
    opacity: 1.0,
    weight: 3,
    fillColor: "#aa0000",
    fillOpacity: 0.3,
    bShowOnClip: true,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.SURVEY] = {
    color: "#aa44aa",
    opacity: 1.0,
    weight: 0,
    fillColor: "#ffaa00",
    fillOpacity: 0.35,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.DOT] = {
    color: "#ffffff",
    opacity: 0.0,
    weight: 0,
    fillColor: "#aa2222",
    fillOpacity: 1.00,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.AUDIO] = {
    color: "#4444aa",
    opacity: 1.0,
    weight: 0,
    fillColor: "#4444aa",
    fillOpacity: 0.35,
    clickable: true};

ce4.leaflet.region.styles[ce4.region.styles.SHOW_ON_CLIP] = {
    color: "#aa0000",
    opacity: 1.0,
    weight: 3,
    fillColor: "#aa0000",
    fillOpacity: 0.0,
    bShowOnClip: true,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.ROVER_LIMIT] = {
    color: "#F2EEDD",
    opacity: 0.15,
    weight: 1,
    fillColor: "#F2EEDD",
    fillOpacity: 0.35,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.TUTORIAL] = {
    color: "#44FF44",
    weight: 0,
    fillColor: "#44FF44",
    fillOpacity: 0.15,
    clickable: false};

// Line Styles
ce4.leaflet.region.styles[ce4.region.styles.HAZARD_LINE] = {
    color: "#ff2222",
    opacity: 0.8,
    weight: 3,
    clickable: true};

ce4.leaflet.region.styles[ce4.region.styles.PROCESSED_LINE] = {
    color: "#000000",
    opacity: 0.3,
    weight: 5,
    clickable: false};

ce4.leaflet.region.styles[ce4.region.styles.PENDING_LINE] = {
    color: "#F2EEDD",
    opacity: 0.6,
    weight: 5,
    clickable: false};

// Marker Styles
ce4.leaflet.region.styles[ce4.region.styles.WAYPOINT] = {
        icon: ce4.leaflet.assets.icons.WAYPOINT,
        clickable: true};

ce4.leaflet.region.styles[ce4.region.styles.MARKER] = {
    clickable: true};

//------------------------------------------------------------------------------
// Constructor for a new map region, Params: (Leaflet L.Map, Region object)
ce4.leaflet.region.MapRegion = function(map, region, optStyleOverride)
{
    // Initialize
    this.map = map;
    this.mapShapes = []; // shapes to draw region

    // Set the style
    var style = ce4.leaflet.region.styles[region.style] || ce4.leaflet.region.styles[ce4.region.styles.DEFAULT_FILL];
    if (optStyleOverride)
        style = ce4.leaflet.region.styles[optStyleOverride];

    // Region style error check
    if (ce4.leaflet.region.styles[region.style] === undefined) console.error("Invalid region style: " + region.style + ". Using default.");

    // Create the region shapes
    switch (region.shape)
    {
        case ce4.region.SHAPE_POLYGON:    this.mapShapes.push(new L.Polygon(region.verts.slice(0), style)); // slice(0) dupes array (leaflet mods it)
            break;

        case ce4.region.SHAPE_POLYLINE:   this.mapShapes.push(new L.Polyline(region.verts.slice(0), style)); // slice(0) dupes array (leaflet mods it)
            break;

        case ce4.region.SHAPE_POINT:      this.mapShapes.push(new L.Marker(region.center.slice(0), $.extend({title: region.title || region.description}, style))); // slice(0) dupes array (leaflet mods it)

                                          // Set a custom icon if it has one
                                          if(region.marker_icon) this.mapShapes[0].setIcon(ce4.leaflet.assets.icons[region.marker_icon]);

                                          // Set the style for the halo circle if the point has a radius and is not style ICON
                                          if(region.radius > 0.0 && region.style !== ce4.region.styles.MARKER) style = ce4.leaflet.region.styles[ce4.region.styles.SURVEY];
                                          else break;

        case ce4.region.SHAPE_CIRCLE:     this.mapShapes.push(new L.Circle(region.center.slice(0), region.radius*ce4.geometry.getMapScaleFactor(region.center[0]), style)); // slice(0) dupes array (leaflet mods it)
            break;
    }

    // Add a popup the primary shape
    this.mapShapes[0].bindPopup((region.title ? ("<b>"+region.title+"</b></br>") : "")  + region.description , {className: 'standard-leaflet-popup', offset: new L.Point(0,-40)})

    // SHOW_ON_CLIP regions should be hidden until a path clips them
    if (region.style === ce4.region.styles.SHOW_ON_CLIP)  this.hide();
    else                                                  this.show();
};

//------------------------------------------------------------------------------
// Shows all regions
ce4.leaflet.region.MapRegion.prototype.show = function()
{
    for (var i=0; i < this.mapShapes.length; i++) {
        this.map.addLayer(this.mapShapes[i]);
    }
};

//------------------------------------------------------------------------------
// Hides all regions
ce4.leaflet.region.MapRegion.prototype.hide = function()
{
    for (var i=0; i < this.mapShapes.length; i++) {
        this.map.removeLayer(this.mapShapes[i]);
    }
};

//------------------------------------------------------------------------------
// Removes all regions from the map entirely
ce4.leaflet.region.MapRegion.prototype.remove = function()
{
    this.hide();
};

//------------------------------------------------------------------------------
// Returns an icon URL for the region
ce4.leaflet.region.MapIcon = function(region)
{
    return region.region_icon && ce4.assets.region[region.region_icon] || region.marker_icon && ce4.assets.region[region.marker_icon] || ce4.assets.region[region.style] || ce4.assets.region.DEFAULT;
}
