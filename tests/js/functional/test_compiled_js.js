casper.test.comment('Test compiled Javascript and gamestate.');

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

    // Verify we are using the compiled JS files.
    this.test.assertResourceExists('/js/compiled.js', 'compiled.js was imported.');
    this.test.assertResourceExists('/js/compiled-libs.js', 'compiled-libs.js was imported.');

    // We should start on the mail page.
    this.test.assertTitle("Extrasolar - Mail: Welcome to Extrasolar!");

    // Now click on the Map tab.
    this.clickLabel("Map", "a");
});

casper.then(function() {
    // Welcome dialog visible.
    this.test.assertTitleMatch(/.*Extrasolar - Map/);
});

casper.run(function() {
    this.test.done();
});
