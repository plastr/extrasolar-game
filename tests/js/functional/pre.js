// This pre.js file is meant to be run with 'casperjs test --pre=pre.js' to provide
// common useful functionality and values for our functional Javascript tests as
// run from the webtest harness.

// Provide the webtest supplied application root URL in the APPLICATION_URL global variable.
var system = require('system');
var APPLICATION_URL = system.env.APPLICATION_URL;

// A namespace for useful testing tools.
var tools = {};

// On slower machines the default timeout of 5 seconds is a bit too short
// for some of our tests so raise that a number of seconds.
casper.options.waitTimeout = 10000;

// Login to the game using credentials provided from the command line.
// Assumes the browser is currently not logged in and on the login (root /) location.
// Expects login_email and login_password to be provided to the test via the command line.
tools.login_from_cli = function() {
    var login_email = casper.cli.options.login_email;
    var login_password = casper.cli.options.login_password;
    if (login_email === undefined || login_password === undefined) {
        var options = require("utils").serialize(casper.cli.options);
        casper.test.fail("No username or password provided via the command line " + options);
        casper.test.done();
    }

    casper.fill("form#form_login", {
        "login_email":    login_email,
        "login_password": login_password
    }, true);
};

// Create a target marker on the map at the given latitude and longitude for the given rover_id.
// NOTE: In the future arrival_time and direction should be provided as arguments. Currently
// this function accepts the defaults for arrival_time and direction.
// NOTE: This function MUST be called at the 'top level' of the test code, as it uses waitFor
// to make sure all the UI event loop business has finished before proceeding with the tests.
tools.create_target = function(lat, lng, rover_id) {
    tools.drag_target_control_and_wait(lat, lng, rover_id);

    var clickNextTargetStep = function() {
        casper.test.assertEvalEqual(function() {
            return $('#wizardcontent button:visible:last').click().length;
        }, 1, "Clicked next target creation step.");
    };

    casper.then(function() {
        // Accept the default north direction.
        clickNextTargetStep();

        // Accept the default time of day.
        clickNextTargetStep();

        // Accept the default target options.
        clickNextTargetStep();
    });
};

// Drag the rover drag marker to the provided latitude and longitude on the map which triggers
// the target creation wizard.
// If no rover_id parameter is supplied, the current 'active' rover is used.
// This function emulates the drag and drop events because casperjs/phantomjs do not currently
// implement these events with their the mouse event systems.
tools.drag_target_control_and_wait = function(lat, lng, rover_id, no_wait) {
    casper.waitFor(function check() {
        return this.evaluate(function(lat, lng, rover_id) {
            // If no rover_id was supplied, use the current active rover.
            if (rover_id === undefined) {
                rover_id = ce4.gamestate.user.sorted_rovers(true)[0].rover_id;
            }
            var m = ce4.ui.leaflet.markers.drag_markers[rover_id].marker;

            // Simulate the drag start/dragging/dragend events.
            var latlng = new L.LatLng(lat, lng);
            m.fire('dragstart');
            m.fire('drag');
            m.setLatLng(latlng);
            m.fire('drag');
            m.fire('dragend');
            return m;
        }, {lat:lat, lng:lng, rover_id:rover_id});
    });

    if (no_wait !== true) {
        casper.waitForSelector('#direction-controls1');
    }
};

// Move the given bocks selection rectangle to the new x and y coordinates. The provided
// index value corresponds to the rectangle index number as tracked by bochs.
tools.move_selection_rect = function(index, x, y) {
    var tracker = 'div.bocks-tracker';
    var selection = '.bocks-selection:nth-of-type('+index+')';
    casper.waitFor(function find_tracker_and_selection() {
        return this.evaluate(function(tracker, selection) {
            return ($(tracker).length === 1 && $(selection).length === 1);
        }, {tracker:tracker, selection:selection});
    }, undefined, function timeout() {
        casper.test.fail("Timed out waiting bocks selection rect " + index);
    });

    var results = [];
    results.push(casper.mouseEvent('mousedown', selection));
    results.push(casper.mouseEvent('mouseover', tracker));
    results.push(tools._mouseEventXY('mousemove', tracker, x, y));
    results.push(casper.mouseEvent('mouseup', tracker));
    results.push(casper.mouseEvent('mouseout', tracker));
    for (var i = 0; i < results.length; i++) {
        if (!results[i]) {
            casper.test.fail("Mouse event for selection rectangle failed " + results);
        }
    }
};

// Signal the test harness to render the newest target and advance the game to that targets
// arrival time by running deferred actions and activating chips.
tools.render_newest_target = function() {
    casper.then(function() {
        // Verify the newest target has not been processed and the next newest has been processed.
        casper.test.assertEval(function() {
            return ce4.gamestate.user.picture_targets_list()[0].processed === 0 &&
                   ce4.gamestate.user.picture_targets_list()[1].processed === 1;
        }, "Checking that the newest target has not been processed.");

        // Calculate how far in the future the target will be arriving.
        var travel_time = this.evaluate(function() {
            var target = ce4.gamestate.user.picture_targets_list()[0];
            return target.arrival_time - target.start_time;
        });

        // Signal the test harness to render the newest target.
        this.echo("TEST.CMD RENDER TARGET");
        // And to advance the game to the arrival time of that target.
        this.echo("TEST.CMD ADVANCE GAME [" + travel_time + "]");

        // And now wait for the rendered target chip to come back.
        casper.waitFor(function check() {
            return casper.evaluate(function() {
                // Run the fetch chips call synchronously as the target chips were
                // activated to some time in the next few seconds so we will have to try
                // a few times in row with the fetch to be sure we see those chips.
                ce4.chips.sync(true);
                return ce4.gamestate.user.picture_targets_list()[0].processed === 1;
            });
        });
    });

    casper.then(function() {
        casper.test.assertEval(function() {
            return ce4.gamestate.user.picture_targets_list()[0].processed === 1;
        }, "Checking that the newest target has been processed.");
    });
};

// Echo a message to the console which looks identical to an assertion's PASS
// message on success. Useful if a waitFor was used as an assertion and echoing
// a message would be helpful documentation.
tools.echo_pass = function(message) {
    var style = 'INFO';
    var status = casper.test.options.passText;
    var c = casper.getColorizer();
    casper.echo([c.colorize(status, style), casper.test.formatMessage(message)].join(' '));
};

// Fump a screenshot of what the viewport looks like. Optionally pass in the
// filename for the screenshot, defaults to screenshot.png.
tools.screenshot = function(opt_filename) {
    casper.then(function() {
        var filename = opt_filename || "screenshot.png";
        casper.capture(filename);
    });
};

// Implement a version of casper.mouseEvent which takes an x and y coordinate for the mouse event to
// occur at so we can issue a mousemoved event on a given selector but at a new location.
// NOTE: Use casper.mouseEvent if at all possible instead of this function.
tools._mouseEventXY = function(type, selector, x, y) {
    var eventSuccess = casper.evaluate(function(type, selector, x, y) {
        var elem = __utils__.findOne(selector);
        if (!elem) {
            __utils__.log("mouseEvent(): Couldn't find any element matching '" + selector + "' selector", "error");
            return false;
        }
        try {
            var evt = document.createEvent("MouseEvents");
            evt.initMouseEvent(type, true, true, window, 1, 1, 1, x, y, false, false, false, false, 0, elem);
            elem.dispatchEvent(evt);
            return true;
        } catch (e) {
            __utils__.log("Failed dispatching " + type + " mouse event on document: " + e, "error");
            return false;
        }
    }, {
        type: type,
        selector: selector,
        x: x, y: y
    });
    return eventSuccess;
};

// Enable this code to print all console messages generated by the client 'browser'
// in the casperjs/phantomjs system to stdout.
casper.on('remote.message', function(message) {
    console.log("BROWSER: " + message);
});

// If a page.error event happens, which is an exception in the client browser code,
// then abort this test and print a backtrace.
casper.on("page.error", function(msg, backtrace) {
    var line = 0;
    try {
        line = backtrace[0].line;
    } catch (e) {}
    this.test.uncaughtError(msg, this.test.currentTestFile, line);

    // Code lifted from 'error' handler in casper.js.
    var c = this.getColorizer();
    backtrace.forEach(function(item) {
        var message = item.file + ":" + c.colorize(item.line, "COMMENT");
        if (item['function']) {
            message += " in " + c.colorize(item['function'], "PARAMETER");
        }
        console.error("  " + message);
    });

    // Abort any further tests if there was an exception at this stage in the suite.
    this.test.done();
});

// If a waitFor() call times out, fail the test suite.
casper.on("waitFor.timeout", function() {
    casper.test.fail("A waitFor call timed out.");
    casper.test.done();
});

casper.test.done();
