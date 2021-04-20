// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
//
// Contains chip Model, Field, Collection, and Manager classes for handling chips loaded
// from a server and updates thereafter.
// Borrows heavily (including documentation wording) from the Google Closure Library
// collections (goog.array, goog.object, goog.structs.*)
goog.provide("lazy8.chips");
goog.provide("lazy8.chips.ChipsError");
goog.provide("lazy8.chips.Field");
goog.provide("lazy8.chips.Model");
goog.provide("lazy8.chips.RootModel");
goog.provide("lazy8.chips.Collection");
goog.provide("lazy8.chips.Manager");

goog.require("goog.object");

/* Chip Type Constants */
lazy8.chips.DELETE = "d";
lazy8.chips.ADD = "a";
lazy8.chips.MOD = "m";

/**
 * A custom Error for chips related exceptions.
 * @constructor
 */
lazy8.chips.ChipsError = function(message) {
    this.name = 'ChipsError';
    this.message = message;
    this.stack = (new Error()).stack;
};
lazy8.chips.ChipsError.prototype = new Error();

/**
 * A helper to report a programmer error using the chips library.
 */
lazy8.chips.error = function(message) {
    throw new lazy8.chips.ChipsError(message);
};

/**
 * A helper to report a runtime warning using the chips library.
 */
lazy8.chips.warn = function(message) {
    console.warn(message);
};

/** Client IDs (cid) are used when a chip Model is created on the client before a
    real ID value can be generated and returned by the server. This is reset to 0
    each time this script is loaded. */
lazy8.chips._client_id_counter = 0;
lazy8.chips.get_next_client_id = function() {
    return "cid" + lazy8.chips._client_id_counter++;
};

// FUTURE: (Field):
// - Add an optional validator function? The validator function could return a new value.
// - Consider implementing the data_type system. Define the possibly field types in constants, e.g.
//   lazy8.field_types.Date, lazy8.field_types.Object, lazy8.field_types.Array and those name to the
//   strings returned by Closure goog.typeOf which knows about null and array.
//      data_type: undefined
//      data_type {string} (optional) The primitive type name that this field value must be an instance of.
// - For optional fields the value could be undefined or the expected type.
// - Should there be an optional default value if required is false?
// - Should there be a global instance of a RequiredField and OptionalField
//   which are just simple versions not requiring a new in those simple cases?
//   Same for "id_field" with an IDField instance? Or should these be namespaced
//   under like chips.field or chips.field_types or something like that?

/**
 * A chip Model Field. The basic specification provided by this object allows for Fields to
 * be flagged as id fields, allow for a client id, or be required or optional. This object may
 * be subclassed to provide additional functionality, especially by overriding create_computed_field.
 *
 * @constructor
 * @param {object} field_spec A description of this field. Keys may include:
 *  id_field {boolean} Whether this is the id_field. Required at least once per model. Assumes
 *       required: true.
 *  allow_cid {boolean} Whether an id_field can have a client ID (cid) assigned if no id_field
 *       value is supplied during construction. A subsequent MOD chip can set the id_field and
 *       clear the cid.
 *  required {boolean} Whether this is a required field.
 *  model_constructor {Object} Optionally provide a Model constructor to be used when instantiating
 *       this child model field.
 */
lazy8.chips.Field = function(field_spec) {
    var default_spec = {
        id_field: false,
        allow_cid: false,
        required: true,
        model_constructor: null
    };
    if (field_spec !== undefined) {
        goog.object.extend(default_spec, field_spec);
    }
    if (default_spec.id_field === true) {
        default_spec.required = true;
    }
    goog.object.extend(this, default_spec);
};

/**
 * If overriden by a Field subclass, allow the Field to augment the Model instance
 * when this Field is first processed during Model instantiation.
 * This is currently intended to be used to add computed fields to the Model instance.
 *
 * @param {lazy8.chips.Model} model The Model instance this Field is apart of.
 * @param {string} field_name The name of the field this Field represents and wraps.
 */
lazy8.chips.Field.prototype.create_computed_field = function(model, field_name) {
   //  By default do nothing.
};

/**
 * A chip Model. This Object has a list of known fields associated with it and
 * is designed to wrap chip updates as they come in from the server. When constructed
 * with a chip_struct, all required fields must be present or an error will occur.
 *
 * NOTE: When defining a new Model 'subclass', be sure to use the named function style e.g.:
 *  foo.Bar = function Bar(chip_struct) {
 *      lazy8.chips.Model.call(this, chip_struct);
 *  };
 *  goog.inherits(foo.Bar, lazy8.chips.Model);
 *
 * @param {Object} chip_struct The chip data to initialize this model with.
 * @constructor
 */
lazy8.chips.Model = function(chip_struct) {
    if (chip_struct === undefined) {
        lazy8.chips.error('Chip struct data is required when creating a Model instance ' + this);
    }

    this._id_field_name = null;
    this._allow_cid = false;
    this._cid = null;
    this._required_fields = {};
    this._optional_fields = {};
    // Holds the field names which are themselves Model singletons. Values are constructors.
    this._model_fields = {};
    // The optional collection this model is a member of.
    // Expected to be a lazy8.chips.Collection instance.
    this._collection = null;

    // Parse the fields list for correctness and cache the results.
    this._parseFields();
    // Handle the collections list.
    this._processCollections();

    this.merge_chip_struct(chip_struct, true);
    // If we still don't have an ID, generate a CID if allowed, otherwise this is
    // an error.
    if (!this.has_id()) {
        if (this._allow_cid) {
            this._cid = lazy8.chips.get_next_client_id();
        }
    }
};

/** Define the list of fields known to this model.
    e.g., {f1:new lazy8.chips.Field(...),...} a mapping between field
    names and Field INSTANCES.
    Override this and define model specific mappings in subclasses. */
lazy8.chips.Model.prototype.fields = {
};

/** Define the list of collections constructors known to this model.
    e.g, {my_models:ModelCollection, ...} a mapping betweeen collection names
    and Collection CONSTRUCTORS.
    Names must not conflict with fields because collections and fields are both
    properties of this Model.
    Note that we don't "new" the Collection as each model instance will do that
    for us when the the instance is constructed.
    Override this and define model specific collection constructors in subclasses. */
lazy8.chips.Model.prototype.collections = {
};

/**
 * Returns the id of this Model instance.
 * It prefers a real id, but if none is present, uses the cid, or
 * returns undefined if it is completely free of id-like things.
 *
 * @return {*} The ID value.
 */
lazy8.chips.Model.prototype.get_id = function() {
    if (this.has_id()) {
        return this[this._id_field_name];
    } else if (this.has_cid()) {
        return this._cid;
    } else {
        return undefined;
    }
};

/**
 * Whether this Model has a real id (the field named as the id_field is set)
 */
lazy8.chips.Model.prototype.has_id = function() {
    return this[this._id_field_name] !== undefined;
};

/**
 * Whether this Model has a client generated id (the id_field has not been set by the server)
 */
lazy8.chips.Model.prototype.has_cid = function() {
    return this._cid !== null;
};

/**
 * Merge a chip struct into this Model instance. The chip struct is expected to be a plain
 * Object with a subset of the defined fields for this Model as fields and values for
 * those fields as values.
 * NOTE: It is expected that the chip Object is a plain object, with no modifications
 * to its prototype. All properties (other than builtins) will be considered as fields.
 *
 * @param {Object} chip_struct The chip data to merge into this Model.
 * @param {boolean=} opt_check_required Whether all required fields are verified to
 *   exist in the chip_struct. If a field is missing, an exception is thrown.
 */
lazy8.chips.Model.prototype.merge_chip_struct = function(chip_struct, opt_check_required) {
    if (goog.typeOf(chip_struct) !== "object") {
        lazy8.chips.error('chip_struct must be an Object ' + this);
    }
    // If requested, verify all required fields are in this chip update.
    if (opt_check_required === true) {
        for (var required in this._required_fields) {
            if (chip_struct[required] === undefined) {
                lazy8.chips.error('Field "' + required + '" is a required field in Model ' + this);
            }
        }
    }

    for (var field_name in chip_struct) {
        // If this is a collection field name, pass that part of the chip to the collection
        // to process.
        if (field_name in this.collections) {
            this[field_name].load_from_struct(chip_struct[field_name]);

        // Else this must be a field on this model.
        } else {
            // Raise an error if this field was not defined on this Model.
            this.assertKnownField(field_name);

            // If this field is itself a model handle that case.
            if (field_name in this._model_fields) {
                // If no value exists for this model name then either instantiate or attach instantiated model.
                if (this[field_name] === undefined) {
                    // If the struct value is an instantiated Model instance, assume it was constructed
                    // correctly and store that value
                    if (chip_struct[field_name] instanceof lazy8.chips.Model) {
                        this[field_name] = chip_struct[field_name];
                    // Otherwise construct a new model instance from the model_constructor value.
                    } else {
                        var model_constructor = this._model_fields[field_name];
                        this[field_name] = new model_constructor(chip_struct[field_name]);
                    }
                // Otherwise if there is already a model instance, pass the subset of the chip update down
                // to it to merge.
                } else {
                    this[field_name].merge_chip_struct(chip_struct[field_name], opt_check_required);
                }

          // Otherwise this is a plain old field, store the value.
          } else {
              // FUTURE: Could record and/or dispatch an event when a value changes sharing
              // both the old and new values. This could potentially be done at the collection
              // level as well where if a collection is defined this instance informs its
              // collection it has changed (or been added or deleted) and what fields changed
              // from and to what values.
              this[field_name] = chip_struct[field_name];
          }
       }
    }

    // If we now have a real ID from the server and already had a cid, clear the cid
    // and update the key in any Collection.
    if (this.has_id() && this.has_cid()) {
        // Clear the cid.
        var old_id = this._cid;
        this._cid = null;
        // And inform the Collection to rekey this model.
        if (this._collection !== null) {
            this._collection._child_reindex(old_id, this);
        }
    }
};

/**
 * If the Model is a member of a Collection the Collection will
 * be asked to remove this Model instance.
 */
lazy8.chips.Model.prototype.remove_from_collection = function() {
    if (this._collection !== null) {
        this._collection.remove(this);
    }
};

/**
  * Return a plain Object representation of this Model, ready to be used as JSON.
  */
lazy8.chips.Model.prototype.to_struct = function(opt_fields) {
    var struct = {};
    for (var field in this.fields) {
        if (!this.fields.hasOwnProperty(field)) {
            continue;
        }
        // Skip the id_field for now.
        if (field === this._id_field_name) {
            continue;
        }
        // If the optional field list was provided, only return fields which
        // are in that list.
        if (opt_fields !== undefined && opt_fields.indexOf(field) === -1) {
            continue;
        }
        struct[field] = this[field];
    }
    if (this.has_id()) {
        struct[this._id_field_name] = this.get_id();
    } else if (this.has_cid()) {
        struct['cid'] = this.get_id();
    }
    return struct;
};

lazy8.chips.Model.prototype.toString = function() {
    if (this.constructor.name && this.constructor.name !== "") {
        return "lazy8.chips.Model<" + this.constructor.name + ">";
    // If the model was defined with an anonymous function (e.g foo.Bar = function())
    // instead of with a named function (e.g. foo.Bar = function Bar()) then we cannot
    // return a proper name.
    } else {
        return "lazy8.chips.Model<anonymous constructor>";
    }
};

lazy8.chips.Model.prototype.assertKnownField = function(field) {
    if (!(field in this.fields)) {
        lazy8.chips.error('Field "' + field + '" not defined in ' + this);
    }
};

lazy8.chips.Model.prototype._parseFields = function() {
    var model = this;
    for (var field_name in model.fields) {
        if (!model.fields.hasOwnProperty(field_name)) {
            continue;
        }
        var definition = model.fields[field_name];
        if (definition.id_field) {
            if (model._id_field_name !== null) {
                lazy8.chips.error('Only one id_field allowed. Duplicate: "' + field_name + ' in Model ' + this);
            }
            model._id_field_name = field_name;
            model._allow_cid = definition.allow_cid;
            // id_fields are always required if allow_cid is not set.
            if (definition.allow_cid === false) {
                model._required_fields[field_name] = definition;
            }

        } else {
            if (definition.required === true) {
                model._required_fields[field_name] = definition;
            } else {
                model._optional_fields[field_name] = definition;
            }
        }
        // A child model constructor was defined, save it for when it will be needed.
        if (definition.model_constructor !== null) {
          model._model_fields[field_name] = definition.model_constructor;
        }
        // If the Field implemented a create_computed_field method, run it now.
        definition.create_computed_field(this, field_name);
    }
};


lazy8.chips.Model.prototype._processCollections = function() {
    var model = this;
    for (var collection_name in model.collections) {
        if (!model.collections.hasOwnProperty(collection_name)) {
            continue;
        }
        var collection_constructor = model.collections[collection_name];
        if (collection_name in model.fields) {
            lazy8.chips.error('Collection name conflicts with field name. Name: "' +
                collection_name + ' in Model ' + this);
        }
        // Insert each collection as a top level attribute on this model.
        if (collection_name in model) {
            lazy8.chips.error('Collection name already defined on model. Name: "' +
                collection_name + ' in Model ' + this);
        }
        var collection = new collection_constructor();
        model[collection_name] = collection;
        // Inform the collection that this model is the parent.
        collection._parent = model;
    }
};


/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
lazy8.chips.RootModel = function(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(lazy8.chips.RootModel, lazy8.chips.Model);

/** Define the name of this root node.
    Override this and define a String for each subclass. */
lazy8.chips.RootModel.prototype.root_id = null;

/**
 * Handle a chip update. This includes the chip update type, the path, and the chip update
 * value (struct payload).
 * chip_update properties: action: (a, m, d), path: [Array], value: {Object}, time: {Date}
 *
 * @param {Object} chip_update The chipuodate data to merge into this Model or pass down
 *     the collections hierarchy.
 */
lazy8.chips.RootModel.prototype.handle_chip_update = function(chip_update) {
    if (chip_update.path[0] !== this.root_id) {
        lazy8.chips.warn('Chip update path unknown to this root path: ' + this.root_id + ' ' + this);
        return;
    }

    // Walk the path and find the last model or collection starting at the this root model.
    var node = this;
    var previousNode = node;
    var segment;
    for (i = 0; i < chip_update.path.length; i++) {
        segment = chip_update.path[i];
        // If we are on the root segment, set the node to the root.
        // FUTURE: Should this be an error condition if i != 0?
        if (segment === this.root_id) {
            node = this;
        // Else the path segment might be a collection.
        } else if (node.collections !== undefined && segment in node.collections) {
            node = node[segment];
        // Else the path segment might be a singleton child model (MOD only).
        } else if (node instanceof lazy8.chips.Model && segment in node.fields) {
            node = node[segment];
        // Else the path segment must be a member of a collection.
        } else {
            node = node.get(segment);
            // If this node is not present in the Collection, then this must be an ADD
            // for a new Model in which case the node needs to be the Collection, which
            // is the previousNode in the path.
            // FUTURE: More error checking here.  e.g., this should only happen for an
            // ADD at the end of the path.
            if (node === undefined) {
                node = previousNode;
            }
        }
        previousNode = node;
    }

    // Node should be a valid reference to a Model or Collection.
    if (node === undefined) {
        lazy8.chips.error("Unable to locate node for chip update: " + chip_update.path +
                          " action:" + chip_update.action + " for RootModel " + this);
    }
    // If this is the root node, only allow a MOD chip.
    if ((node === this) && (chip_update.action !== lazy8.chips.MOD)) {
        lazy8.chips.error("Only MOD chips allowed on a root model: " + chip_update.action +
                          " for RootModel " + this);
    }

    switch (chip_update.action) {
        // If this is an add, the node must be a collection.
        case lazy8.chips.ADD:
            // If the last chip segment is a Collection, this is adding a new server
            // created Model.
            if (node instanceof lazy8.chips.Collection) {
                node.add(chip_update.value);
            // Otherwise, if the last chip segment is a Model, then this ADD is the result
            // of a client created Model being persisted and being assigned a real id. In
            // that case, merge_chip will clear the cid and reindex the Model in any Collection.
            } else if (node instanceof lazy8.chips.Model) {
                node.merge_chip_struct(chip_update.value);
            } else {
                lazy8.chips.error("Last chip path segment in a ADD must be a Model " +
                                  "or Collection: " + node + " path:" + chip_update.path +
                                  " for RootModel " + this);
            }
            break;

        // If this is a mod, the node must be a model.
        case lazy8.chips.MOD:
            if (!(node instanceof lazy8.chips.Model)) {
                lazy8.chips.error("Last chip path segment in a MOD must be a Model: " +
                                  node + " path:" + chip_update.path + " for RootModel " + this);
            }
            node.merge_chip_struct(chip_update.value);
            break;

        // If this is a mod, the node must be a model.
        case lazy8.chips.DELETE:
            if (!(node instanceof lazy8.chips.Model)) {
                lazy8.chips.error("Last chip path segment in a DELETE must be a Model: " +
                                  node + " path:" + chip_update.path + " for RootModel " + this);
            }
            node.remove_from_collection();
            break;

        default:
            lazy8.chips.error("Unknown chip action in update: " + chip_update.action +
                              " for RootModel " + this);
    }
};


/**
 * A chip Collection. This Object manages a collection of Model instances, and provides
 * functinoality to search, sort and update those instances.
 *
 * NOTE: When defining a new Collection 'subclass', be sure to use the named function style e.g.:
 *  foo.BarCollection = function BarCollection(chip_struct) {
 *      lazy8.chips.Collection.call(this, chip_struct);
 *  };
 *  goog.inherits(foo.BarCollection, lazy8.chips.Collection);
 *
 * @param {Object=} opt_model_structs The Model instances to initialize this Collection with.
 *  The Object keys are the Model IDs and the values are the Model fields and values.
 * @constructor
 */
lazy8.chips.Collection = function(opt_model_structs) {
    this._models = {};
    // The optional parent of this collection. Expected to be a lazy8.chips.Model instance.
    this._parent = null;
    if (opt_model_structs !== undefined) {
        this.load_from_struct(opt_model_structs);
    }
};

/** Define the Model 'subclass' constructor which is held in this Collection.
    Override this and assign the constructor in subclasses. */
lazy8.chips.Collection.prototype.model_constructor = null;

/**
 * Load all of the Model data from the supplied Object. The Object keys are the Model
 * IDs and the values are the Model fields and values.
 *
 * @param {Object} model_structs The model data to load into the Collection.
 */
lazy8.chips.Collection.prototype.load_from_struct = function(model_structs) {
    for (var model_id in model_structs) {
        this.add(model_structs[model_id]);
    }
};

lazy8.chips.Collection.prototype.toString = function() {
    if (this.constructor.name && this.constructor.name !== "") {
        return "lazy8.chips.Collection<" + this.constructor.name + ">";
    // If the collection was defined with an anonymous function
    // (e.g foo.BarCollection = function()) instead of with a named function
    // (e.g. foo.BarCollection = function BarCollection()) then we cannot
    // return a proper name.
    } else {
        return "lazy8.chips.Collection<anonymous constructor>";
    }
};


/**
 * Helper to assert that the Model type held by this Collection defines the given field.
 *
 * @param {string} field The Model field to check.
 */
lazy8.chips.Collection.prototype.assertKnownField = function(field) {
    this.model_constructor.prototype.assertKnownField(field);
};

/**
 * Returns the Model for the given ID. This will also
 * return the same Model instance if requested to find a given Model instance.
 * Returns undefined if the Model or model_id is not in the collection.
 *
 * @param {lazy8.chips.Model|string} model_or_id The Model instance or
 *     ID value to find.
 * @return {lazy8.chips.Model|undefined} The Model or undefined if not found.
 */
lazy8.chips.Collection.prototype.get = function(model_or_id) {
    if (model_or_id instanceof lazy8.chips.Model) {
        return this._models[model_or_id.get_id()];
    } else {
        return this._models[model_or_id];
    }
};

/**
 * Add the given Model or chip data to the the Collection. It will be keyed using the
 * ID from the Model.
 *
 * @param {lazy8.chips.Model|Object} model_or_chip The Model instance to add or
 *     chip data packed into an Object.
 * @return {lazy8.chips.Model} The Model that was added.
 */
lazy8.chips.Collection.prototype.add = function(model_or_chip) {
    // If the parameter provided is not already a Model, assume it is chip data
    // and pass it through to the constructor.
    var model;
    if (!(model_or_chip instanceof lazy8.chips.Model)) {
        model = new this.model_constructor(model_or_chip);
    // Otherwise the parameter is already a constructed model.
    } else {
        model = model_or_chip;
    }

    if (this.contains(model)) {
        lazy8.chips.error('Model "' + model + '" is already in Collection. [' + model.get_id() + '] ' + this);
    }
    this._models[model.get_id()] = model;
    // Inform the model that it is a member of this collection.
    model._collection = this;
    return model;
};

/**
 * Removes the given Model or ID from the Collection.
 * Does nothing if the Model or model_id is not present in the Collection.
 *
 * @param {lazy8.chips.Model|string} model_or_id The Model instance or
 *     ID value to remove.
 */
lazy8.chips.Collection.prototype.remove = function(model_or_id) {
    if (!this.contains(model_or_id)) {
        lazy8.chips.error('Model "' + model_or_id + '" is not in Collection ' + this);
    }

    if (model_or_id instanceof lazy8.chips.Model) {
        delete this._models[model_or_id.get_id()];
    } else {
        delete this._models[model_or_id];
    }
};

/**
 * Whether the Collection contains the given Model or ID.
 *
 * @param {lazy8.chips.Model|string} model_or_id The Model instance or
 *     ID value to look for.
 * @return {boolean} true if the Model or ID is present.
 */
lazy8.chips.Collection.prototype.contains = function(model_or_id) {
    if (model_or_id instanceof lazy8.chips.Model) {
        return this._models[model_or_id.get_id()] !== undefined;
    } else {
        return this._models[model_or_id] !== undefined;
    }
};

/**
 * Whether the Collection contains any Models.
 *
 * @return {boolean} true if any Model is in the Collection.
 */
lazy8.chips.Collection.prototype.isEmpty = function() {
    return this.any() === undefined;
};

/**
 * Returns the number of Models in the Collection.
 *
 * @return {number} The number of Models in the Collection.
 */
lazy8.chips.Collection.prototype.getCount = function() {
    var count = 0;
    for (var model_id in this._models) {
        count++;
    }
    return count;
};

/**
 * Calls a function for each Model in the Collection.
 *
 * @param {Function} func The function to call for every element. This function
 *     takes 1 argument (the Model). The return value is ignored.
 * @param {Object=} opt_this An optional "this" context for the function.
 */
lazy8.chips.Collection.prototype.forEach = function(func, opt_this) {
    for (var model_id in this._models) {
        func.call(opt_this, this._models[model_id]);
    }
};

/**
 * Returns any Model from the Collection.
 *
 * @return {lazy8.chips.Model|undefined} The Model or undefined if no Models
 *     are in this Collection.
 */
lazy8.chips.Collection.prototype.any = function() {
    for (var model_id in this._models) {
        return this._models[model_id];
    }
    return undefined;
};

/**
 * Call a function for each Model. If any call returns true, some()
 * returns true (without checking the remaining elements). If all calls
 * return false, some() returns false.
 *
 * @param {Function} func The function to call for every Model. This function
 *     takes 1 argument (the Model) and should return a boolean.
 * @param {Object=} opt_this An optional "this" context for the function.
 */
lazy8.chips.Collection.prototype.some = function(func, opt_this) {
    for (var model_id in this._models) {
        var model = this.get(model_id);
        if (func.call(opt_this, model)) {
            return true;
        }
    }
    return false;
};

/**
 * Calls a function for each Model. If all calls return true, every()
 * returns true. If any call returns false, every() returns false and
 * does not continue to check the remaining elements.
 *
 * @param {Function} func The function to call for every Model. This function
 *     takes 1 argument (the Model) and should return a boolean.
 * @param {Object=} opt_this An optional "this" context for the function.
 */
lazy8.chips.Collection.prototype.every = function(func, opt_this) {
    for (var model_id in this._models) {
        var model = this.get(model_id);
        if (!func.call(opt_this, model)) {
            return false;
        }
    }
    return true;
};

/**
 * Calls a function for each Model, and if the function returns true adds that Model
 * to a new array and returns it.
 *
 * @param {Function} func The function to call for every Model. This function takes
 *     1 argument (the Model) and should return a boolean. If the return value is true
 *     the element is added to the result array. If it is false the element is not included.
 * @param {Object=} opt_this An optional "this" context for the function.
 */
lazy8.chips.Collection.prototype.filter = function(func, opt_this) {
    var model_array = [];
    this.forEach(function(model) {
        if (func.call(opt_this, model)) {
            model_array.push(model);
        }
    });
    return model_array;
};

/**
 * Search the Models for the first model that satisfies a given condition and
 * return that element.
 *
 * @param {Function} func The function to call for every element. This function
 *     takes 1 argument (the Model) and should return a boolean.
 * @param {Object=} opt_this An optional "this" context for the function.
 */
lazy8.chips.Collection.prototype.find = function(func, opt_this) {
    for (var model_id in this._models) {
        var model = this.get(model_id);
        if (func.call(opt_this, model)) {
            return model;
        }
    }
    return undefined;
};

/**
 * Search the Models for the last model that satisfies a given condition and
 * return that element.
 *
 * @param {Function} func The function to call for every Model. This function
 *     takes 1 argument (the Model) and should return a boolean.
 * @param {Object=} opt_this An optional "this" context for the function.
 */
lazy8.chips.Collection.prototype.select = function(func, opt_this) {
    var selected = this.any();
    this.forEach(function(model) {
        if (func.call(opt_this, model, selected)) {
            selected = model;
        }
    });
    return selected;
};

/**
 * Returns the "minimum" Model based on the supplied Model field.
 * Minimum is compared using the builtin < operator.
 *
 * @param {string} field The Model field to compare.
 */
lazy8.chips.Collection.prototype.min = function(field) {
    this.assertKnownField(field);
    return this.select(function(current, selected) {
        return (current[field] < selected[field]);
    });
};

/**
 * Returns the "maximum" Model based on the supplied Model field.
 * Maxmimum is compared using the builtin > operator.
 * @param {string} field The Model field to compare.
 */
lazy8.chips.Collection.prototype.max = function(field) {
    this.assertKnownField(field);
    return this.select(function(current, selected) {
        return (current[field] > selected[field]);
    });
};

/**
 * Passes every Model into a function and accumulates the result.
 *
 * @param {Function} func The function to call for every Model. This function
 *     takes 2 arguments (the function's previous result or the initial value,
 *     and the current Model)
 *     function(previousValue, currentModel).
 * @param {*} val The initial value to pass into the function on the first call.
 * @param {Object=} opt_this An optional "this" context for the function.
 * @return {*} Result of evaluating func repeatedly across the values in the Collection.
 */
lazy8.chips.Collection.prototype.reduce = function(func, val, opt_this) {
    var rval = val;
    this.forEach(function(model) {
        rval = func.call(opt_this, rval, model);
    });
    return rval;
};

/**
 * Returns the Models in an unsorted array.
 */
lazy8.chips.Collection.prototype.unsorted = function() {
    var models_array = [];
    var i = 0;
    this.forEach(function(model) {
        models_array[i++] = model;
    });
    return models_array;
};

/**
 * Returns the Models in a sorted array in ascending order using the supplied Model field.
 * If the field is not defined in the Model, an error will occur.
 * Optionally, opt_descend can be set to true and the array will be sorted in descending
 * order. Additionally, opt_compareFn can be defined as the comparison function. If this is
 * defined, opt_descend will be ignored. If no opt_compareFn is specified, elements are
 * compared using the default comparison function, which compares the elements using the
 * built in < and > operators.  This will produce the expected behavior for homogeneous
 * arrays of String(s) and Number(s), unlike the native sort, but will give unpredictable
 * results for heterogenous lists of strings and numbers with different numbers of digits.
 *
 * This sort is not guaranteed to be stable.
 *
 * Description based on goog.array.sort.
 *
 * @param {string} field The Model field to sort on.
 * @param {boolean=} opt_descend If true, sort the array in descending order.
 * @param {Function=} opt_compareFn Optional comparison function by which the
 *     array is to be ordered. Should take 2 Model arguments to compare, and return a
 *     negative number, zero, or a positive number depending on whether the
 *     first argument is less than, equal to, or greater than the second.
 */
lazy8.chips.Collection.prototype.sorted = function(field, opt_descend, opt_compareFn) {
    this.assertKnownField(field);
    var models_array = this.unsorted();
    // If the compareFn was passed in, use that.
    var compareFn = opt_compareFn;
    if (compareFn === undefined) {
        // Otherwise use the default descend compare if requested.
        if (opt_descend === true) {
            compareFn = function(a, b) {
                return a[field] < b[field] ? 1 : a[field] > b[field] ? -1 : 0;
            };
        // Or fallback on the default ascending compare.
        } else {
            compareFn = function(a, b) {
                return a[field] > b[field] ? 1 : a[field] < b[field] ? -1 : 0;
            };
        }
    }
    models_array.sort(compareFn);
    return models_array;
};

/**
 * Inform the Collection that a model that was keyed with a certain id has changed
 * its id. This will almost certainly only be used when a cid'd model comes back
 * from the server with a real id.
 *
 * @param {string} old_id The old id for this model.
 * @param {lazy8.chips.Model} model The Model to rekey. The real id should already be merged.
 * @private
 */
lazy8.chips.Collection.prototype._child_reindex = function(old_id, model) {
    this.remove(old_id);
    this.add(model);
};

/*
* Create a chips manager that handles syncing with the backend and dispatching events to listeners.
* @param {Date} last_seen_chip_time Represents when the latest chip was seen by the client.
* @param {int} fetch_interval The interval to poll for new chips, in milliseconds.
* @param {Function} is_chip_time_newer Function that accepts two chip objects and returns True if
    the first chip is 'newer' than the second chip.
* @constructor
*/
lazy8.chips.Manager = function(last_seen_chip_time, fetch_interval, is_chip_time_newer) {
    this.fetch_url = "delta";
    this.last_seen_chip_time = last_seen_chip_time;
    this.fetch_interval = fetch_interval;
    this.is_chip_time_newer = is_chip_time_newer;
    this.timeout = null;
    this.listeners = [];
    this.bundle_listeners = [];
};

// Annotates data (which should be a js object) with a 'last_seen_chip_time' field,
// which represents the client's last seen chip time.
lazy8.chips.Manager.prototype.insert_last_seen_chip_time = function insert_last_seen_chip_time(struct) {
    struct.chips = this.last_seen_chip_time_query_param();
};

// Returns the last_seen_chip_time as a dict with the expect key name ready to be a
// query parameter.
lazy8.chips.Manager.prototype.last_seen_chip_time_query_param = function last_seen_chip_time_query_param() {
    return {'last_seen_chip_time': this.last_seen_chip_time};
};

// This extracts any possible chips from any JSON payload (not just a sync request).
lazy8.chips.Manager.prototype.process_chips = function process_chips(struct) {
    // When an ajax function returns, merge any chips with the gamestate data.
    if (struct.chips && struct.chips.length) {
        this._dispatch_all(struct.chips);
    }
};

/*
 * Listen for a path prefix change with the given listener code.
 * prefix: array Chips key prefix to match for this listener.
 * listener: function Callback to run if the prefix matches a chip: listener(chip, match)
 * Returns the listener position which can be passed to remove_listener().
 */
lazy8.chips.Manager.prototype.listen = function listen(prefix, listener) {
    var position = this.listeners.length;
    this.listeners.push([prefix, listener]);
    return position;
};

// Remove the listener at the given position, as returned by listen().
lazy8.chips.Manager.prototype.remove_listener = function remove_listener(position) {
    this.listeners[position] = undefined;
};

/*
 * Listen for every "bundle" of chips. This will be fired after a bundle of chips have
 * been processed from the server, e.g. after a fetch chips request.
 * listener: function Callback to run if the prefix matches a chip: listener(chips)
 * Returns the listener position which can be passed to remove_bundle_listener().
 */
lazy8.chips.Manager.prototype.listen_bundle = function listen_bundle(listener) {
    var position = this.bundle_listeners.length;
    this.bundle_listeners.push(listener);
    return position;
};

// Remove the listener at the given position, as returned by listen_bundle().
lazy8.chips.Manager.prototype.remove_bundle_listener = function remove_bundle_listener(position) {
    this.bundle_listeners[position] = undefined;
};

/**
 * Start the sync process with the server, polling for new chip updates.
 * @param {boolean=} opt_synchronous Optionally issue the sync ajax call in a blocking,
 * synchronous manner. Most likely you do not want to do this in a real browser situation,
 * however this functionality is useful when unit testing to guarantee chips are fetched
 * and processed before proceeding.
 */
lazy8.chips.Manager.prototype.sync = function sync(opt_synchronous) {
    var manager = this;
    manager._sync_impl(
        {'last_seen_chip_time': manager.last_seen_chip_time},
        // Success. Process the chips.
        function (data) {
            manager.process_chips(data);
            manager._schedule_sync();
        },
        // Failure. Log the error.
        function (jqXHR, textStatus, errorThrown) {
            manager._schedule_sync();
            console.error("ERROR: Fetching chips failed.", textStatus, errorThrown);
        },
        opt_synchronous
    );
};

// Match a given prefix list against a given path list. The prefix can contain
// wildcards inside of "<>" for any path element. Returns false if there was no
// match or if there was a match returns a "match" object, which contains
// any wildcard matched elements as properties and a suffix property containing
// any remaining path elements not matched explicitly.
// e.g. prefix=['root', 'child', '<wild>'], path=['root', 'child', '12345', 'more'] ->
//    retval={prefix:'more', wild='12345'}
lazy8.chips.Manager.prototype.prefix_match = function(prefix, path) {
    var retval = {}, i;
    if (prefix === undefined || prefix === null) {
        return false;
    }
    for (i = 0; i < prefix.length; i++) {
        if (prefix[i] !== path[i]) {
            if (prefix[i][0] === '<') {
                retval[prefix[i].slice(1, -1)] = path[i];
            } else {
                return false;
            }
        }
    }
    retval.suffix = path.slice(prefix.length);
    return retval;
};

/* Private Methods */

// The AJAX request to sync chips from the server. Factored out for unit testing.
// See .sync() for description of opt_synchronous argument.
lazy8.chips.Manager.prototype._sync_impl = function _sync_impl(json_data, success, error, opt_synchronous) {
    var options = {
        type: 'GET',
        url: this.fetch_url,
        data: json_data,
        dataType: 'json',
        global: false,
        async: true,
        cache: false,
        success: success,
        error: error
    };
    if (opt_synchronous === true) {
        options.async = false;
    }
    jQuery.ajax(options);
};

// Handles the setting up a timer to poll for chip updates from the server.
lazy8.chips.Manager.prototype._schedule_sync = function _schedule_sync() {
    // Use a timeout instead of an interval so that the rate at which fetching happens is
    // more predictable. This also makes it safer if sync() is called more than once by the
    // consumer.
    clearTimeout(this.timeout);
    if (this.fetch_interval) {
        this.timeout = setTimeout(this._sync_cb(), this.fetch_interval);
    }
};

// Returns a function, for use in setTimeout/Interval because those sometimes
// supply unwanted arguments to the called function
lazy8.chips.Manager.prototype._sync_cb = function _sync_cb() {
    var manager = this;
    return function () { manager.sync(); };
};

lazy8.chips.Manager.prototype._dispatch_to_listener = function _dispatch_to_listener(chip) {
    var matched = this._listeners_for_path(this.listeners, chip.path);
    for (var i = 0; i < matched.length; i++) {
        try {
            matched[i][0](chip, matched[i][1]);
        } catch (err) {
            lazy8.chips.warn("Listener error handling chip: " + chip.path);
            throw err;
        }
    }
};

// Dispatch these chips into the listeners one at a time (in order they were sent
// from server)
lazy8.chips.Manager.prototype._dispatch_all = function _dispatch_all(chip_bundle) {
    for (var i = 0; i < chip_bundle.length; i++) {
        var chip = chip_bundle[i];
        // Update the last seen chip time if this chip is 'newer'.
        if (this.is_chip_time_newer(chip.time, this.last_seen_chip_time)) {
            this.last_seen_chip_time = chip.time;
        }

        // Dispatch this chip to any immediate listeners.
        this._dispatch_to_listener(chip);
    }
    // Fire any chip bundles for this entire bundle of chips.
    for (var j = 0; j < this.bundle_listeners.length; j++) {
        try {
            this.bundle_listeners[j](chip_bundle);
        } catch (err) {
            lazy8.chips.warn("Bundle listener error: " + this.bundle_listeners[j]);
            throw err;
        }
    }
};

// Returns a list of lists, the second list is [listener_function, match_object]
// match_object contains any wildcard elements keyed by their name, and any remaining suffix left
// over when matching the chip path.
lazy8.chips.Manager.prototype._listeners_for_path = function(listeners, path) {
    var matched = [];
    for (var i = 0; i < listeners.length; i++) {
        if (listeners[i] === undefined) continue;
        var matches_and_suffix = this.prefix_match(listeners[i][0], path);
        if (matches_and_suffix) {
            matched.push([listeners[i][1], matches_and_suffix]);
        }
    }
    return matched;
};
