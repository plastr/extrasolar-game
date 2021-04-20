// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.map_tile contains the MapTile model.
goog.provide("ce4.map_tile");
goog.provide("ce4.map_tile.MapTile");
goog.provide("ce4.map_tile.MapTileCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util')
goog.require('ce4.util.EpochDateField');

ce4.map_tile.make_tile_key = function(zoom, x, y) {
    return zoom + "," + x + "," + y;
};

ce4.map_tile.dom_id = function(zoom, x, y) {
    return 'map_tile_' + [zoom, x, y].join("_");
};

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.map_tile.MapTile = function MapTile(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.map_tile.MapTile, lazy8.chips.Model);

/** @override */
ce4.map_tile.MapTile.prototype.fields = {
    tile_key: new lazy8.chips.Field({id_field:true}),
    zoom: new lazy8.chips.Field({required:true}),
    x: new lazy8.chips.Field({required:true}),
    y: new lazy8.chips.Field({required:true}),
    arrival_time: new ce4.util.EpochDateField({required:true})
};

ce4.map_tile.MapTile.prototype.dom_id = function() {
    return ce4.map_tile.dom_id(this.zoom, this.x, this.y);
};

ce4.map_tile.MapTile.prototype.to_url = function(url_root) {
    var filename = ce4.util.pad_int(this.x, 7) + "-" + ce4.util.pad_int(this.y, 7) + ".jpg";
    return url_root + "/" + [this.arrival_time, this.zoom, filename].join("/");
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.map_tile.MapTileCollection = function MapTileCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.map_tile.MapTileCollection, lazy8.chips.Collection);

/** @override */
ce4.map_tile.MapTileCollection.prototype.model_constructor = ce4.map_tile.MapTile;
