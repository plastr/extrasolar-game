function chips_tests() {
    module("Chips");

    goog.require('lazy8.chips');
    goog.require('lazy8.chips.Model');
    goog.require('lazy8.chips.RootModel');
    goog.require('lazy8.chips.ChipsError');
    goog.require('lazy8.chips.Field');
    goog.require('lazy8.chips.Manager');
    goog.require('ce4.util');

    test("prefix_match", function() {
        var pm = lazy8.chips.Manager.prototype.prefix_match;
        // prefix, path
        deepEqual(pm(["a"], ["a","b"]), 
            {suffix: ["b"]}, "true prefix");
        deepEqual(pm(["a", "b"], ["a","b"]), 
            {suffix: []}, "full-match prefix");
        equal(pm(["b"], ["a","b"]), false, "non-matching prefix");
        deepEqual(pm([], ["a", "b"]), 
            {suffix:  ["a", "b"]}, "empty prefix");
        deepEqual(pm(null, ["a", "b"]), false, "null prefix");
        deepEqual(pm(undefined, ["a", "b"]), false, "undefined prefix");
    });

    test("wildcard match", function() {
        var pm = lazy8.chips.Manager.prototype.prefix_match;
        // prefix, path
        deepEqual(pm(['<wild>'], ["a","b"]), 
            {wild: 'a', suffix: ["b"]}, "top-level wildcard");
        deepEqual(pm(['a', '<duh>'], ["a","b"]), 
            {duh: 'b', suffix: []}, "second-level wildcard");
        equal(pm(['a', '*'], ["a"]), false, "missing segment");
        deepEqual(pm(['a', '<glp>', 'c'], ['a','b','c']), 
            {glp:'b', suffix:[]}, "middle wildcard");
    });

    test("listeners", function() {
        var manager = new lazy8.chips.Manager(current_last_seen_chip_time(), 10000, ce4.util.is_chip_time_newer);
        var test_chip = mock_chip(lazy8.chips.ADD, ["root"], {name: "testing"});
        var test_chips = {chips: [test_chip]};
        manager._sync_impl = function(json_data, success, failure) {
            success(test_chips);
        };
        var results = [];
        equal(manager.listeners.length, 0);
        var listener_id = manager.listen(["root"], function(chip, match) {
            results.push(chip.path);
        });
        equal(manager.listeners.length, 1);
        manager.listen(["<wild>"], function(chip, match) {
            results.push(chip.path);
        });
        manager.sync();
        equal(results.length, 2);
        equal(results[0][0], ["root"]);
        // TODO: Check the match result.
        equal(results[1][0], ["root"]);

        manager.remove_listener(listener_id);
        manager.sync();
        // Only one additional callback should have triggered.
        equal(results.length, 3);
    });

    test("bundle listeners", function() {
        var manager = new lazy8.chips.Manager(current_last_seen_chip_time(), 10000, ce4.util.is_chip_time_newer);
        var test_chips = {chips: [
                            mock_chip(lazy8.chips.ADD, ["root"], {name: "testing"}),
                            mock_chip(lazy8.chips.ADD, ["root", "collection", "12345"], {name: "old"}),
                            mock_chip(lazy8.chips.MOD, ["root", "collection", "12345"], {name: "new"}),
                            mock_chip(lazy8.chips.ADD, ["root", "other_collection", "54321"], {name: "other"})
                         ]};
        manager._sync_impl = function(json_data, success, failure) {
            success(test_chips);
        };
        var pm = lazy8.chips.Manager.prototype.prefix_match;

        var results = [];
        manager.listen_bundle(function(chips) {
            for (var i = 0; i < chips.length; i++) {
                var chip = chips[i];
                var matches_and_suffix = pm(["root", "collection", "<wild>"], chip.path);
                if (matches_and_suffix && matches_and_suffix.suffix.length === 0) {
                    results.push(chip);
                }
            }
        });
        manager.sync();
        // Verify that only exact matches fire.
        equal(results.length, 2);
    });

    /**
     * @constructor
     * @extends {lazy8.chips.Model}
     */
    TestModel = function(chip_struct) {
        lazy8.chips.Model.call(this, chip_struct);
    };
    goog.inherits(TestModel, lazy8.chips.Model);

    /** @override */
    TestModel.prototype.fields = {
        model_id: new lazy8.chips.Field({id_field:true}), // always required
        f1: new lazy8.chips.Field({required:true}),
        f2: new lazy8.chips.Field({required:false})
    };

    // Example method.
    TestModel.prototype.f1_value = function() {
        return "Value: " + this.f1;
    };

    test("Model constructor and merge chip", function() {
        var chip_struct = {'model_id':'uuid-12345', 'f1': 'orig_value'};
        var model = new TestModel(chip_struct);
        equal(model.f1, 'orig_value');
        equal(model.f1_value(), 'Value: orig_value');
        equal(model.get_id(), 'uuid-12345');

        chip_struct = {'f1': 'new_value'};
        model.merge_chip_struct(chip_struct);
        equal(model.f1, 'new_value');

        chip_struct = {'bogus': 'bogus_field'};
        raises(function() {
            model.merge_chip_struct(chip_struct);
        }, lazy8.chips.ChipsError);

        // f1 is a required field.
        chip_struct = {'model_id':'uuid-12345'};
        raises(function() {
            model = new TestModel(chip_struct);
        }, lazy8.chips.ChipsError);

        // id_field is a required field.
        chip_struct = {'f1':'new_value'};
        raises(function() {
            model = new TestModel(chip_struct);
        }, lazy8.chips.ChipsError);
    });

    /**
     * @constructor
     * @extends {lazy8.chips.Model}
     */
    TestModelCID = function(chip_struct) {
        lazy8.chips.Model.call(this, chip_struct);
    };
    goog.inherits(TestModelCID, lazy8.chips.Model);

    /** @override */
    TestModelCID.prototype.fields = {
        model_id: new lazy8.chips.Field({id_field:true, allow_cid:true}),
        f1: new lazy8.chips.Field({required:true})
    };

    test("Model with cid allowable id_field", function() {
        var model = new TestModelCID({'model_id':'uuid-12345', 'f1': 'orig_value'});
        ok(model.has_id());
        equal(model.has_cid(), false);
        equal(model.get_id(), 'uuid-12345');
        model = new TestModelCID({'f1': 'orig_value'});
        ok(model.has_cid());
        equal(model.has_id(), false);
        equal(model.get_id().substring(0, 3), 'cid');
        deepEqual(model.to_struct(), {cid:model.get_id(), f1:'orig_value'});

        // Perform a chip update which should replace the CID.
        model.merge_chip_struct({'model_id':'uuid-12345', 'f1': 'new_value'});
        ok(model.has_id());
        equal(model.has_cid(), false);
        equal(model.get_id(), 'uuid-12345');
        deepEqual(model.to_struct(), {model_id:'uuid-12345', f1:'new_value'});
    });

    /**
     * @constructor
     * @extends {lazy8.chips.Collection}
     */
    TestCollection = function(chip_structs) {
        lazy8.chips.Collection.call(this, chip_structs);
    };
    goog.inherits(TestCollection, lazy8.chips.Collection);

    /** @override */
    TestCollection.prototype.model_constructor = TestModel;

    test("Collection constructor and accessors", function() {
        var chip_structs = {'uuid-12345': {'model_id':'uuid-12345', 'f1': 'orig_value'}};
        var first_model, second_model, found;

        // Test get(). Collection from structs.
        var collection = new TestCollection(chip_structs);
        equal(collection.isEmpty(), false);
        first_model = collection.get('uuid-12345');
        equal(first_model.f1, 'orig_value');
        found = collection.get(first_model);
        equal(found.f1, 'orig_value');
        found = collection.get('bogus_id');
        equal(found, undefined);

        // Test add(), contains(), getCount() and isEmpty(). Empty initial Collection.
        second_model = test_model('uuid-34512', 'new_value');
        collection = new TestCollection();
        equal(collection.getCount(), 0);
        equal(collection.isEmpty(), true);
        collection.add(second_model);
        equal(collection.getCount(), 1);
        equal(collection.isEmpty(), false);
        found = collection.get('uuid-34512');
        equal(found.f1, 'new_value');
        ok(collection.contains('uuid-34512'));
        ok(collection.contains(found));
        raises(function() {
            collection.add(second_model);
        }, lazy8.chips.ChipsError);

        // Test remove() with model_id
        collection.remove('uuid-34512');
        raises(function() {
            collection.remove('uuid-34512');
        }, lazy8.chips.ChipsError);
        equal(collection.contains('uuid-34512'), false);

        // Test remove() with model and add() with chip value
        collection.add({'model_id':'uuid-34512', 'f1': 'orig_value'});
        second_model = collection.get('uuid-34512');
        collection.remove(second_model);
        raises(function() {
            collection.remove(second_model);
        }, lazy8.chips.ChipsError);
        equal(collection.contains(second_model), false);
    });

    test("Collection iterations", function() {
        var test_count = 6;
        var collection = new TestCollection();
        for (var i = 0; i < test_count; i++) {
            var model_id = 'uuid-1234' + i;
            collection.add(test_model(model_id, i));
        }

        var each_count, found, result, expected, model_array;

        // Test forEach()
        each_count = 0;
        collection.forEach(function(model) {
            each_count++;
        });
        equal(each_count, test_count);

        // Test any()
        found = collection.any();
        ok(found);

        // Test some()
        result = collection.some(function(model) {
            return (model.f1 > 3);
        });
        ok(result);
        result = collection.some(function(model) {
            return (model.f1 > test_count);
        });
        equal(result, false);

        // Test every()
        result = collection.every(function(model) {
            return (model.f1 < test_count );
        });
        ok(result);
        result = collection.every(function(model) {
            return (model.f1 > 3);
        });
        equal(result, false);

        // Test filter()
        model_array = collection.filter(function(model) {
            return model.model_id === 'uuid-12344';
        });
        equal(model_array.length, 1);
        equal(model_array[0].model_id, 'uuid-12344');

        // Test find()
        found = collection.find(function(model) {
            return model.f1 > 3;
        });
        ok(found);
        found = collection.find(function(model) {
            return model.f1 > 100;
        });
        equal(found, undefined);

        // Test select()
        found = collection.select(function(current, selected) {
            return (current.get_id() === 'uuid-12344');
        });
        equal(found.get_id(), 'uuid-12344');

        // Test min()
        found = collection.min('f1');
        equal(found.f1, 0);
        raises(function() {
            collection.min('bogus_field');
        }, lazy8.chips.ChipsError);

        // Test max()
        found = collection.max('f1');
        equal(found.f1, test_count - 1);
        raises(function() {
            collection.max('bogus_field');
        }, lazy8.chips.ChipsError);

        // Test reduce()
        result = collection.reduce(function(rval, model) {
            return model.f1 + rval;
        }, 0);
        equal(result, 15);

        // Test unsorted()
        model_array = collection.unsorted();
        equal(model_array.length, test_count);

        // Test sorted()
        model_array = collection.sorted('f1');
        for (var j = 0; j < model_array.length; j++) {
            equal(model_array[j].f1, j);
        }
        model_array = collection.sorted('f1', true);
        expected = (model_array.length - 1);
        for (var k = 0; k < model_array.length; k++) {
            equal(model_array[k].f1, expected--);
        }
        raises(function() {
            collection.sorted('bogus_field');
        }, lazy8.chips.ChipsError);
    });

    /**
     * @constructor
     * @extends {TestModel}
     */
    TestParentModel = function(chip_struct) {
        TestModel.call(this, chip_struct);
    };
    goog.inherits(TestParentModel, TestModel);

    /** @override */
    TestParentModel.prototype.collections = {
        testmodels: TestCollection
    };

    test("Model with collections", function() {
        var parent = new TestParentModel({'model_id':'uuid-12345', 'f1':'orig_value'});
        ok(parent.collections.testmodels);
        ok(parent.testmodels);
        // Verify the collection parent is set correctly.
        ok(parent.testmodels._parent === parent);

        // Add a child to the collection. It should have its _collection attribute set to
        // the parent.
        var model = test_model('uuid-34512', 'child_value');
        ok(model._collection === null);
        parent.testmodels.add(model);
        ok(model._collection === parent.testmodels);
    });

    test("Load initial chip data with model and collection.", function() {
        var chip_struct = {'model_id':'uuid-12345', 'f1':'new_value', 'testmodels':
            {'uuid-34512': {'model_id':'uuid-34512', 'f1':'child_value'}}};
        var parent = new TestParentModel(chip_struct);
        equal(parent.f1, 'new_value');
        var child = parent.testmodels.get('uuid-34512');
        equal(child.f1, 'child_value');
    });

    /**
     * @constructor
     * @extends {lazy8.chips.Collection}
     */
    TestCollectionCID = function(chip_structs) {
        lazy8.chips.Collection.call(this, chip_structs);
    };
    goog.inherits(TestCollectionCID, lazy8.chips.Collection);

    /** @override */
    TestCollectionCID.prototype.model_constructor = TestModelCID;

    /**
     * @constructor
     * @extends {lazy8.chips.RootModel}
     */
    TestRootModel = function(chip_struct) {
        lazy8.chips.RootModel.call(this, chip_struct);
    };
    goog.inherits(TestRootModel, lazy8.chips.RootModel);

    /** @override */
    TestRootModel.prototype.fields = {
        f1: new lazy8.chips.Field({required:true}),
        f2: new lazy8.chips.Field({required:false})
    };

    /** @override */
    TestRootModel.prototype.root_id = "testroot";

    /** @override */
    TestRootModel.prototype.collections = {
        testmodels: TestCollection,
        testmodelscid: TestCollectionCID
    };

    test("Handle full chip update with root model and collection.", function() {
        var root = new TestRootModel({'f1':'orig_value'});
        var test_chip, child, old_id;

        // Modify the root element.
        test_chip = mock_chip(lazy8.chips.MOD, ['testroot'], {'f1':'new_value'});
        root.handle_chip_update(test_chip);
        equal(root.f1, 'new_value');

        // Cannot add or delete the root.
        raises(function() {
            root.handle_chip_update(mock_chip(lazy8.chips.ADD, ['testroot'], {}));
        }, lazy8.chips.ChipsError);
        raises(function() {
            root.handle_chip_update(mock_chip(lazy8.chips.DELETE, ['testroot'], {}));
        }, lazy8.chips.ChipsError);

        // Add a model to the collection.
        test_chip = mock_chip(lazy8.chips.ADD, ['testroot', 'testmodels', 'uuid-34512'],
            {'model_id':'uuid-34512', 'f1':'child_value'});
        root.handle_chip_update(test_chip);
        child = root.testmodels.get('uuid-34512');
        equal(child.f1, 'child_value');

        // Modify a model in the collection.
        test_chip = mock_chip(lazy8.chips.MOD, ['testroot', 'testmodels', 'uuid-34512'],
            {'f1':'child_new_value'});
        root.handle_chip_update(test_chip);
        child = root.testmodels.get('uuid-34512');
        equal(child.f1, 'child_new_value');

        // Delete a model in the collection.
        test_chip = mock_chip(lazy8.chips.DELETE, ['testroot', 'testmodels', 'uuid-34512'], {});
        root.handle_chip_update(test_chip);
        child = root.testmodels.get('uuid-34512');
        equal(child, undefined);

        // Provide a bad chip path by trying to modify the just deleted model.
        raises(function() {
            test_chip = mock_chip(lazy8.chips.MOD, ['testroot', 'testmodels', 'uuid-34512'],
                {'f1':'child_new_value'});
            root.handle_chip_update(test_chip);
        }, lazy8.chips.ChipsError);

        // Add a model with a cid and then update it 'from the server' with the real id.
        // The cid should no longer be in the Collection.
        child = new TestModelCID({'f1': 'orig_value'});
        ok(child.has_cid());
        equal(child.has_id(), false);
        root.testmodelscid.add(child);
        old_id = child.get_id();
        ok(root.testmodelscid.contains(old_id));

        test_chip = mock_chip(lazy8.chips.ADD, ['testroot', 'testmodelscid', child.get_id()],
            {'model_id':'uuid-54321', 'f1':'new_value'});
        root.handle_chip_update(test_chip);
        child = root.testmodelscid.get(child.get_id());
        ok(child.has_id());
        equal(child.has_cid(), false);
        equal(child.f1, 'new_value');
        equal(root.testmodelscid.contains(old_id), false);
    });

    /**
     * @constructor
     * @extends {lazy8.chips.Model}
     */
    TestModelSingleton = function(chip_struct) {
        lazy8.chips.Model.call(this, chip_struct);
    };
    goog.inherits(TestModelSingleton, lazy8.chips.Model);

    /** @override */
    TestModelSingleton.prototype.fields = {
        child_id: new lazy8.chips.Field({id_field:true}),
        f1: new lazy8.chips.Field({required:true})
    };

    // Example method.
    TestModelSingleton.prototype.is_child = function() {
        return 'am_child';
    };

    /**
     * @constructor
     * @extends {lazy8.chips.RootModel}
     */
    TestRootModelSingletonChild = function(chip_struct) {
        lazy8.chips.RootModel.call(this, chip_struct);
    };
    goog.inherits(TestRootModelSingletonChild, lazy8.chips.RootModel);

    /** @override */
    TestRootModelSingletonChild.prototype.fields = {
        f1: new lazy8.chips.Field({required:true}),
        child: new lazy8.chips.Field({required:true, model_constructor:TestModelSingleton})
    };

    /** @override */
    TestRootModelSingletonChild.prototype.root_id = "testroot";

    test("Handle chip update with root model and singleton child model.", function() {
        var child = new TestModelSingleton({'child_id':'child', 'f1':'orig_value'});
        var root = new TestRootModelSingletonChild({'f1':'orig_value', 'child':child});

        // Modify the child element.
        var test_chip = mock_chip(lazy8.chips.MOD, ['testroot', 'child'], {'child_id':'child', 'f1':'new_value'});
        root.handle_chip_update(test_chip);
        equal(child.f1, 'new_value');
    });

    test("Handle initial creation from struct of root model and singleton child model.", function() {
		var chip_struct = {'f1':'orig_value', 'child':{'child_id':'child', 'f1':'orig_value'}}
        var root = new TestRootModelSingletonChild(chip_struct);
        equal(root.child.child_id, 'child');
        equal(root.child.f1, 'orig_value');
		// Run a method on the child model object to verify that constructor class was used
		// when initializing the field on the root object.
		equal(root.child.is_child(), 'am_child');

		// Test whether merging in a chip update also works.
        var test_chip = mock_chip(lazy8.chips.MOD, ['testroot', 'child'], {'child_id':'child', 'f1':'new_value'});
        root.handle_chip_update(test_chip);
        equal(root.child.f1, 'new_value');

		// And test whether we can merge a chip struct directly onto the root.
		var chip_struct = {'child':{'child_id':'child', 'f1':'third_value'}}
        root.merge_chip_struct(chip_struct);
        equal(root.child.f1, 'third_value');

		// And test whether we can merge a chip struct directly onto the child.
		var chip_struct = {'f1': 'fourth_value'};
		root.child.merge_chip_struct(chip_struct);
		equal(root.child.f1, 'fourth_value');
    });
};

function test_model(model_id, f1, f2) {
    return new TestModel({'model_id':model_id, 'f1':f1, 'f2':f2});
};

// Return a last_seen_chip_time/chip.time compatible value
// which is 'now' in microseconds as a string.
function current_last_seen_chip_time() {
    var now = new Date();
    var micros = now.getTime() * 1000;
    return micros.toString();
};

function mock_chip(action, path, value) {
    return {
        action: action, // a, m, d
        path: path, // array
        value: value, // dict
        time: current_last_seen_chip_time() // string microseconds since epoch
    };
};
