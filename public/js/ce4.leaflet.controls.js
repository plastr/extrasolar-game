// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.leaflet.region contains various controls used on the leaflet.
goog.provide('ce4.leaflet.controls');
goog.provide('ce4.leaflet.controls.DirectionWizard');
goog.provide('ce4.leaflet.controls.CreateButton');
goog.provide('ce4.leaflet.controls.RadialControl');

goog.require('ce4.mission.callbacks');
goog.require('ce4.planet');
goog.require('ce4.util');

ce4.leaflet.controls.EARLIEST_TARGET_HOURS = 1;
ce4.leaflet.controls.TARGET_WINDOW_HOURS = 20;
ce4.leaflet.controls.EARLIEST_TARGET_MS = ce4.leaflet.controls.EARLIEST_TARGET_HOURS*60*60*1000;

//------------------------------------------------------------------------------
// Constructor for a new DirectionWizard
ce4.leaflet.controls.DirectionWizard = function(extraSolarMap, marker, tdisplay, rover)
{
    // Initialize
    this.extraSolarMap = extraSolarMap;
    this.map = this.extraSolarMap.leafletMap;
    this.user = this.extraSolarMap.user;
    this.marker = marker;
    this.rover = rover;
    this.tdisplay = tdisplay;

    // TODO: set up a periodic update so that if they leave the wizard open
    // for a while it's still correct. Or, have the wizard track the number of seconds
    // for the arrival_delta, instead of tracking it as a Date object.
    var now_ms = ce4.util.utc_now_in_ms();
    this.earliestTime = ce4.leaflet.controls.earliest_rover_picture(rover, now_ms);

    // Save time dialog opened so that the time the user selects is consistant
    this.nowWhenOpened_ms = now_ms;
    this.timeRange = 12;  // hours

    this.Display();
};

//------------------------------------------------------------------------------
// Creates the control in a popup and displays it
ce4.leaflet.controls.DirectionWizard.prototype.Display = function()
{
    // Direction Control HTML
    var ControlHTML = "<div align=center id=\"wizardcontent\" style=\"height: 390px; width:320px;\">\
          <div id=\"direction-slider\" style=\"position: absolute; top: 240px; width:300px; cursor: pointer; cursor: hand;\"></div>"
    // Step 1
    + "   <div id=\"direction-controls1\" style=\"display:none;\">\
            <img class=\"direction-wizard-step-image\" src=\""+ce4.util.url_static("/img/dw/stepOne.png")+"\"><br>\
            <div class=\"direction-wizard-control-container overlay-container\">\
              <font class=\"direction-wizard-font\">set direction</font><br><br>\
              <center><div class=\"direction-wizard-direction-data overlay-container\"><font class=\"direction-wizard-font\"><span id=\"compass-direction\"></span><br><hr style=\"border-color: rgba(255,255,255,0.25); padding-top: 0px; margin: 8px;\"><span id=\"angle\"></span>&deg;</font></div></center>\
              <center><br><div id=\"compass-container\" class=\"direction-wizard-compass\">\
                <ul id=\"compass-drag\"><li>\
                  <img src=\""+ce4.util.url_static("/img/dw/direction_compass_overlay.png")+"\" height=\"33\" width=\"1200\"/>\
                </li></ul>\
                <div class=\"direction-wizard-compass-caret\"></div>\
              </div></center>\
              <div style=\"position: absolute; top: 200px; width:300px;\">\
                <table width=100%><tr><td width=50% style=\"text-align:left;\">\
                  <button class=\"gradient-button gradient-button-overlay\" id=\"cancel\">Back</button>\
                </td><td width=50% style=\"text-align:right;\">\
                  <button class=\"gradient-button gradient-button-overlay\" id=\"next\">Next</button>\
                </td></tr></table>\
              </div>\
            </div>\
          </div>"
    // Step 2
    + "   <div id=\"direction-controls2\" style=\"display:none;\">\
            <img class=\"direction-wizard-step-image\" src=\""+ce4.util.url_static("/img/dw/stepTwo.png")+"\">\
            <div class=\"direction-wizard-control-container overlay-container\">\
              <font class=\"direction-wizard-font\">set time delay</font><br>\
              <br><center><div id=\"delay-sky\" class=\"direction-wizard-delay-sky\">\
                <img id=\"delay-control-sun-image\" src=\""+ce4.util.url_static("/img/dw/icon_sun.png")+"\" style=\"position: absolute;\"/>\
                <img id=\"delay-control-star1-image\" src=\""+ce4.util.url_static("/img/dw/icon_stars.png")+"\" style=\"position: absolute;\"/>\
                <img id=\"delay-control-star2-image\" src=\""+ce4.util.url_static("/img/dw/icon_stars.png")+"\" style=\"position: absolute;\"/>\
                <img id=\"delay-control-star3-image\" src=\""+ce4.util.url_static("/img/dw/icon_stars.png")+"\" style=\"position: absolute;\"/>\
                <img id=\"delay-control-moon1-image\" src=\""+ce4.util.url_static("/img/dw/icon_moon.png")+"\" style=\"position: absolute;\"/>\
                <img id=\"delay-control-moon2-image\" src=\""+ce4.util.url_static("/img/dw/icon_moon.png")+"\" style=\"position: absolute;\"/>\
              </div>\
              <center><div class=\"direction-wizard-delay-data1\">\
                <p class=\"direction-wizard-small-font\">Ready at <span id=\"local-time\"></span></p>\
              </div></center><br>\
              <div class=\"direction-wizard-delay-data2\">\
                <font class=\"direction-wizard-font\"><span id=\"time-from-now\"></span></font>\
              </div>\
              <div id=\"delay-slider\" class=\"direction-wizard-delay-slider\" style=\"width:276px;\"><div id=\"delay-slider-fast-move\" class=\"direction-wizard-delay-fast-move\" title=\"Early photo scheduling is limited. Upgrade your account to schedule photos earlier.\"></div></div></center>\
              <div style=\"position: absolute; top: 200px; width:300px;\">\
                <table width=100%><tr><td width=50% style=\"text-align:left;\">\
                  <button class=\"gradient-button gradient-button-overlay\" id=\"back\">Back</button>\
                </td><td width=50% style=\"text-align:right;\">\
                  <button class=\"gradient-button gradient-button-overlay\" id=\"next\">Next</button>\
                </td></tr></table>\
              </div>\
            </div>\
          </div>"
    // Step 3
    + "   <div id=\"direction-controls3\" style=\"display:none;\">\
            <img class=\"direction-wizard-step-image\" src=\""+ce4.util.url_static("/img/dw/stepThree.png")+"\">\
            <div class=\"direction-wizard-control-container overlay-container\">\
              <font class=\"direction-wizard-font\">set options</font><br><br>\
                <table class=\"direction-wizard-options\" id=\"id-direction-wizard-options\">\
                </table>\
              <div style=\"position: absolute; top: 200px; width:300px;\">\
                <table width=100%><tr><td width=50% style=\"text-align:left;\">\
                  <button class=\"gradient-button gradient-button-overlay\" id=\"back\">Back</button>\
                </td><td width=50% style=\"text-align:right;\">\
                  <button class=\"gradient-button gradient-button-overlay\" id=\"next\">Done</button>\
                </td></tr></table>\
              </div>\
            </div>\
          </div>"
    // Step 4 - Validation
    + "   <div id=\"direction-controls4\" style=\"display:none;\">\
            <img class=\"direction-wizard-step-image\" src=\""+ce4.util.url_static("/img/dw/stepFour.png")+"\">\
            <div class=\"direction-wizard-control-container overlay-container\">\
              <font class=\"direction-wizard-font\">uploading instructions</font><br><br><br><br><br>\
                    <img src=\""+ce4.util.url_static("/img/XRI_logo_0001_satel-icn.png")+"\">\
                    <img src=\""+ce4.util.url_static("/img/xri-loader.gif")+"\">\
                    <img src=\""+ce4.util.url_static("/img/XRI_logo_0002_world-icn.png")+"\">\
                    <img src=\""+ce4.util.url_static("/img/xri-loader.gif")+"\">\
                    <img src=\""+ce4.util.url_static("/img/XRI_logo_0003_rover-icn.png")+"\">\
            </div>\
          </div>"
    // Server error
    + "   <div id=\"direction-controls-error\" style=\"display:none;\">\
            <img class=\"direction-wizard-step-image\" src=\""+ce4.util.url_static("/img/dw/stepFour.png")+"\">\
            <div class=\"direction-wizard-control-container overlay-container\">\
              <font class=\"direction-wizard-font\">Error while scheduling photo.  Please try again.</font><br><br>\
              <button class=\"gradient-button gradient-button-overlay\" id=\"cancel\">OK</button>\
            </div>\
          </div>"
    // Mission Content
    + "   <div id=\"missioncontent\"style=\"position: absolute; left: 25px; top: 10px; width:300px; display:none;\"></div>"
    // Direction Control Close
    + " </div>";

    // Direction Control Functionality
    var dom = document.createElement("DIV");
    $(ControlHTML).appendTo(dom);
    $(dom).find('#direction-controls1 #angle').text(this.tdisplay.new_target_fields.yaw/Math.PI*180);
    $(dom).find('#direction-controls1 #cancel').click($.proxy(function() { this.cancel(); this.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step03', {})}, this));
    $(dom).find('#direction-controls1 #next').click($.proxy(function() { ce4.util.toggleView('direction-controls', 'direction-controls2', 2); this.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step05', {}); }, this));
    $(dom).find('#direction-controls2 #back').click($.proxy(function() { ce4.util.toggleView('direction-controls', 'direction-controls1', 2); this.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step04', {}); }, this));
    $(dom).find('#direction-controls3 #back').click($.proxy(function() { ce4.util.toggleView('direction-controls', 'direction-controls2', 2); this.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step05', {}); }, this));
    $(dom).find('#direction-controls-error #cancel').click($.proxy(function() { this.dismiss(); }, this));

    // Close any popup that may be open
    this.map.closePopup();

    // Event Listeners to handle the popup closing based on user intent
    this.map.addEventListener('popupclose', this.cancel, this);
    this.marker.addEventListener('mousedown', function () { this.map.removeEventListener('popupclose', this.cancel, this); }, this);
    this.marker.addEventListener('mouseup', function () { this.map.addEventListener('popupclose', this.cancel, this); }, this);

    // Initialize popup
    this.popup = L.popup({className: 'direction-wizard-control', closeButton: false, closeOnClick: false, offset: new L.Point(0,19)});
    this.popup.setLatLng(this.marker.getLatLng());
    this.popup.openOn(this.map);
    this.popup.setContent(dom);

    // Step 1 - Direction Control: called when control is changed
    var change_func = $.proxy(function(event, value) {
                                  var angle = Math.round(value/Math.PI*180);
                                  if (angle < 0) angle += 360;
                                  this.tdisplay.new_target_fields.yaw = value;
                                  $('#angle').text(angle);
                                  $('#compass-direction').text(ce4.util.yaw_to_compass(value));
                                  $('#radial-control-background-image').rotate(angle);
                                  if(event !== false) $('#compass-drag li').css('left', -1662 + (-10 * angle / 3));
                                  ce4.mission.callbacks.wizard_hook(1, this.tdisplay.new_target_fields, this);
                              }, this);

    // Step 1 - Direction Control: create control
    new ce4.leaflet.controls.RadialControl($(dom).find('#direction-slider'), {
        background:       ce4.util.url_static('/img/dw/direction_groundIndicator_handle.png'),
        background_over:  ce4.util.url_static('/img/dw/direction_groundIndicator_handle_over.png'),
        nomarker:         true,
        size:             300,
        value:            this.tdisplay.getPathDirection(),  // Starting orientation in radians.
        change:           change_func,
        slide:            change_func,
        init:             change_func});

    // Step 2 - Starting sky color and sun/moon position.
    var default_slider_value = this.rover.min_target_seconds / (60 * 60) - ce4.leaflet.controls.EARLIEST_TARGET_HOURS;
    var now_ms = ce4.util.utc_now_in_ms();
    this.earliestTime = ce4.leaflet.controls.earliest_rover_picture(this.rover, now_ms);
    var scheduled_arrival = ce4.util.date_sans_millis(this.earliestTime.getTime() + default_slider_value*60*60*1000);
    this.updateSky(this.earliestTime.getTime(), scheduled_arrival.getTime());

    // Use the appropriate icons for the moon phases.
    var major_lunar_phase  = ce4.planet.current_lunar_phase(0);
    var minor_lunar_phase  = ce4.planet.current_lunar_phase(1);
    var major_moon_int = Math.floor((major_lunar_phase * 8) + 0.5);
    var minor_moon_int = Math.floor((minor_lunar_phase * 8) + 0.5);
    if (major_moon_int > 7) major_moon_int = 0;
    if (minor_moon_int > 7) minor_moon_int = 0;
    $('#delay-control-moon1-image').attr('src', ce4.util.url_static('/img/dw/icon_moon'+(major_moon_int+1)+'.png'));
    $('#delay-control-moon2-image').attr('src', ce4.util.url_static('/img/dw/icon_moon'+(minor_moon_int+1)+'.png'));

    // Step 2 - Initialize default arrival time
    if(this.tdisplay.new_target_fields.arrival_time_date === null) this.tdisplay.new_target_fields.arrival_time_date = scheduled_arrival;
    $('#local-time').text(ce4.util.localTimeAsStr(scheduled_arrival));
    var scheduled_delay_ms = scheduled_arrival - now_ms;
    $(dom).find('#time-from-now').text(ce4.util.format_time_hm(scheduled_delay_ms));

    // Step 2 - Time Delay Control: called when control is changed
    var delay_change_func = $.proxy(function(value, slider) {
                                  // Update the wall-clock time in case the wizard has been open for a while.
                                  var now_ms = ce4.util.utc_now_in_ms();
                                  this.earliestTime = ce4.leaflet.controls.earliest_rover_picture(this.rover, now_ms);
                                  var scheduled_arrival = ce4.util.date_sans_millis(this.earliestTime.getTime() + value*60*60*1000);
                                  this.tdisplay.new_target_fields.arrival_time_date = scheduled_arrival; // Local time
                                  $('#local-time').text(ce4.util.localTimeAsStr(scheduled_arrival));

                                  // Update the time delay, which should never be less than EARLIEST_TARGET_HOURS, no matter how long the wizard is open.
                                  var scheduled_delay_ms = scheduled_arrival - now_ms;
                                  $(dom).find('#time-from-now').text(ce4.util.format_time_hm(scheduled_delay_ms));

                                  // Update sky tint, sun/moon position.
                                  this.updateSky(this.earliestTime.getTime(), scheduled_arrival.getTime());
                                  ce4.mission.callbacks.wizard_hook(2, this.tdisplay.new_target_fields, this);
                              }, this);

    // Step 2 - Time Delay Control: create control with a valuge range from 0 to TARGET_WINDOW_HOURS
    // Default to the earliest hour at which payment is not required.
    ce4.util.toggleView('direction-controls', 'direction-controls2', 1); // Hack to make slider work properly
    var sld = new dhtmlxSlider('delay-slider', {
        size: 276,  // 276-24 pixels/20 hours * 15.3 hours/1 eri = 193 pixels/eri = background texture width
        skin: "leaflet",
        vertical:false,
        step:0.10,
        min:0.0,
        max:ce4.leaflet.controls.TARGET_WINDOW_HOURS, // FUTU: Change this to use this.rover.max_target_seconds (this is problematic because the slider size is derived from this number as well)
        value:default_slider_value});
    sld.attachEvent("onChange", delay_change_func);
    sld.setImagePath(ce4.util.url_static("/img/"));
    sld.init();
    sld.enableTooltip(false);

    // Step 2 - Delay
    var cap_move = this.user.capabilities.get('CAP_S1_ROVER_FAST_MOVE');

    var update_delay_use = function() {
        if(cap_move.has_uses()) {
            $(dom).find('#delay-slider-fast-move').hide();
        }
        else {
            $(dom).find('#delay-slider-fast-move').show();
            if(sld.getValue() < default_slider_value) {
                sld.setValue(default_slider_value);
                delay_change_func(default_slider_value); // sld.setValue doesn't trigger onChange event
            }
        }
    };
    update_delay_use();

    // Step 2 - Next button
    $(dom).find('#direction-controls2 button:last').click($.proxy(function(event) {
        if(sld.getValue() >= default_slider_value || cap_move.has_uses()) {
            ce4.util.toggleView('direction-controls', 'direction-controls3', 2);
            this.user.tutorial.advance(ce4.tutorial.ids.TUT01, 'tutorial01-step06', {});
            return true;
        }
        else {
            ce4.ui.upgrade.dialogOpen("upgrade-wizard-delay", {onCancel: update_delay_use});
            return false;
        }
    },this));

    // Step 3 - Options
    var html_options = $(dom).find('#id-direction-wizard-options');
    var cap_flash    = this.user.capabilities.get('CAP_S1_CAMERA_FLASH');
    var cap_panorama = this.user.capabilities.get('CAP_S1_CAMERA_PANORAMA');
    var cap_infrared = this.user.capabilities.get('CAP_S1_CAMERA_INFRARED');
    if (cap_flash.is_available()) {
        html_options.append($('<tr><td><input type="checkbox" class="camera-option-checkbox" id="id-camera-option-flash" name="option_flash" value="1"></td><td><div class="capability-flash">&nbsp;</div></td><td>Flash</td><td id="option_flash_uses"></td></tr>').click(ce4.util.selectRow));
    }
    if (cap_panorama.is_available()) {
        html_options.append($('<tr><td><input type="checkbox" class="camera-option-checkbox" id="id-camera-option-panorama" name="option_panorama" value="1"></td><td><div class="capability-panorama">&nbsp;</div></td><td>Panorama</td><td id="option_panorama_uses"></td></tr>').click(ce4.util.selectRow));
    }
    if (cap_infrared.is_available()) {
        html_options.append($('<tr><td><input type="checkbox" class="camera-option-checkbox" id="id-camera-option-infrared" name="option_infrared" value="1"></td><td><div class="capability-infrared">&nbsp;</div></td><td>Infrared</td><td id="option_infrared_uses"></td></tr>').click(ce4.util.selectRow));;
    }

    var update_option_uses = function() {
        var tooltip_unlimited = "You have unlimited uses of this feature.";
        var tooltip_limited = "This feature has a limited number of uses. Upgrade your account for unlimited access.";
        var html_options = $(dom).find('#id-direction-wizard-options');
        html_options.find('#option_flash_uses').html(   '<div class="overlay-container overlay-container-small" title="'+(cap_flash.is_unlimited()    ? tooltip_unlimited : tooltip_limited)+'">'+cap_flash.uses_left_text()    +'</div>');
        html_options.find('#option_panorama_uses').html('<div class="overlay-container overlay-container-small" title="'+(cap_panorama.is_unlimited() ? tooltip_unlimited : tooltip_limited)+'">'+cap_panorama.uses_left_text() +'</div>');
        html_options.find('#option_infrared_uses').html('<div class="overlay-container overlay-container-small" title="'+(cap_infrared.is_unlimited() ? tooltip_unlimited : tooltip_limited)+'">'+cap_infrared.uses_left_text()+'</div>');

        // Uncheck checked with no uses
        if(html_options.find('#id-camera-option-flash').prop('checked')    && !cap_flash.has_uses())    $('#id-camera-option-flash').prop('checked', false);
        if(html_options.find('#id-camera-option-panorama').prop('checked') && !cap_panorama.has_uses()) $('#id-camera-option-panorama').prop('checked', false);
        if(html_options.find('#id-camera-option-infrared').prop('checked') && !cap_infrared.has_uses()) $('#id-camera-option-infrared').prop('checked', false);
    };
    update_option_uses();

    // Step 3 - Done button
    $(dom).find('#direction-controls3 button:last').click($.proxy(function(event) {
        if( (!html_options.find('#id-camera-option-flash').prop('checked') || cap_flash.has_uses()) &&
            (!html_options.find('#id-camera-option-panorama').prop('checked') || cap_panorama.has_uses()) &&
            (!html_options.find('#id-camera-option-infrared').prop('checked') || cap_infrared.has_uses())) {
            ce4.util.toggleView('direction-controls', 'direction-controls4', 2);
            this.sendToServer(this.tdisplay.new_target_fields);
            return true;
        }
        else {
            ce4.ui.upgrade.dialogOpen("upgrade-wizard-options", {onCancel: update_option_uses});
            return false;
        }
    },this));


    // Some options are mutually exclusive.
    var change_option_func = $.proxy(function(event, value) {
                                if (event.target.name === 'option_panorama') {
                                    $('#id-camera-option-infrared').prop('checked', false);
                                }
                                if (event.target.name === 'option_infrared') {
                                    $('#id-camera-option-panorama').prop('checked', false);
                                }
                            }, this);

    $('.camera-option-checkbox').change(change_option_func);

    // Open step 1
    ce4.util.toggleView('direction-controls', 'direction-controls1', 1);

    var compass_drag_interval_id;
    $('#compass-drag').jParadrag({
                    width: 275,
                    height: 33,
                    startPosition: Math.round((1800 -138 - (-10 * Math.round(this.tdisplay.getPathDirection()/Math.PI*180) / 3)) % 1200),
                    loop: true,
                    factor: 1,
                    onDrag: function(){ compass_drag_interval_id = setInterval( function(){ change_func(false, Math.abs(parseInt($('#compass-drag li').css('left')) + 462) % 1200 * Math.PI / 600 ); }, 100); },
                    onMomentumStop: function(){ clearInterval(compass_drag_interval_id);},
                    momentum: {avg: 3, friction: 0.4}
                });

    // Make draggable for touch devices using touch punch (This breaks IE, so check for touch support)
    if ($.support.touch) {
        $('.radial-control > .background-image').draggable({ containment: "parent" });
        $('.dhtmlxSlider_leaflet')              .draggable({ containment: "parent" });
    }
};

//------------------------------------------------------------------------------
// Update the appearance of the sky based on the scheduled arrival time.
ce4.leaflet.controls.DirectionWizard.prototype.updateSky = function(earliest_time_ms, arrival_time_ms)
{
    // Convert from ms to eris.
    var eris_at_arrival = ce4.planet.ms_to_eris(arrival_time_ms);
    // Compute the time of day (0.0 = midnight, 0.5 = noon).
    var time_at_arrival = eris_at_arrival - Math.floor(eris_at_arrival);

    // Repositin the slider background.
    var eris_at_earliest = ce4.planet.ms_to_eris(earliest_time_ms);
    var time_at_earliest = eris_at_earliest - Math.floor(eris_at_earliest);
    var background_image_width = 193;
    var slider_handle_width = 24;
    var slider_background_offset = Math.floor(slider_handle_width/2-time_at_earliest*background_image_width);
    $('#delay-slider').css('background-position', slider_background_offset + "px 0px");

    // Add icons to the sky for the sun, stars and each of the 2 moons.
    var moon1_position = ce4.planet.lunar_position_at_time(0, arrival_time_ms);
    var moon2_position = ce4.planet.lunar_position_at_time(1, arrival_time_ms);
    this.updateSkyIcon('#delay-control-sun-image',  time_at_arrival,       62.0);
    this.updateSkyIcon('#delay-control-star1-image', time_at_arrival+0.43, 62.0);
    this.updateSkyIcon('#delay-control-star2-image', time_at_arrival+0.50, 62.0);  // Directly opposite sun.
    this.updateSkyIcon('#delay-control-star3-image', time_at_arrival+0.57, 62.0);
    this.updateSkyIcon('#delay-control-moon1-image', moon1_position,       62.0);
    this.updateSkyIcon('#delay-control-moon2-image', moon2_position,       62.0);

    // Interpolate between colors based on time of day.
    var SKY_COLORS = [
      [0.13, 0.18, 0.28],  // Midnight
      [0.13, 0.18, 0.28],  // 3am
      [0.80, 0.37, 0.51],  // Sunrise
      [0.55, 0.70, 1.00],  // 9am
      [0.55, 0.70, 1.00],  // Noon
      [0.55, 0.70, 1.00],  // 3pm
      [0.80, 0.37, 0.51],  // Sunset
      [0.13, 0.18, 0.28],  // 9pm
      [0.13, 0.18, 0.28]   // Midnight
    ];
    var interval = Math.floor(time_at_arrival*8.0);
    var interp = (time_at_arrival*8.0) - interval;
    var r = SKY_COLORS[interval][0]*(1.0-interp) + SKY_COLORS[interval+1][0]*interp;
    var g = SKY_COLORS[interval][1]*(1.0-interp) + SKY_COLORS[interval+1][1]*interp;
    var b = SKY_COLORS[interval][2]*(1.0-interp) + SKY_COLORS[interval+1][2]*interp;
    var blended_color = 'rgba('+(r*255).toFixed()+','+(g*255).toFixed()+','+(b*255).toFixed()+',.7)';
    $('#delay-sky').css('background-color', blended_color);
}

//------------------------------------------------------------------------------
// Position the indicated icon based on the sky_position (0 to 1 where 0.25=eastern horizon, 0.5=overhead,
// 0.75=western horizon) and orbit radius.
ce4.leaflet.controls.DirectionWizard.prototype.updateSkyIcon = function(div_name, sky_position, orbit_radius)
{
    var orbit_center_x = 153;
    var orbit_center_y = 120;

    // Normalize sky_position;
    sky_position = sky_position - Math.floor(sky_position);
    if (sky_position < 0.25 || sky_position > 0.75) {
        $(div_name).hide();
    }
    else {
        var angle = Math.PI/2.0 - sky_position*2.0*Math.PI;
        var x = orbit_center_x + 1.3*orbit_radius*Math.cos(angle);
        var y = orbit_center_y + orbit_radius*Math.sin(angle);
        $(div_name).show().css({"left": x+"px", "top": y+"px"});
    }
}

//------------------------------------------------------------------------------
// TODO: Is this used by anything anymore?
ce4.leaflet.controls.DirectionWizard.prototype.setNextButtonDisabled = function(value)
{
    $('#direction-controls1 button:last', this.popup._content).attr('disabled', value);
    $('#direction-controls2 button:last', this.popup._content).attr('disabled', value);
    $('#direction-controls3 button:last', this.popup._content).attr('disabled', value);
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.DirectionWizard.prototype.setMissionContent = function(value, ok)
{
    // TODO: Probably can do this better with _popup.setContent() and then remove the openPopup hack
    ce4.util.toggleView('notab', 'missioncontent', 1);
    $('#missioncontent', this.popup._content).html(value).removeClass('ok').addClass(function() { return ok ? 'ok' : '';});

    // Don't allow the player to advance to the next step if ok is false.
    this.setNextButtonDisabled(!ok);
};

//------------------------------------------------------------------------------
// Calculate time between arrival date chosen by user and time dialog was opened
ce4.leaflet.controls.DirectionWizard.prototype.sendToServer = function(new_target_fields)
{
    // In milliseconds
    var millis_between = new_target_fields.arrival_time_date.getTime() - this.nowWhenOpened_ms;

    // And convert that to seconds
    var arrival_delta = Math.floor(millis_between / 1000);

    // TODO: Should this data be set on the target (this.tdisplay.new_target_fields.metadata)?
    var metadata = {};
    if($("#id-camera-option-flash").is(":checked"))    metadata.TGT_FEATURE_FLASH    = "";
    if($("#id-camera-option-panorama").is(":checked")) metadata.TGT_FEATURE_PANORAMA = "";
    if($("#id-camera-option-infrared").is(":checked")) metadata.TGT_FEATURE_INFRARED = "";

    // If the target is successfully created, close the dialog box.
    var cbSuccess = $.proxy(function(event, value) {
        this.dismiss();
    }, this);

    // If target creation fails, report the error in the dialog box.
    var cbFailure = $.proxy(function(event, value) {
        ce4.util.toggleView('direction-controls', 'direction-controls-error', 1);;
    }, this);

    // Tell the server to create a target
    this.rover.createTarget(new_target_fields.lat, new_target_fields.lng,
                            new_target_fields.yaw, new_target_fields.pitch,
                            arrival_delta, metadata, cbSuccess, cbFailure);
};

//------------------------------------------------------------------------------
// The user either completed the wizard or closed it before finishing.
ce4.leaflet.controls.DirectionWizard.prototype.dismiss = function()
{
    this.map.removeEventListener('popupclose', this.cancel, this);
    this.popup._close();
    //this.marker.unbindPopup();
    this.tdisplay.remove();
    if(this.markerAngle !== undefined)
    {
        this.map.removeLayer(this.markerAngle);
        delete this.markerAngle;
    }

    if(this.rover.wizard) this.rover.wizard = undefined;

    this.extraSolarMap.initDragMarker(this.rover);
};

//------------------------------------------------------------------------------
// The user pressed the close button on the wizard.
// FUTU: Depricate this, and replace it with direct calls to cancel
ce4.leaflet.controls.DirectionWizard.prototype.cancel = function()
{
    this.dismiss();
};

//------------------------------------------------------------------------------
// Compute a Date object for UTC a set number of hours from now.
ce4.leaflet.controls.earliest_rover_picture = function(rover, now_ms)
{
    var lastTarget = rover.getLastTarget();
    var earliestMs;

    // If the last target is in the future, add EARLIEST_TARGET_MS to its arrival time
    if (lastTarget && lastTarget.arrival_time_ms() > now_ms)
    {
        earliestMs = lastTarget.arrival_time_ms() + ce4.leaflet.controls.EARLIEST_TARGET_MS;
    }
    // Else add EARLIEST_TARGET_MS to the current time
    else
    {
        earliestMs = now_ms + ce4.leaflet.controls.EARLIEST_TARGET_MS;
    }

    // Return this as a Date object (Adds local time zone info and converts from UTC)
    return ce4.util.date_sans_millis(earliestMs);
};


//------------------------------------------------------------------------------
// Create a button control for the leaflet map
ce4.leaflet.controls.CreateButton = function(p)
{
    var controlDiv  = L.DomUtil.create('div', p.css);
    var controlUI   = L.DomUtil.create('div', p.css + '-border', controlDiv);
    var controlText = L.DomUtil.create('div', p.css + '-interior', controlUI);

    L.DomEvent.disableClickPropagation(controlDiv);

    return new (L.Control.extend({
        options: { position: p.position || 'topright' },
        onAdd: function (map)
        {
            if(p.onClick) L.DomEvent.addListener(controlDiv, 'click', p.onClick, p.context);
            this.setTitle(p.title);
            this.setHTML(p.html);
            return controlDiv;
        },
        onRemove: function (map)
        {
            if(p.onClick) L.DomEvent.removeListener(controlDiv, 'click', p.onClick);
        },
        setTitle: function (title) { controlUI.title = title || ''; },
        setHTML: function (html) { controlText.innerHTML = html || ''; }
    }));
};


//------------------------------------------------------------------------------
//  Radial control for selecting things that are circular.
//     options available:
//         size:          width/height in pixels  (default: 150)
//         background:    url of image to be used as the backdrop
//         change:        callback for when the value has stopped moving
//         slide:         callback when the user is moving the control around
ce4.leaflet.controls.RadialControl = function(container, opts)
{
    this.opts = opts;
    this.size = opts.size || 150;
    this.background = opts.background;
    this.background_over = opts.background_over;
    this.container = container.get(0);
    this.initialize();

    if(opts.range != undefined)
    {
        this.setRange(opts.range[0], opts.range[1]);
    }

   return this;
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype.initialize = function()
{
    $(this.container).html(
        '<div class="radial-control">\
            <div class="background-image">\
                <img class="background-image" src="' + this.background + '" id=radial-control-background-image>\
            </div>\
            <div class="marker"></div>\
        </div>');

    if(this.background_over)
    {
        $(this.container).mouseover($.proxy(function () {$('#radial-control-background-image').attr("src", this.background_over); }, this));
        $(this.container).mouseout($.proxy(function () { $('#radial-control-background-image').attr("src", this.background);  }, this));
    }

    $(this.container).find('.radial-control').css({
            position: "relative",
            width: this.size + "px",
            height: this.size + "px"});

    $(this.container).find('.background-image').css({
            width: this.size + "px",
            height: this.size + "px"});

    if(this.opts.nomarker === undefined || this.opts.nomarker === false)
    {
        $(this.container).find('.marker').css({
                position: 'absolute',
                width: '17px',
                height: '17px',
                margin: '-8px 0 0 -8px',
                overflow: 'hidden',
                background: 'url('+ce4.util.url_static('/img/marker.png')+') no-repeat'});
    }

    if(this.opts.value != undefined)
    {
        this._setValueNoUpdate(this.opts.value);
    } else {
        this._setValueNoUpdate(0);
    }

    $(this.container).find('*').mousedown($.proxy(this.mousedown, this));

    if(typeof this.opts.init == "function")
    {
        this.opts.init(this, this.value);
    }
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype._setValueNoUpdate = function(val)
{
    if(this.value == val) { return this; }

    val = ce4.leaflet.controls.containAngle(val);
    this.value = val;
    this.containMarker();
    this.updateDisplay();
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype.setValue = function(val, sliding)
{
    this._setValueNoUpdate(val);

    if(sliding)   this.updateSlideCallbacks();
    else          this.updateChangeCallbacks();

    return this;
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype.updateDisplay = function(val)
{
    var coords = {
        left:   Math.round(this.size/2 + Math.sin(this.value)*this.size/2.1),
        top:    Math.round(this.size/2 - Math.cos(this.value)*this.size/2.1)};

    $(this.container).find('.marker').css(coords);
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype.updateSlideCallbacks = function()
{
    if(typeof this.opts.slide == "function")
    {
        this.opts.slide(this, this.value);
    }
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype.updateChangeCallbacks = function()
{
    if(typeof this.opts.change == "function")
    {
        this.opts.change(this, this.value);
    }
};

//------------------------------------------------------------------------------
// Capture mouse
ce4.leaflet.controls.RadialControl.prototype.mousedown = function(event)
{
    if (!document.dragging)
    {
      $(document).bind('mousemove', $.proxy(this.mousemove, this))
            .bind('mouseup', $.proxy(this.mouseup, this));
      document.dragging = true;
    }
    this.mousemove(event);
    return false;
};

//------------------------------------------------------------------------------
// Update mouse dragging
ce4.leaflet.controls.RadialControl.prototype.mousemove = function(event)
{
    var coords = this.relativeCoords(event);
    var angle = Math.atan2(coords.x, -coords.y);
    this.setValue(angle, true);
    return false;
};

//------------------------------------------------------------------------------
// Returns coordinates relative to the center of the control
ce4.leaflet.controls.RadialControl.prototype.relativeCoords = function(event)
{
    var offset = $(this.container).offset();
    return {
        x: Math.round(event.pageX - offset.left - this.size/2),
        y: Math.round(event.pageY - offset.top - this.size/2)
    };
};

//------------------------------------------------------------------------------
// Uncapture mouse
ce4.leaflet.controls.RadialControl.prototype.mouseup = function(event)
{
    this.updateChangeCallbacks();
    $(document).unbind('mousemove', this.mousemove);
    $(document).unbind('mouseup', this.mouseup);
    document.dragging = false;
    return false;
};

//------------------------------------------------------------------------------
// Restricts the marker to stay within the specified range
//    First arg is the most-counterclockwise angle
//    Second arg is the available range extending clockwise from it
//    Both angles should be between [-PI, PI].
ce4.leaflet.controls.RadialControl.prototype.setRange = function(ccw, cw)
{
    this.range = [ccw, cw];
    this.containMarker();
    this.updateDisplay();
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.RadialControl.prototype.containMarker = function()
{
    if(this.range == undefined) return;
    var r0 = this.range[0];
    var r1 = this.range[1];
    if(r0 <= r1 && (this.value >= r0 && this.value <= r1))
        {
        return;
    }
    else if(r0 > r1 && (this.value >= r0 || this.value <= r1))
    {
        return;
    }
    this.value = r0;
};

//------------------------------------------------------------------------------
// Returns value from 0 to 1.0 representing the marker's position within the range
// Returns undefined if there is no set range
ce4.leaflet.controls.RadialControl.prototype.getPositionInRange = function()
{
    return (this.range == undefined) ? undefined : (this.value-this.range[0])/(this.range[1]-this.range[0]);
};

//------------------------------------------------------------------------------
ce4.leaflet.controls.containAngle = function(a)
{
    while(a > Math.PI)  a -= 2*Math.PI;
    while(a < -Math.PI) a += 2*Math.PI;
    return a;
};

