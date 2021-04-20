// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.game contains the gamestate change tracking and initialization as well as chips setup.
goog.provide('ce4.game');

goog.require('ce4.util');
goog.require('ce4.gamestate');
goog.require('ce4.ui');
goog.require('ce4.user.User');
goog.require('ce4.social.SocialNetworks');

// A callback to handle gamestate specific constructions whenever the entire gamestate changes.
ce4.game.gamestate_changed = function(new_gamestate) {
    // Construct the User object and all the child Models and Collections.
    ce4.gamestate.user = new ce4.user.User(new_gamestate.user);
    // Store the server provided configuration.
    ce4.gamestate.config = new_gamestate.config;
    // Store the server provided URLs.
    ce4.gamestate.urls = new_gamestate.urls;
    // If provided, Store the classroom data.
    if (new_gamestate.classroom != undefined) {
        ce4.gamestate.classroom = new_gamestate.classroom;
    }

    // Compute a time difference (in seconds) that should be added to Date().getTime()
    // to get the server's UTC time.
    ce4.util.server_time_diff = new_gamestate.config.server_time*1000 - new Date().getTime();

    // Display the username and XP etc.
    ce4.ui.update_navbar();
};

// The initial entry point for the entire client. Called with the entire gamestate JSON object
// from the server.
ce4.game.init = function(gamestate) {

    // Setup things that need to be handled whenever the entire gamestate changes.
    ce4.game.gamestate_changed(gamestate);

    // Setup social networking component. Disabled for Edmodo users.
    ce4.ui.social = new ce4.social.SocialNetworks(ce4.gamestate.user.is_social_enabled());

    // Construct the chips Manager but don't start it polling yet.
    ce4.chips = new lazy8.chips.Manager(
        gamestate.config.last_seen_chip_time,
        ce4.gamestate.config.chip_fetch_interval*1000,
        ce4.util.is_chip_time_newer);
    ce4.chips.fetch_url = ce4.util.url_api(ce4.gamestate.urls.fetch_chips);

    // Register a chip listener on the root user object to dispatch any chip to the correct
    // Collection or Model to handle.
    ce4.chips.listen(['user'], function(chip, match) {
        ce4.gamestate.user.handle_chip_update(chip);
    });

    // If a mission changes, the mission parent/child hierachy might need to be rewired up.
    ce4.chips.listen(['user', 'missions', '<mission_id>'], function(chip, match) {
        // The mission hierarchy might have changed.
        ce4.gamestate.user.wire_up_missions_hierarchy();
    });

    // If a map tile changes (only expecting ADD or MOD), inform the map of the new tile.
    ce4.chips.listen(['user', 'map_tiles', '<tile_key>'], function(chip, match) {
        var tile = ce4.gamestate.user.map_tiles.get(match.tile_key);
        if (tile === undefined) {
            console.error("No map tile found in listener: " + match.tile_key);
            return;
        }
        if (ce4.ui.is_map_loaded()) {
            ce4.ui.leaflet.updateMapTile(tile);
        }
    });

    // Toasts Listeners
    ce4.chips.listen(['user', 'missions', '<mission_id>'], function(chip, match) {
        if(chip.action === lazy8.chips.ADD) {
            var mission = ce4.gamestate.user.missions.get(match.mission_id);
            if(!mission.parent) {
                ce4.ui.new_alert({type: ce4.ui.ALERT_MISSION, object: mission, time: mission.started_at_ms()});
            }
        }
        else if(chip.action === lazy8.chips.MOD && chip.value.done) {
            var mission = ce4.gamestate.user.missions.get(match.mission_id);
            if(!mission.parent) {
                ce4.ui.new_alert({type: ce4.ui.ALERT_MISSION_DONE, object: mission, time: mission.done_at_ms()});
            }
        }
    });
    ce4.chips.listen(['user', 'rovers', '<rover_id>', 'targets', '<target_id>'], function(chip, match) {
        if(chip.action === lazy8.chips.MOD && chip.value.processed) {
            var target = ce4.gamestate.user.rovers.get(match.rover_id).targets.get(match.target_id);
            ce4.ui.new_alert({type: ce4.ui.ALERT_PICTURE, object: target, time: target.arrival_time_ms()});
        }
    });
    ce4.chips.listen(['user', 'messages', '<message_id>'], function(chip, match) {
        if(chip.action === lazy8.chips.ADD) {
            var message = ce4.gamestate.user.messages.get(match.message_id);
            ce4.ui.new_alert({type: ce4.ui.ALERT_MESSAGE, object: message, time: message.sent_at_ms()});
        }
    });
    ce4.chips.listen(['user', 'species', '<species_id>'], function(chip, match) {
        // Do not match subspecies chips.
        if (match.suffix.length > 0) return;
        var discovery = ce4.gamestate.user.species.get(match.species_id);
        if(chip.value.name !== undefined && discovery.isFullyAvailable()) {
            ce4.ui.new_alert({type: ce4.ui.ALERT_DISCOVERY, object: discovery, time: discovery.available_at_ms()});
        }
    });
    ce4.chips.listen(['user', 'achievements', '<achievement_key>'], function(chip, match) {
        if(chip.value.achieved_at) {
            var achievement = ce4.gamestate.user.achievements.get(match.achievement_key);
            ce4.ui.new_alert({type: ce4.ui.ALERT_ACHIEVEMENT, object: achievement, time: achievement.achieved_at_ms()});
        }
    });

    // For every chip "bundle" that is received from the backend, refresh the current page
    // and map.
    ce4.chips.listen_bundle(function(chips) {
        // Refreshing the page during the tutorials can cause problems.  Has the player completed them?
        var tutorials_done = ce4.gamestate.user.progress.contains('PRO_TUT_04');

        // Always refresh the map, as most chips will involve map displayed data.
        // RCJ: For some reason, ce4.ui.map is defined even if it hasn't been initialized yet,
        // so we need to check if the function we want has been defined yet.
        // This may be related to how closure works.
        if (tutorials_done && ce4.ui.is_map_loaded()) {
            ce4.ui.leaflet.refreshUserData();
        }

        // If the current page is not the map, message, or picture, redraw it as well.
        // TODO: Preserve bocks state on reload, and remove ce4.ui.PICTURE from here.
        if (tutorials_done && !ce4.ui.is_current_page_name(ce4.ui.LEAFLET) && !ce4.ui.is_current_page_name(ce4.ui.MESSAGE)
                           && !ce4.ui.is_current_page_name(ce4.ui.PICTURE) && !ce4.ui.is_current_page_name(ce4.ui.MOBILE_PICTURE)) {
            ce4.ui.reload_current_page();
        }
    });

    // Update unviewed alert count
    ce4.ui.update_unviewed_alerts();

    // Handle history/anchor changes. This will also load the initial page.
    $(window).on('hashchange', ce4.ui.history_callback).trigger('hashchange');
    $('#navbar').show();

    // Start the chips Manager polling for changes.
    ce4.chips.sync();
};

// Load the initial gamestate object from the server in the background.
ce4.game.fetch_gamestate = function(gamestate_url) {
    $.ajax({
        type: 'GET',
        url: gamestate_url,
        cache: false,
        success: function (gamestate) {
            ce4.game.init(gamestate);
        },
        error: function(jqXHR, textStatus, errorThrown) {
            console.log("Error while fetching gamestate. Error = " + errorThrown);
            if (ce4.util.is_native()) {
                localStorage.removeItem('auto_login');
                window.location = "index.html";
            }
            else {
                if (ce4.game.fetch_gamestate_backoff === undefined) {
                    ce4.game.fetch_gamestate_backoff = ce4.util.exponential_backoff(50, 5000);
                }
                setTimeout(ce4.game.fetch_gamestate, ce4.game.fetch_gamestate_backoff());
            }
        }
    });
};
