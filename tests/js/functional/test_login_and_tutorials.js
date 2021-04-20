casper.test.comment('Test logging into ops and completing tutorials.');

// Constants for this test.
// NOTE: Ideally these would be derived in a more robust manner.
var TUTORIAL_ROVER_ID = 99999;
// A lat/lng pair that is too far from the waypoint to satisfy the target creation tutorial.
var LAT_LNG_TOO_FAR = [-0.0005075303, -179.999328];
// A lat/lng pair that is close enough to the waypoint to satisfy the target creation tutorial.
var LAT_LNG_CLOSE = [-0.0007282185405346223, -179.99915242369474];
// A lat/lng pair that is near the lander on the real map.
// TODO: Pass these coordinates (and yaw?) through from AT_LANDER. In the meantime,
// this is a point facing toward the lander so the direction/yaw does not need to be changed.
var LAT_LNG_LANDER = [6.240573747202986, -109.414378700324];

// The identification rectangle coordinates of the tutorial object rectangles.
var TUT_PLANT_RECT  = [750, 500];
var TUT_ROVER_RECT  = [580, 500];
var TUT_ANIMAL_RECT = [300, 500];
// The identification rectangle coordinates of the lander rectangle.
// TODO: These coordinates should be derived from the debug.rects.SPC_LANDER01 data and
// passed in via the command line.
var LANDER_RECT = [300, 300];

// The initial targets for a new user.
var INITIAL_TARGETS = 4;
// This value is set after gamestate is loaded.
var INITIAL_MESSAGES = null;

casper.start(APPLICATION_URL, function() {
    this.test.assertTitle("Welcome to Extrasolar!");

    // Login to the game.
    tools.login_from_cli();
});

casper.then(function() {
    // Check the gamestate was loaded.
    this.test.assertEvalEquals(function() {
        return ce4.gamestate.user.email;
    }, "testuser@example.com", "ce4.gamestate loaded successfully.");

    // Before the simulator is completed, there should be 0 pictures.
    this.test.assertEvalEquals(function() {
        return ce4.gamestate.user.picture_targets_list().length;
    }, 0, "Expected 0 targets before completing simulator.");

    // Count the number of initial messages.
    INITIAL_MESSAGES = this.evaluate(function() {
        return ce4.gamestate.user.messages.getCount();
    });
    this.test.assert(INITIAL_MESSAGES > 0, "Checking initial message count.");

    // We should start on the mail page.
    this.test.assertTitle("Extrasolar - Mail: Welcome to Extrasolar!");

    // Now click on the Map tab.
    this.clickLabel("Map", "a");
});

casper.then(function() {
    // Welcome dialog visible.
    this.test.assertTitleMatch(/.*Extrasolar - Map/);

    // Set a destination.
    clickNextTutorialStep('#tutorial01-step02', '#tutorial01-step03');
});

casper.then(function() {
    assertNotTutorialStep('#tutorial01-step04-fail');
});

// Attempt to create a target not close enough to the tutorial waypoint.
casper.then(function() {
    tools.drag_target_control_and_wait(LAT_LNG_TOO_FAR[0], LAT_LNG_TOO_FAR[1], TUTORIAL_ROVER_ID, true);
});

// Should see the failure text.
casper.then(function() {
    assertTutorialStep('#tutorial01-step04-fail');
});

// Now create the target close enough to the tutorial waypoint.
// NOTE: Since this location is directly south of the waypoint, the default north
// orientation for the camera direction will satisfy the next step in the tutorial.
// This was done as currently drag and drop is complicated to do in casperjs/phantomjs.
casper.then(function() {
    tools.create_target(LAT_LNG_CLOSE[0], LAT_LNG_CLOSE[1], TUTORIAL_ROVER_ID);
});

casper.then(function() {
    // Direction has been set.
    clickNextTutorialStep('#tutorial01-step07', '#tutorial01-step08');

    // Rover has now moved.
    clickNextTutorialStep('#tutorial01-step08', '#tutorial01-step09', 'PRO_TUT_01_STEP_09');
});

// Now click on the Home tab.
casper.then(function() {
    this.clickLabel("Home", "a");
});

// Since the simulator target thumbnail is inserted into the page, we need to wait for it to appear.
casper.waitForSelector('img[src$="/img/scenes/simulator_photo.jpg"]');

casper.then(function() {
    // Home tab description.
    clickNextTutorialStep('#tutorial03-step01', '#tutorial03-step02');

    // Click the simulator target thumbnail.
    this.click('img[src$="/img/scenes/simulator_photo.jpg"]');
});

casper.then(function() {
    // Page title should change.
    this.test.assertTitle("(1) Extrasolar - Picture Detail");

    // Next step: "Click the [Add Tag] button..."
    waitForTutorial('#tutorial04-step03');
});

casper.then(function() {
    // Click Add Tag button.
    this.click('#id-add-tag');
});

casper.then(function() {
    // "Click and drag the corners of the rectangle..." appears briefly ('#tutorial04-step04') but
    // do not waitForTutorial as on a slower machine that might get missed and cause a timeout.

    // Move the first selection rectangle to the plant.
    tools.move_selection_rect(1, TUT_PLANT_RECT[0], TUT_PLANT_RECT[1]);
});

casper.then(function() {
    // Now add tags and position them for the rover and animal.
    this.click('#id-add-tag');
    tools.move_selection_rect(2, TUT_ROVER_RECT[0], TUT_ROVER_RECT[1]);

    this.click('#id-add-tag');
    tools.move_selection_rect(3, TUT_ANIMAL_RECT[0], TUT_ANIMAL_RECT[1]);

    // How to submit photo.
    // There is a timer waiting to trigger this tutorial text which we will wait for.
    waitForTutorial('#tutorial04-step08');
});

casper.then(function() {
    // Click submit id button.
    this.click('#id-species-submit');
});

casper.then(function() {
    // Full resolution download and points described.
    clickNextTutorialStep('#tutorial04-step09', '#tutorial04-step10');

    // These progress keys are all set at the end of the tutorials.
    assertProgressNotExists('PRO_TUT_01');
    assertProgressNotExists('PRO_TUT_03');
    assertProgressNotExists('PRO_TUT_04');

    // Training Complete! This is the last step, which redirects to Home.
    clickNextTutorialStep('#tutorial04-step10');
});

casper.then(function() {
    assertProgressExists('PRO_TUT_01');
    assertProgressExists('PRO_TUT_03');
    assertProgressExists('PRO_TUT_04');

    // Tutorials done, we are sent to the home page.
    this.test.assertTitleMatch(/.*Extrasolar/);
});

casper.then(function() {
    // Wait for the chip to come in with the new target images.
    casper.waitFor(function check() {
        return this.evaluate(function() {
            return (ce4.gamestate.user.picture_targets_list().length > 0);
        });
    });

    // Check that the initial photos are shown to the user.
    this.test.assertEvalEquals(function() {
        return ce4.gamestate.user.picture_targets_list().length;
    }, INITIAL_TARGETS, "Initial picture targets loaded successfully.");
});

// Now click on the Map tab.
casper.then(function() {
    this.clickLabel("Map", "a");
});

// Now create the target close enough to the lander.
casper.then(function() {
    tools.create_target(LAT_LNG_LANDER[0], LAT_LNG_LANDER[1]);
});

// Return to the Home tab.
casper.then(function() {
    this.clickLabel("Home", "a");
});

var pre_render_values = {};
casper.then(function() {
    // Verify that the new target is in the gamestate.
    this.test.assertEvalEquals(function() {
        return ce4.gamestate.user.picture_targets_list().length;
    }, INITIAL_TARGETS + 1, "New target created successfully.");
    // Wait for the chip to come in which replaces the cid with a real id.
    // This will time out and fail if the chip never arrives.
    casper.waitFor(function check() {
        return this.evaluate(function() {
            return ce4.gamestate.user.picture_targets_list()[0].has_id();
        });
    });

    // Track some data that will change after the target is rendered.
    pre_render_values = this.evaluate(function() {
        return {
            map_tiles: ce4.gamestate.user.map_tiles.getCount(),
            messages: ce4.gamestate.user.messages.getCount(),
            missions: ce4.gamestate.user.missions.getCount(),
            epoch: ce4.gamestate.user.epoch
        };
    });

    // A new message is sent at the end of the tutorials.
    this.test.assertEvalEqual(function() {
        return ce4.gamestate.user.messages.getCount();
    }, INITIAL_MESSAGES + 1, "Checking simulator/tutorial message was sent.");
});

casper.then(function() {
    this.test.assertEval(function() {
        return !ce4.gamestate.user.messages_list()[0].is_read();
    }, "Checking first message is unread.");
});

// The message list is now dynamically constructed so wait for it to be inserted into the DOM.
casper.waitForSelector('table.messages-list');

// Click that first message unread message.
casper.then(function() {
    this.click('table.messages-list tr');
});

// Wait for the message content to be loaded.
casper.waitWhileSelector('#message .message_loading');

casper.then(function() {
    this.test.assertTitle("Extrasolar - Mail: Simulation complete. Issuing rover.");
});

// Verify the message gets read (via a chip coming back in the content load).
casper.then(function() {
    casper.waitFor(function check() {
        return this.evaluate(function() {
            return ce4.gamestate.user.messages_list()[0].is_read();
        });
    });
});

// Now click on the Map tab to see how it handles chips coming in for
// the rendered target.
casper.then(function() {
    this.clickLabel("Map", "a");
});

// Render the just created target.
casper.then(function() {
    tools.render_newest_target();
});

// Assert some data that was changed by the render.
casper.then(function() {
    var post_render_values = this.evaluate(function() {
        return {
            map_tiles: ce4.gamestate.user.map_tiles.getCount(),
            messages: ce4.gamestate.user.messages.getCount(),
            missions: ce4.gamestate.user.missions.getCount(),
            epoch: ce4.gamestate.user.epoch
        };
    });
    this.test.assert(post_render_values.map_tiles > pre_render_values.map_tiles,
        "Check that new map tiles arrived.");
    this.test.assert(post_render_values.messages > pre_render_values.messages,
        "Check that a new message arrived.");
    this.test.assert(post_render_values.missions > pre_render_values.missions,
        "Check that a new species mission was added.");
    this.test.assert(post_render_values.epoch < pre_render_values.epoch,
        "Check that epoch decreased.");
});

casper.then(function() {
    this.clickLabel("Home", "a");
});

casper.then(function() {
    this.test.assertEval(function() {
        return !ce4.gamestate.user.picture_targets_list()[0].hasBeenViewed();
    }, "Checking newest target is unviewed.");
});

// Click the first target thumbnail.
casper.then(function() {
    this.click('#gallery-thumbnails li.bigger a');
});

casper.then(function() {
   this.test.assertTitle("(1) Extrasolar - Picture Detail");
});

// Verify the target gets marked viewed.
casper.then(function() {
    casper.waitFor(function check() {
        return this.evaluate(function() {
            return ce4.gamestate.user.picture_targets_list()[0].hasBeenViewed();
        });
    });
    tools.echo_pass("Checking newest target is now viewed.");
});

// Verify the lander has not been identified yet.
casper.then(function() {
    this.test.assertEval(function() {
        return !ce4.gamestate.user.species.has_key("SPC_LANDER01");
    }, "Checking lander has not been identified.");
});

// Click Add Tag button.
casper.then(function() {
    this.click('#id-add-tag');
});

// Move the selection rectangle to the lander
casper.then(function() {
    tools.move_selection_rect(1, LANDER_RECT[0], LANDER_RECT[1]);
});

// Click submit id button.
casper.then(function () {
    this.click('#id-species-submit');
});

// Verify the lander gets identified (via a chip coming back in the tag submit).
casper.then(function() {
    casper.waitFor(function check() {
        return this.evaluate(function() {
            return ce4.gamestate.user.species.has_key("SPC_LANDER01");
        });
    });
    tools.echo_pass("Checking lander has now been identified.");
});

// Now click on the Lander catalog link.
casper.then(function() {
    this.click('#id-species-identified li a');
});

casper.then(function() {
    this.test.assertTitleMatch(/.*Extrasolar - Species Catalog/);
});

// And finally make sure TUT01 is done.
casper.then(function() {
    this.test.assertEval(function() {
        return ce4.gamestate.user.missions.for_definition("MIS_TUT01").done === 1;
    }, "Checking TUT01 is now done.");
});

casper.run(function() {
    this.test.done();
});

// ======== Test Utilities ========

// This is required as all the tutorial step buttons are in the DOM but we only
// want to click the :visible one. casperjs has poor visibility filtering functionality
// so use jQuery instead.
var clickNextTutorialStep = function(current_step, next_step, progress_key) {
    assertTutorialStep(current_step);
    if (next_step !== undefined) {
        assertNotTutorialStep(next_step);
    }
    if (progress_key !== undefined) {
        assertProgressNotExists(progress_key);
    }

    casper.test.assertEvalEquals(function() {
        return $('button.gradient-button-tutorial:visible').click().length;
    }, 1, "Clicked next tutorial step " + next_step);

    if (progress_key !== undefined) {
        assertProgressExists(progress_key);
    }
    // If there is not next_step assume this is the last step which means
    // the current_step will not go invisible.
    if (next_step !== undefined) {
        assertNotTutorialStep(current_step);
        assertTutorialStep(next_step);
    }
};

var assertTutorialStep = function(step_id, opt_expected) {
    var visible = isTutorialStepVisible(step_id);
    casper.test.assertEquals(visible, true, "Tutorial step " + step_id + " visible.");
};
var assertNotTutorialStep = function(step_id, opt_expected) {
    var visible = isTutorialStepVisible(step_id);
    casper.test.assertEquals(visible, false, "Tutorial step " + step_id + " not visible.");
};
var isTutorialStepVisible = function(step_id) {
    var is_hidden = casper.evaluate(function(step_id) {
        var step$ = $(step_id);
        if (step$.length === 0) {
            throw new Error("Cannot find tutorial step: " + step_id);
        }
        return step$.css("display") === "none";
    }, {step_id:step_id});
    return !is_hidden;
};
var waitForTutorial = function(step_id) {
    casper.waitFor(function check() {
        return isTutorialStepVisible(step_id);
    }, undefined, function timeout() {
        casper.test.fail("Timed out waiting for tutorial step " + step_id);
    });
};

var assertProgressExists = function(progress_key) {
    casper.waitFor(function check() {
        return casper.evaluate(function(progress_key) {
            return ce4.gamestate.user.progress.contains(progress_key);
        }, {progress_key:progress_key});
    }, function then() {
        casper.test.assert(true, "Has progress key " + progress_key);
    }, function timeout() {
        casper.test.fail("Does not have progress key " + progress_key);
    });
};
var assertProgressNotExists = function(progress_key) {
    var contains = casper.evaluate(function(progress_key) {
        return ce4.gamestate.user.progress.contains(progress_key);
    }, {progress_key:progress_key});
    casper.test.assert(!contains, "Should not have progress key " + progress_key);
};
