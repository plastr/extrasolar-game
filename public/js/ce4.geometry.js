// Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.geometry contains useful math and vector routines.
goog.provide("ce4.geometry");

// Vector math.  Note that rather than creating a full vector class, these functions
// operate on arrays of size 2.
// TODO: Allow the inputs to be other types of data.  Throw errors for unexpected types.
ce4.geometry.vec2add = function(v0, v1) {
    return [v0[0]+v1[0], v0[1]+v1[1]];
};

ce4.geometry.vec2subtract = function(v0, v1) {
    return [v0[0]-v1[0], v0[1]-v1[1]];
};

ce4.geometry.vec2dot = function(v0, v1) {
    return v0[0]*v1[0] + v0[1]*v1[1];
};

// Convert a lat/lng pair into our canonical coordinate system, which is based
// on a planet with circumference 2^25 and then translated to the region where
// our map data is concentrated.
ce4.geometry.latLngToMeters = function(latLng) {
    var siny = Math.sin(latLng[0]*Math.PI/180.0);
    var yd = 16777216.0 - 0.5*Math.log((1.0+siny)/(1.0-siny))*(33554432.0/(2.0*Math.PI));
    var xd = 16777216.0 + latLng[1]*(33554432.0/360.0);

    // Translate to the renderer's coordinate system
    // Map tile offset: 25694,63254 at level 17 (1m per pixel, 256x256 pixels)
    var originX = 25694*256;
    var originY = 63254*256;
    yd -= originY;
    xd -= originX;

    return [xd,yd];
}

// Compute the distance, in meters, between two lat/lng pairs in our canonical
// coordinate system.  Note that this differes from the real haversine.
ce4.geometry.distCanonical = function(latLngA, latLngB) {
    var va = ce4.geometry.latLngToMeters(latLngA);
    var vb = ce4.geometry.latLngToMeters(latLngB);
    var vDelta = ce4.geometry.vec2subtract(va, vb);
    var distSq = ce4.geometry.vec2dot(vDelta, vDelta);
    return Math.sqrt(distSq);
}

// Get the angle, in radians, from A to B. 0=north, PI/2=east, etc.
ce4.geometry.getDirection = function(latLngA, latLngB) {
    var va = ce4.geometry.latLngToMeters(latLngA);
    var vb = ce4.geometry.latLngToMeters(latLngB);
    var dx = vb[0] - va[0];
    var dy = vb[1] - va[1];
    if (dx === 0.0 && dy === 0.0)
        return 0.0;
    return Math.atan2(dy, dx) + Math.PI/2.0;
}

// Get the actual distance between points on a sphere.  Note, we primarily use our
// own canonical coordinate system, so you probably don't want to use this function.
WORLD_RADIUS_KM = 6371;
WORLD_RADIUS_M = WORLD_RADIUS_KM * 1000;
ce4.geometry.haversine = function(ll1, ll2) {
    // Returns the distance in meters between a pair of lat/long coordinates.
    // ganked from http://www.movable-type.co.uk/scripts/latlong.html
    var dLat = ce4.util.toRadians(ll2.lat-ll1.lat);
    var dLon = ce4.util.toRadians(ll2.lng-ll1.lng);
    var a = Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(ce4.util.toRadians(ll1.lat)) *
            Math.cos(ce4.util.toRadians(ll2.lat)) *
            Math.sin(dLon/2) * Math.sin(dLon/2); 
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
    var d = WORLD_RADIUS_M * c;
    return d;
}

// Get a scale multiplier to perform a conversion between distances from
// Google maps to our canonical coordinate system.
ce4.geometry.getMapScaleFactor = function(lat) {
    // Earth's actual circumference/Canonical circumference*latitude adjustment.
    return 40075016.69/33554432.0*Math.cos(lat*Math.PI/180.0);
}
