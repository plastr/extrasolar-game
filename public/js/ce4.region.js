// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.region contains the Region model.
goog.provide("ce4.region");
goog.provide("ce4.region.Region");
goog.provide("ce4.region.RegionCollection");
goog.provide("ce4.region.styles");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');
goog.require('ce4.geometry');

// Region constants
ce4.region.LINE_EPSILON = 0.000000001;

ce4.region.SHAPE_POLYGON  = "POLYGON";
ce4.region.SHAPE_POLYLINE = "POLYLINE";
ce4.region.SHAPE_CIRCLE   = "CIRCLE";
ce4.region.SHAPE_POINT    = "POINT";

ce4.region.RESTRICT_NONE    = "NONE";
ce4.region.RESTRICT_INSIDE  = "INSIDE";
ce4.region.RESTRICT_OUTSIDE = "OUTSIDE";

ce4.region.styles.DEFAULT_FILL   = "STYLE_DEFAULT_FILL";
ce4.region.styles.FORBIDDEN      = "STYLE_FORBIDDEN";
ce4.region.styles.HAZARD_LINE    = "STYLE_HAZARD_LINE";
ce4.region.styles.HAZARD_FILL    = "STYLE_HAZARD_FILL";
ce4.region.styles.SURVEY         = "STYLE_SURVEY";
ce4.region.styles.DOT            = "STYLE_DOT";
ce4.region.styles.WAYPOINT       = "STYLE_WAYPOINT";
ce4.region.styles.AUDIO          = "STYLE_AUDIO";
ce4.region.styles.SHOW_ON_CLIP   = "STYLE_SHOW_ON_CLIP";
ce4.region.styles.ROVER_LIMIT    = "STYLE_ROVER_LIMIT";
ce4.region.styles.TUTORIAL       = "STYLE_TUTORIAL";
ce4.region.styles.PROCESSED_LINE = "STYLE_PROCESSED_LINE";
ce4.region.styles.PENDING_LINE   = "STYLE_PENDING_LINE";
ce4.region.styles.MARKER         = "STYLE_MARKER";

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.region.Region = function Region(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.region.Region, lazy8.chips.Model);

/** @override */
// These fields may be null or empty lists: 'marker_icon', 'region_icon', 'verts', 'center', 'radius'.
ce4.region.Region.prototype.fields = {
    region_id: new lazy8.chips.Field({id_field:true}),
    title: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    restrict: new lazy8.chips.Field({required:true}),
    style: new lazy8.chips.Field({required:true}),
    visible: new lazy8.chips.Field({required:true}),
    shape: new lazy8.chips.Field({required:true}),
    marker_icon: new lazy8.chips.Field({required:true}),
    region_icon: new lazy8.chips.Field({required:true}),
    verts: new lazy8.chips.Field({required:true}),
    center: new lazy8.chips.Field({required:true}),
    radius: new lazy8.chips.Field({required:true})
};

// Using the parametric equation for a line segment between start and end, compute
// the time t > 0 at which the segment intersects the polygon.
// Params: Start and end should each be a two-element array with lat and lng.
ce4.region.Region.prototype.clip_line = function(start, end) {
    var tNearest =  9999999.0;
    // If this region doesn't restrict movement, don't clip the line.
    if (this.restrict === ce4.region.RESTRICT_NONE) {
        return 1.0;
    }

    if (this.shape === ce4.region.SHAPE_POLYGON) {
        // For each pair of coordinates in the polygon, see if there is an intersection.
        var numVerts = this.verts.length;
        for (var i=0; i<numVerts; i++) {
            var v0 = this.verts[i];
            var v1 = this.verts[(i+1)%numVerts];
            // Compute which halfspace the start and endpoints lie in.
            var halfspace_start = ce4.region.point_line_halfspace(start, v0, v1);
            var halfspace_end   = ce4.region.point_line_halfspace(end, v0, v1);
            // If both points are on the same side of the line, ignore this segment.
            if (halfspace_start >  ce4.region.LINE_EPSILON && halfspace_end > 0.0) {
                continue;
            }
            if (halfspace_start < -ce4.region.LINE_EPSILON && halfspace_end < 0.0) {
                continue;
            }
            // If we and are leaving a RESTRICT_OUTSIDE space, ignore this segment.
            if (halfspace_end <= 0.0 && this.restrict === ce4.region.RESTRICT_OUTSIDE) {
                continue;
            }
            // If we are entering a RESTRICT_INSIDE space, ignore this segment
            if (halfspace_end >= 0.0 && this.restrict === ce4.region.RESTRICT_INSIDE) {
                continue;
            }
            // If the determinate is 0, the lines are parallel or one segment is a point.
            var det = (v1[1]-v0[1])*(end[0]-start[0]) - (v1[0]-v0[0])*(end[1]-start[1]);
            if (det === 0.0) {
                continue;
            }
            // Calculate the time t of the intersection in the parametric equation for the poly.
            var tPoly = ((end[0]-start[0])*(start[1]-v0[1]) -
                        (end[1]-start[1])*(start[0]-v0[0]))/det;
            if (tPoly < 0.0 || tPoly > 1.0) {
                // Intersection was beyond the ends of the line segment.
                continue;
            }
            // Calculate the time t of the intersection in the parametric equation for the ray.
            var tRay = ((v1[0]-v0[0])*(start[1]-v0[1]) -
                       (v1[1]-v0[1])*(start[0]-v0[0]))/det;
            // Compare against -LINE_EPSILON instead of 0 to allow intersections a short distance
            // behind us.  This is important if the starting point is right on the line.
            if (tRay >= -ce4.region.LINE_EPSILON && tRay < tNearest) {
                tNearest = tRay;
            }
        }
        return tNearest;
    }

    if (this.shape === ce4.region.SHAPE_POINT || this.shape === ce4.region.SHAPE_CIRCLE) {
        // If the circle has radius 0 or this point has no 'halo' radius, no clipping will happen.
        if (this.radius === 0.0) {
            return 1.0;
        }

        // Convert our center, start and end points into vectors in meter space.
        var vCenter = ce4.geometry.latLngToMeters(this.center);
        var vStart = ce4.geometry.latLngToMeters(start);
        var vEnd = ce4.geometry.latLngToMeters(end);        

        // The only difference between POINT and CIRCLE behavior is that for points,
        // lines are clipped only if the endpoint falls inside the halo.
        if (this.shape === ce4.region.SHAPE_POINT) {
            var dx = vEnd[0]-vCenter[0];
            var dy = vEnd[1]-vCenter[1];
            if (dx*dx + dy*dy >= this.radius*this.radius)
                return 1.0;  // Don't clip.
        }

        // Translate our coordinate system so that the circle is at the origin.
        vStart = ce4.geometry.vec2subtract(vStart, vCenter);
        vEnd = ce4.geometry.vec2subtract(vEnd, vCenter);

        // Solve the parametric equation using the quadratic formula.
        var vDir = ce4.geometry.vec2subtract(vEnd, vStart);
        var a = ce4.geometry.vec2dot(vDir, vDir);
        var b = 2*ce4.geometry.vec2dot(vStart, vDir);
        var c = ce4.geometry.vec2dot(vStart, vStart) - this.radius*this.radius;

        var discriminant = b*b-4*a*c;
        if( discriminant < 0 ) {  // No intersection.
            return 1.0;
        }
        else {
            discriminant = Math.sqrt(discriminant);
            var t1 = (-b - discriminant)/(2*a);
            var t2 = (-b + discriminant)/(2*a);
        
            if (t1 >= 0 && t1 <= 1)
                return t1;
            if (t2 >= 0 && t2 <= 1)
                return t2;
        }
        // No intersection.
        return 1.0;
    }

    // TODO: Handle intersections with other shape types.
    console.error("Unimplemented conditions in clip_line. Shape=" + this.shape + ".");
    return 1.0;  
};

// Return true if the point is inside the boundary, false otherwise.
// Params: point a two-element array with lat and lng.
ce4.region.Region.prototype.point_inside = function(point) {
    if (this.shape === ce4.region.SHAPE_POLYGON) {
        // Cast a ray in the +x direction and count line-segment crossings to determine if
        // the given point is inside the boundary.
        // For each pair of coordinates in the polygon, see if there is an intersection.
        var intersections = 0;
        var numVerts = this.verts.length;
        for (var i=0; i<numVerts; i++) {
            var v0 = this.verts[i];
            var v1 = this.verts[(i+1)%numVerts];
            // If the y-coordinates are the same, then no intersection is possible.
            if (v0[1] === v1[1]) {
                continue;
            }
            // Make sure that v0 has a smaller y-coordinate than v1.
            if (v0[1] > v1[1]) {
                var swap = v0;
                v0 = v1;
                v1 = swap;
            }
            // Check if the line from 'point' moving in the +x direction crosses this segment.
            // The choice of inequality operators is important to make sure we count a line
            // exactly once if we cross the vertex.
            if (point[1] > v1[1] || point[1] <= v0[1]) {
                continue;
            }
            // Compute which halfspace the point is in.
            var halfspace = ce4.region.point_line_halfspace(point, v0, v1);
            if (halfspace > 0) {
                intersections++;
            }
        }
        // An even number of intersections means we're outside the polygon.
        if (intersections%2 === 0) {
            return false;
        }
        return true;
    }
    else if (this.shape === ce4.region.SHAPE_CIRCLE || this.shape === ce4.region.SHAPE_POINT) {
        return ce4.region.point_inside_circle(point, this.center, this.radius);
    }

    // TODO: Check against other shape types.
    console.error("Unimplemented conditions in point_inside. Shape=" + this.shape + ".");
    return false;  
};

// Check which half-space the point is in relative to line [v0,v1].
// Params: Point, v0, and v1 are all arrays with x and y values.
// Return: A positive or negative value indicates the respective halfspace.
// 0 means the point is on the line or the line has zero length.
ce4.region.point_line_halfspace = function(point, v0, v1) {
    var v0_to_v1 = [v1[0]-v0[0], v1[1]-v0[1]];
    var v0_to_point = [point[0]-v0[0], point[1]-v0[1]];
    var normal = [-v0_to_v1[1], v0_to_v1[0]];

    // Take the dot product of the normal and v0_to_point.
    return normal[0]*v0_to_point[0] + normal[1]*v0_to_point[1];
};

// Check whether the given point falls within the given circle.
// Params: point, and center are arrays with lat and lng values.
//   radius is a float in meters.
// Return: True if the point falls inside the circle or on the radius.
// TODO: reimplement without google.maps
ce4.region.point_inside_circle = function(point, center, radius) {
    var vPoint  = ce4.geometry.latLngToMeters(point);
    var vCenter = ce4.geometry.latLngToMeters(center);
    var delta = [vPoint[0]-vCenter[0], vPoint[1]-vCenter[1]];
    return delta[0]*delta[0] + delta[1]*delta[1] <= radius*radius;
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.region.RegionCollection = function RegionCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.region.RegionCollection, lazy8.chips.Collection);

/** @override */
ce4.region.RegionCollection.prototype.model_constructor = ce4.region.Region;
