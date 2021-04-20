// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.planet contains various utilities that can be used to get data
// on current and upcoming events on Epsilon Eridani e.
goog.provide("ce4.planet");
goog.require("ce4.util");

// Game time helpers.
ce4.planet.epoch = new Date(Date.UTC(2010, 5, 1, 0, 0, 0, 0));
ce4.planet.epoch_millis = ce4.planet.epoch.getTime();
// TODO: this is only an average day length, need to compensate for variability
// based on latitude and orbital location
ce4.planet.HOURS_PER_ERI = 15.3;
ce4.planet.LUNAR_CYCLE1 = 20.21;  // In Earth days.
ce4.planet.LUNAR_CYCLE2 = 55.61;  // In Earth days.
ce4.planet.eri_length_millis = ce4.planet.HOURS_PER_ERI * 60 * 60 * 1000;

ce4.planet.date_to_eris = function(date) {
    // note that getTime() converts from localtime to UTC, so both epoch_millis
    // and time.getTime() are UTC values
    var millis_since_epoch = date.getTime() - ce4.planet.epoch_millis;
    return millis_since_epoch / ce4.planet.eri_length_millis;
};

ce4.planet.ms_to_eris = function(ms) {
    var millis_since_epoch = ms - ce4.planet.epoch_millis;
    return millis_since_epoch / ce4.planet.eri_length_millis;
};

// Return floating point value representing mission_day.time_within_day.
ce4.planet.now_in_eris = function() {
    var now_sync = new Date().getTime() + ce4.util.server_time_diff;
    var millis_since_epoch = now_sync - ce4.planet.epoch_millis;
    return millis_since_epoch / ce4.planet.eri_length_millis;
};

// Input should be either 0 (major moon) or 1 (minor moon).
// Return floating point value representing lunar phase:
// 0.0=new, 0.25=first quarter, 0.5=full, 0.75=third quarter
ce4.planet.current_lunar_phase = function(moon_id) {
    var now_sync = new Date().getTime() + ce4.util.server_time_diff;
    var millis_since_epoch = now_sync - ce4.planet.epoch_millis;
    var lunar_cycle_ms = ce4.planet.LUNAR_CYCLE1*24*60*60*1000;
    if (moon_id == 1)
        lunar_cycle_ms = ce4.planet.LUNAR_CYCLE2*24*60*60*1000;
    var phase = millis_since_epoch / lunar_cycle_ms;
    // Return only the fractional part of the phase.
    return phase - Math.floor(phase);
};

// Given the time in ms (already normalized with the server_time_diff),
// compute a value between 0 and 1 representing the current lunar position
// (0.25=eastern horizon, 0.5=overhead, 0.75=western horizon).
ce4.planet.lunar_position_at_time = function(moon_id, time_ms) {
    var millis_since_epoch = time_ms - ce4.planet.epoch_millis;
    var lunar_cycle_ms = ce4.planet.LUNAR_CYCLE1*24*60*60*1000;
    if (moon_id == 1)
        lunar_cycle_ms = ce4.planet.LUNAR_CYCLE2*24*60*60*1000;
    // The equations we're solving:
    // eris = millis_since_epoch / eri_length_millis
    // lunar_phase (relative to stationary planet) = millis_since_epoch / lunar_cycle_ms
    // lunar_position (relative to rotating point on planet) = eris + lunar_phase
    // Solve for the current lunar position:
    var lunar_position = millis_since_epoch / ce4.planet.eri_length_millis - millis_since_epoch / lunar_cycle_ms;
    return lunar_position - Math.floor(lunar_position);
}

// This function can be used to calculate upcoming moonrise or moonset events.
// Moon_id should be either 0 (major moon) or 1 (minor moon).
// event_threshold is a fractional floating point value representing
// the time of the event (0.25=moonrise, 0.75=moonset)
// Return time, in milliseconds, until event.
ce4.planet.next_lunar_event = function(moon_id, event_threshold) {
    var now_sync = new Date().getTime() + ce4.util.server_time_diff;
    var millis_since_epoch = now_sync - ce4.planet.epoch_millis;
    var lunar_cycle_ms = ce4.planet.LUNAR_CYCLE1*24*60*60*1000;
    if (moon_id == 1)
        lunar_cycle_ms = ce4.planet.LUNAR_CYCLE2*24*60*60*1000;
    // The equations we're solving:
    // eris = millis_since_epoch / eri_length_millis
    // lunar_phase (relative to stationary planet) = millis_since_epoch / lunar_cycle_ms
    // lunar_position (relative to rotating point on planet) = eris + lunar_phase
    // Solve for the current lunar position:
    var lunar_position = millis_since_epoch / ce4.planet.eri_length_millis - millis_since_epoch / lunar_cycle_ms;
    var next_lunar_event = Math.floor(lunar_position) + event_threshold;
    if (next_lunar_event < lunar_position) {
        next_lunar_event += 1.0;
    }

    // Now solve the inverse equation to determine the time of this event threshold.
    // lunar_position*eris_length_millis*lunar_cycle_ms = millis_since_epoch*lunar_cycle_ms + millis_since_epoch*eri_length_millis
    // millis_since_epoch = lunar_position*eris_length_millis*lunar_cycle_ms/(lunar_cycle_ms+eri_length_millis)
    var time_of_threshold = next_lunar_event*ce4.planet.eri_length_millis*lunar_cycle_ms/(lunar_cycle_ms - ce4.planet.eri_length_millis);

    // Turn this into a time relative to now.
    return Math.floor(time_of_threshold - millis_since_epoch);
};

// This function can be used to calculate upcoming sunrise or sunset events.
// event_threshold is a fractional floating point value representing
// the time of the event (0=midnight, 0.25=sunrise, 0.5=noon, 0.75=sunset)
// Return time, in milliseconds, until event.
ce4.planet.next_solar_event = function(event_threshold) {
    var now_sync = new Date().getTime() + ce4.util.server_time_diff;
    var millis_since_epoch = now_sync - ce4.planet.epoch_millis;
    // The equations we're solving:
    // eris = millis_since_epoch / eri_length_millis
    // Solve for the current solar position:
    var solar_position = millis_since_epoch / ce4.planet.eri_length_millis;
    var next_solar_event = Math.floor(solar_position) + event_threshold;
    if (next_solar_event < solar_position) {
        next_solar_event += 1.0;
    }

    // Now solve the equation for millis_since_epoch to determine the time of this event threshold.
    var time_of_threshold = next_solar_event*ce4.planet.eri_length_millis;

    // Turn this into a time relative to now.
    return Math.floor(time_of_threshold - millis_since_epoch);
};
