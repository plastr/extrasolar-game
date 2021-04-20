// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.ui contains the page navigation and display as well as the history tracking code.
goog.provide('ce4.ui');
goog.provide('ce4.ui.map'); // The currently displayed ExtraSolarMap instance.

goog.require('ce4.util');
goog.require('ce4.planet');
goog.require('ce4.gamestate');
goog.require('ce4.mission.callbacks');
goog.require('ce4.leaflet.ExtraSolarMap');
goog.require('ce4.boxTagger');

goog.require('xri.ui');
goog.require('xri.validation');

goog.require('ce4.ui.product');

// List of page tags/names, hash values in URL.
ce4.ui.PROFILE = "profile";
ce4.ui.MAIL = "mail";
ce4.ui.MESSAGE = "message";
ce4.ui.LEAFLET = "map";
ce4.ui.GALLERY = "gallery";
ce4.ui.PICTURE = "picture";
ce4.ui.MOBILE_PICTURE = "mobile_picture"  // Mobile only
ce4.ui.ACCOUNT = "account"                // Mobile only
ce4.ui.TASKS = "tasks";
ce4.ui.CATALOG = "catalog";
ce4.ui.HOME = "home";
ce4.ui.COPYRIGHT = "copyright";
ce4.ui.TASK = "task";
ce4.ui.CLASSROOM = "classroom";

ce4.ui.MAX_MISSION_ONE_TYPE             = 17; // Maximum missions to display if there is only 1 type of mission
ce4.ui.MAX_MISSION_TWO_TYPES            = 16; // Maximum missions to display if there are 2 types of missions, MUST BE AN EVEN NUMBER!!!
ce4.ui.PER_PAGE_SPECIES                 = 12; // Species items to display per page

ce4.ui.MAX_HOME_MESSAGES                = 8;  // Maximum messages on the home tab

ce4.ui.MAX_GALLERY_IMAGES               = 10000; // Maximum images to list in the gallery

ce4.ui.MAP_AUTO_FULLSCREEN_WIDTH        = 1029; // Automatically enter fullscreen below width and height
ce4.ui.MAP_AUTO_FULLSCREEN_HEIGHT       = 825;

ce4.ui.IMAGE_PANORAMA_SMALL_WDITH       = 2400;
ce4.ui.IMAGE_PANORAMA_SMALL_HEIGHT      = 600;
ce4.ui.IMAGE_PANORAMA_LARGE_WDITH       = 5120;
ce4.ui.IMAGE_PANORAMA_LARGE_HEIGHT      = 1280;

ce4.ui.MOBILE_THUMB_IMAGE_DEFAULT_WIDTH = 200;
ce4.ui.MOBILE_THUMB_IMAGE_PADDING       = 2*2 + 6*2;

ce4.ui.is_mobile = window.is_mobile;

// Stores the current "page", which is the page name and any additional history parts, e.g. UUIDs.
ce4.ui.current_page = null;
// Stores just the current page name, e.g. "map"
ce4.ui.current_page_name = null;

//------------------------------------------------------------------------------
ce4.ui.load_page = function (tag, bForceReload) {
    if (ce4.ui.current_page !== tag || bForceReload === true)
    {
        var parts = tag.split(','),
            name = parts.shift();

        // Mobile uses a slightly different set of templates and page_funcs.
        if (name === ce4.ui.PICTURE && ce4.ui.is_mobile) {
            name = ce4.ui.MOBILE_PICTURE;
        }
        else if (name === ce4.ui.MOBILE_PICTURE && !ce4.ui.is_mobile) {
            name = ce4.ui.PICTURE;
        }
        if (name === ce4.ui.ACCOUNT && !ce4.ui.is_mobile) {
            name = ce4.ui.PROFILE;
        }

        var oldparts = (ce4.ui.current_page ? ce4.ui.current_page.split(',') : null),
            oldname = (oldparts ? oldparts.shift() : null),
            pageobj = ce4.ui.page_funcs[name],
            args = ce4.ui.get_cb(name, 'args').call(pageobj, ce4.ui.parse_args(parts.shift())),
            page_tmpl = $("#" + name + "_page");
        try
        {
            if (oldname)
            {
                ce4.ui.get_cb(oldname, 'unload').apply(ce4.ui.page_funcs[oldname]);
                ce4.mission.callbacks.unload_page(ce4.ui.current_page);
            }
        }
        catch(err)
        {
            console.error("Page unload error", err);
        }

        // Scroll element to top of the screen
        if(!ce4.ui.reloading) $('#content').scrollTop(0);

        $("#content").html($.tmpl(page_tmpl, {args:args}));
        document.title = "Extrasolar" + (tag != ce4.ui.HOME ? " - " + page_tmpl.attr('title') : "");
        ce4.ui.current_page = tag;
        ce4.ui.current_page_name = name;

        window.location.hash = tag; // NOTE: This is replicating: $.history.load(tag), encodeURIComponent causes issues with some browsers, probably not needed? (, becomes %2C);

        try
        {
            ce4.ui.get_cb(name, 'load').apply(pageobj, [args]);
            ce4.mission.callbacks.load_page(tag);
        }
        catch(err)
        {
            if(tag !== 'home')
            {
                window.location.hash = 'home';
            }
            else
            {
                console.error("Page load error", err);
                $("#content").html('<div class="error">Error in loading page ' + name + ': ' + err + '</div>');
            }
        }

        var clicked_tab_name = ce4.ui.page_funcs[name].tabName.substring(4,13).toString();

        if(clicked_tab_name === ce4.ui.HOME)
        {
            $(".xri-tabs li").removeClass("active");
            $("#home_tab").addClass("active");
        } else if (clicked_tab_name === ce4.ui.LEAFLET)
        {
            $(".xri-tabs li").removeClass("active");
            $("#map_tab").addClass("active");
        } else if (clicked_tab_name === ce4.ui.PROFILE){
            $(".xri-tabs li").removeClass("active");
            $("#profile_tab").addClass("active");
        } else if (clicked_tab_name === ce4.ui.CLASSROOM){
            $(".xri-tabs li").removeClass("active");
            $("#classroom_tab").addClass("active");
        }

        // Display level information
        // FUTU: pass a callback function to dialogOpen to update the level after store checkout is complete
        // FUTU: Store this data in a ce4.user.Level object which wraps current_voucher_level
        var current_voucher_key = ce4.gamestate.user.current_voucher_level;
        if      (current_voucher_key === "VCH_ALL_PASS") $("#xri-wrapper > header, .mobile-menu-item-upgrade").addClass("level-all-pass").find(".level .title").html("Pioneer");
        else if (current_voucher_key === "VCH_S1_PASS")  $("#xri-wrapper > header, .mobile-menu-item-upgrade").addClass("level-s1-pass").find(".level .title").html("Associate");
        else    $("#xri-wrapper > header, .mobile-menu-item-upgrade").addClass("level-volunteer").find(".level .title").html("Volunteer");

        // If some instances, like Edmodo users, we may hide store and invitation buttons.
        if (ce4.gamestate.user.is_store_enabled()) {
            $("#xri-wrapper .upgrade").show();
        }
        else {
            $(".profile-upgrade > button").hide();
            $(".profile-invites-left").hide();
        }

        // Some data contain cross-links to other tabs, denoted by spans with the ce4_crosslink class.  Update those now.
        ce4.ui.update_crosslinks();
    }
    ce4.ui.update_title_unviewed_alerts();
};


//------------------------------------------------------------------------------
ce4.ui.page_funcs = {
    // ==================== MAIL ====================
    mail: {
        tabName : "tab_home",
        load: function(args) {
            ce4.ui.populate_message_list($(".messages-holder"));

            if(!ce4.ui.is_mobile) {
                $('.xri-inbox').pajinate({
                    item_container_id : '.messages-list tbody', // tbody needed for tables
                    nav_panel_id : '.page_navigation',
                    nav_label_info : 'Page {3} of {4}',
                    num_page_links_to_display : 0,
                    items_per_page : 18,
                    show_first_last: false,
                    nav_label_prev : 'Newer',
                    nav_label_next : 'Older',
                    nav_label_ellipse:'',
                    start_page : 0
                });
            }

            // Update unviewed counts
            ce4.ui.update_unviewed_message_count();
        },
        unload: function() {
        }
    },
    // ==================== MESSAGE ====================
    message: {
        tabName : "tab_home",
        load: function(args) {
            // Use this function to update our DOM after we fetch the message contents.
            // Note: The gamestate message object will be unlocked and marked read by chips handling.
            var on_message_response = function(response) {
                // If this is the native app, we need to alter image paths slightly to properly
                // reference the local image.
                if (ce4.util.is_native()) {
                    response.content_html = response.content_html.replace('"/static/', '"static/');
                }

                // Insert the message content into the page.
                $('#message').html(response.content_html);
                $('#message_title').html(args.msg.subject);
                $('#message_from').html(args.msg.sender);
                if (ce4.gamestate.user.email)
                    $('#message_to').html(ce4.gamestate.user.email);
                else
                    $('#message_to').html(ce4.gamestate.user.first_name + ' ' + ce4.gamestate.user.last_name);
                $('#message_subject').html(args.msg.subject);
                $('#message_date').html(args.msg.sent_at_date());

                // Set page title to message subject.
                document.title = "Extrasolar - Mail: " + args.msg.subject;


                // Set up XRI live call button
                call_button = $('.message_call_button').html('<div class="message-call-container">'
                    + '<table width="100%" border=0px cellspacing=0 cellpadding=8px style="margin:0px;"><tr>'
                    + '<td rowspan=2 bgcolor="#d0d0d0" align="center" style="width:60px; vertical-align:middle"><img src="'+ce4.util.url_static('/static/img/messages/phone_large.png')+'"></td>'
                    + '<td width=><button class="gradient-button gradient-button-standard gradient-button-stretch" onclick="">Start Live Call</button></td>'
                    + '<td rowspan=2 style="width=60px; text-align:right; vertical-align:middle"><img src="'+ce4.util.url_static('/static/img/messages/XRI_logo_small.png')+'"></td>'
                    + '</tr><tr><td>'+$('.message_call_button').data('participants')+'</td></tr></table></div>');
                call_button.click(function(){
                    ce4.util.json_post({
                        url: $('.message_call_button').data('url'),
                        data: {'password': $('.message_call_button').data('key')},
                        success: function(response) { ce4.ui.reload_current_page(); },
                        error: function() { console.log("Error initiating call."); }
                    });
                });


                // Set up kryptex call terminal
                var makecall = function (echo, command) {
                    var term = this;
                    var strParticipants = $('.message_call_form').data('participants').split(',').join(' ');
                    ce4.util.json_post({
                        url: $('.message_call_form').data('url'),
                        data: {'password': $('.message_call_form').data('key')},
                        success: function(response) { on_message_response(response); echo("call connected"); setTimeout(function(){ term.dialog('close');}, 2000); },
                        error: function() { echo("Error initiating call."); }
                    });
                    echo("initiating call\n~/scripts/initcall -p " + strParticipants + "\n...");
                };
                $('.message_call_form').html($("<a class='clickable'><img src='"+ce4.util.url_static('/static/img/messages/terminal.png')+"'> Click to launch Terminal</a>").click(function()
                {
                    var arrParticipants = $('.message_call_form').data('participants').split(',');
                    var strParticipants = arrParticipants.join(' ');
                    var strVerify = '';
                    for (var i = 0; i < arrParticipants.length; i++) {
                        strVerify += 'checking status of ' + arrParticipants[i] + '... available.\n';
                    }
                    ce4.ui.terminal.open(   "executing grpcall.pl -p " + strParticipants + "\n"
                                          + "type 'verify' to check status of participants",
                                          [ {expression: /^verify$/i,   action: function(echo, command){ echo(strVerify + "all participants online.  type 'call' to begin call:"); }},
                                            {expression: /^call$/i,     action: makecall} ]
                    );
                }));


                // Set up kryptex password terminal
                var password = function (echo, command) {
                    ce4.util.json_post({
                        url: $('.message_pass_form').data('url'),
                        data: {'password': command},
                        success: function(response) { on_message_response(response); echo(response.was_unlocked ? "**** DOCUMENT DECRYPTED ****\ntype 'exit' to view document." : "decryption failed.\nenter password or type 'exit' to cancel:"); },
                        error: function() { echo("Error submitting message password."); }
                    });
                    echo("attempting document decryption...");
                };
                $('.message_pass_form').html($("<a class='clickable'><img src='"+ce4.util.url_static('/static/img/messages/terminal.png')+"'> Click to launch Terminal</a>").click(function()
                {
                    ce4.ui.terminal.open(   "executing chkpswd.pl\n"
                                          + "enter password or type 'exit' to cancel:\n",
                                          [ {expression: /^.+$/i,  action: password} ]
                    );
                }));


                // Set up kryptex authentication terminal
                var authenticate = function (echo, command) {
                    ce4.util.json_post({
                        url: $('.ce4_authenticate_form').data('url'),
                        data: {'password': command},
                        success: function(response) { on_message_response(response); echo(response.was_unlocked ? "**** USER AUTHENTICATED ****\ntype 'exit' to close terminal." : "incorrect password.\nenter password or type 'exit' to cancel:"); },
                        error: function() { echo("Error submitting password."); }
                    });
                    echo("attempting to reauthenticate user with password...");
                };
                $('.ce4_authenticate_form').html($("<a class='clickable'><img src='"+ce4.util.url_static('/static/img/messages/terminal.png')+"'> Click to launch Terminal</a>").click(function()
                {
                    ce4.ui.terminal.open(   "executing authenticate.pl\n"
                                          + "enter password or type 'exit' to cancel:\n",
                                          [ {expression: /^.+$/i,  action: authenticate} ]
                    );
                }));


                // Set up kryptex forwarding terminal
                var forward = function (echo, command, recipient) {
                    ce4.util.json_post({
                        url: $('.ce4_message_fwd_form').data('url'),
                        data: {'recipient': recipient},
                        success: function() { echo("Sent!"); },
                        error: function() { echo("Error forwarding attachment."); }
                    });
                    echo("Forwarding message...");
                };
                $('.ce4_message_fwd_form').html($("<a class='clickable'><img src='"+ce4.util.url_static('/static/img/messages/terminal.png')+"'> Click to launch Terminal</a>").click(function()
                {
                    ce4.ui.terminal.open(   "executing secure_send.pl\n"
                                          + "to cancel, type 'exit'.  to forward document, type\n"
                                          + "'forward <recipient>'.  Recipient options:\n"
                                          + (ce4.gamestate.user.progress.contains('PRO_ENABLE_FWD_TO_EXOLEAKS') ? " . enki\n" : "")
                                          + " . jane\n"
                                          + " . kryptex\n"
                                          + " . turing",
                                          [ {expression: /^[\s']*forward .?kryptex.?[\s']*$/i,  action: forward, params: ["KRYPTEX"]},
                                            {expression: /^[\s']*forward .?turing.?[\s']*$/i,   action: forward, params: ["TURING"]},
                                            {expression: /^[\s']*forward .?jane.?[\s']*$/i,     action: forward, params: ["JANE"]},
                                            {expression: /^[\s']*forward .?enki.?[\s']*$/i,     action: forward, params: ["ENKI"]},
                                            {expression: /^[\s']*forward[\s']*$/i,          action: function(echo, command){echo("Type: forward <recipient>");}},
                                            {expression: /^[\s']*forward .*$/i,       action: function(echo, command){echo("Unable to forward, invalid recipient:"+command.substr(command.indexOf(' ')));}}]
                    );
                }));
                ce4.ui.update_crosslinks();

                // On mobile, resize images and videos to fit.
                if(ce4.ui.is_mobile) {
                    jQuery(window).on("resize", ce4.ui.mobile_resize_message_content);
                    ce4.ui.mobile_resize_message_content();
                }
            };

            // Set sender icon
            $(".mail-thumb").html("<img src='" + ce4.ui.get_sender_icon(args.msg.sender_key) + "72x72.png' />");

            // Set previous and next links
            var prev_url = ce4.ui.message_prev_url(args.msg.message_id);
            var next_url = ce4.ui.message_next_url(args.msg.message_id);
            if(prev_url != '') $('.previous_link').add('.first_link').removeClass('no_more ').prop("href", prev_url);
            else $('.previous_link').bind('click', false);
            if(next_url != '') $('.next_link').add('.last_link').removeClass('no_more ').prop("href", next_url);
            else $('.next_link').bind('click', false);

            // Load the message content via AJAX call.
            ce4.util.json_get({
                url: ce4.util.url_api(args.msg.urls.message_content),
                success: on_message_response,
                error: function() {
                    console.log("Error fetching mail message.");
                    $('#message').html("<p>Error loading message.</p>");
                }
            });

            $("#content").addClass("elastic");
            $("#content .xri-pane").addClass("elastic");

            // Update unviewed counts
            ce4.ui.update_unviewed_message_count();
        },
        unload : function(){
            $("#content").removeClass("elastic");
            $("#content .xri-pane").removeClass("elastic");
            if(ce4.ui.is_mobile) {
                jQuery(window).off("resize", ce4.ui.mobile_resize_message_content);
            }
        },
        // Get the parameters that will be passed to the jQuery templating system.
        args: function(p) {
            return {msg: ce4.gamestate.user.messages.get(p.id)};
        }
    },
    // ==================== MAP (LEAFLET) ====================
    map: {
        tabName : 'tab_map',
        load: function(args) {
            // If no map DOM element has been created, create it now and attach it.
            if(ce4.cache == undefined) ce4.cache = {};
            if(ce4.cache.leaflet == undefined) {

                // Preload the direction wizard images
                $([ce4.util.url_static('/img/dw/direction_groundIndicator_handle.png'),
                   ce4.util.url_static('/img/dw/direction_groundIndicator_handle_over.png'),
                   ce4.util.url_static('/img/dw/direction_groundIndicator_minimal.png')]).preload();

                ce4.ui.leaflet = new ce4.leaflet.ExtraSolarMap({ urls:ce4.gamestate.urls, user:ce4.gamestate.user });
            }
            // Otherwise, reattach the cached map DOM element.
            else
            {
                // When navigating away from the Map tab, the map is detached from the DOM but
                // kept in the ce4.cache namespace. If the Map has already been cached, then
                // be sure that its containing div is empty and then reattach the cached DOM.
                $('#map-container').children().remove();
                $('#map-container').append(ce4.cache.leaflet);

            }
            if (args.target)          ce4.ui.leaflet.centerTarget(args.target);
            if (args.region)          ce4.ui.leaflet.centerRegion(args.region);
            if (args.lat && args.lng) ce4.ui.leaflet.centerLatLng([args.lat, args.lng]);

            // Enter fullscreen if we were already fullscreen, or the window size is small
            if(ce4.ui.set_fullscreen || ce4.ui.set_fullscreen === undefined && $(window).width() < ce4.ui.MAP_AUTO_FULLSCREEN_WIDTH && $(window).height() < ce4.ui.MAP_AUTO_FULLSCREEN_HEIGHT && !ce4.ui.is_mobile) ce4.ui.leaflet.enterFullscreen();

            ce4.ui.leaflet.onShow();

            ce4.gamestate.user.tutorial.begin(ce4.tutorial.ids.TUT01, {map: ce4.ui.leaflet});
        },
        unload: function() {
            // preserve state
            ce4.ui.set_fullscreen = ce4.ui.is_fullscreen;

            if(ce4.ui.is_fullscreen) ce4.ui.leaflet.exitFullscreen();

            if (ce4.ui.leaflet != undefined)
            {
                ce4.gamestate.user.tutorial.abort(ce4.tutorial.ids.TUT01);
                ce4.ui.leaflet.onHide();
            }
                        ce4.cache.leaflet = $("#leaflet-container").detach();

        },
        // The target_id is an optional argument that can be passed through the #map URL.
        args: function(p) {
            return { target: (p.t) ? ce4.gamestate.user.find_target(p.t) : null,
                      region: p.r,
                      lat:    p.lat,
                      lng:    p.lng};
        }
    },
    // ==================== GALLERY ====================
    gallery: {
        tabName : "tab_home",

        load: function() {
            ce4.ui.thumbs_list(ce4.ui.MAX_GALLERY_IMAGES);

            // disabled for consistency
            this.gallery_interval_id = setInterval(ce4.ui.updateThumbs, 1000);

            $(".xri-filter > input").button({icons: {primary:'xri-filter-check',label:'custom'}});

            if(!ce4.ui.is_mobile) {
                $('#photo-container').pajinate({
                    item_container_id : '#gallery-thumbnails',
                    nav_panel_id : '.page_navigation',
                    nav_label_info : 'Page {3} of {4}',
                    onPageDisplayed : xri.ui.lazyLoad,
                    num_page_links_to_display : 0,
                    items_per_page : 20,
                    show_first_last: false,
                    nav_label_prev : 'Newer',
                    nav_label_next : 'Older',
                    nav_label_ellipse:'',
                    start_page : 0
                });
                xri.ui.lazyLoad();
            }
            else
            {
                $(window).on( "resize", ce4.ui.mobile_gallery_thumbnail_size);
                $('#content').on("scroll", xri.ui.lazyLoadOnScreen, 250);
                xri.ui.lazyLoadOnScreen();
            }

            // Update unviewed counts
            ce4.ui.update_unviewed_photo_count();

            ce4.gamestate.user.tutorial.begin(ce4.tutorial.ids.TUT03, {page: 'gallery'});

            if ($('#gallery-thumbnails').children().length == 0) $(".newest-data").append('<p>Visit the <a href="#map">Map</a> to schedule new photos!</p> ');
        },
        unload: function() {
            ce4.gamestate.user.tutorial.abort(ce4.tutorial.ids.TUT03);
            if(ce4.ui.is_mobile) {
                $(window).off( "resize", ce4.ui.mobile_gallery_thumbnail_size);
                $('#content').off("scroll", xri.ui.lazyLoad);
            }
            clearInterval(this.gallery_interval_id);
        }
    },
    // ==================== PICTURE ====================
    picture: {
        tabName : 'tab_home',

        load: function(args) {
            var bocks;

            // Set up the links for the social sharing buttons.
            ce4.ui.initPictureSocial(args.target, false);

            if(args.target.is_panorama()) {
                // FUTU: onDragStop function should probably be called dynamically as the the image is dragged, requires modification of the jParadrag library
                $('#image-drag').jParadrag({
                    width: 800,
                    height: 600,
                    startPosition: ce4.ui.current_panorama_position && ((ce4.ui.current_panorama_position * ce4.ui.IMAGE_PANORAMA_SMALL_WDITH + ce4.ui.IMAGE_PANORAMA_SMALL_WDITH - 800 / 2) % ce4.ui.IMAGE_PANORAMA_SMALL_WDITH) || 800,
                    loop: true,
                    factor: 1,
                    momentum: {avg: 3, friction: 0.4},
                    onMomentumStop: function() {
                        var pos = $("#image-drag .ui-draggable").position().left;
                        bocks.panoramaShift(pos, 800);
                        ce4.ui.current_panorama_position = Math.abs(((pos - 800 / 2) % ce4.ui.IMAGE_PANORAMA_SMALL_WDITH) / ce4.ui.IMAGE_PANORAMA_SMALL_WDITH);
                    },
                    onLoad: xri.ui.panorama_pan_buttons
                });
            }
            var picture_loaded = function(loadevt) {
                $('#picture-detailed').unbind('load');

                var alreadyScored = false;
                var totalTags = args.target.image_rects.getCount();
                var cbFailed = function() {
                    // Hide the loading icon.
                    $("#id-image-rects-loading").hide();
                };
                var cbSuccess = function() {
                    // Reload to update the tags.
                    ce4.ui.reload_current_page();
                };

                // if there's a rect already, let's hook it up
                var setSelect;
                if (!args.target.image_rects.isEmpty()) {
                    var image_rect = args.target.image_rects.get(0);
                    alreadyScored = true;
                    if (bocks) bocks.disable();
                }


                if(args.target.is_panorama()) {
                    bocks = $.bocks('#picture-detailed', {}, ce4.ui.IMAGE_PANORAMA_SMALL_WDITH * 3, ce4.ui.IMAGE_PANORAMA_SMALL_HEIGHT, ce4.ui.IMAGE_PANORAMA_SMALL_WDITH, function(){return $(".ui-draggable").position() && $(".ui-draggable").position().left || -3200;}); // TODO: Can we use .load to wait for .ui-draggable to have a position?
                }
                else {
                    bocks = $.bocks('#picture-detailed', {}, 800, 600);
                    $('.bocks-selContainer').draggable({ containment: "parent" }); // Needed to allow touch punch to function and make bocks draggable on mobile
                }
                bocks.on('cancelSelection', function () { $("#id-species-identified #species-tags li:last").remove(); totalTags -= 1;});

                if (alreadyScored) {
                    bocks.disable();
                    if (!args.target.image_rects.isEmpty()) {
                        bocks.setSelectionList(args.target.image_rects.unsorted());
                    }
                }

                $('#id-species-submit').show();

                ce4.gamestate.user.tutorial.begin(ce4.tutorial.ids.TUT04, {bocks: bocks, page: 'picture'});

                ce4.ui.get_current_bocks = function(){return bocks;};

                // Mark the target image as having been viewed if not previously viewed.
                args.target.markViewed();

                // Display submitted tags
                $.each(args.target.get_detected_species_data(), function(i, species_data){
                    var discovery;
                    var options = {tabid: species_data.seq, url:'#catalog'};
                    if (species_data.species_id === null) {
                        discovery = ce4.ui.DISCOVERY_INSUFFICIENT;
                    }
                    else if (ce4.species.is_too_far_for_id(species_data.species_id)) {
                        discovery = ce4.ui.DISCOVERY_TOO_FAR;
                    }
                    else {
                        discovery = ce4.gamestate.user.species.get(species_data.species_id);
                        options['url'] = ce4.util.url_catalog({id: species_data.species_id});
                    }
                    $("#species-ids").append(ce4.ui.create_catalog_item(discovery, options));
                });

                $('#id-add-tag').click(function()
                {
                    // Maximum of 3 tags
                    if(totalTags < 3)
                    {
                        // Increment tags
                        totalTags += 1;

                        // Add the region tag and create button handler
                        $("#id-species-identified #species-tags").append(ce4.ui.create_catalog_item(ce4.ui.DISCOVERY_NEWTAG, {tabid: bocks.addSelection()}));

                        // Enable submit button
                        $("#id-species-submit").attr('disabled', false);
                    }
                });

                // The submit button is disabled until at least 1 selection region is added.
                $('#id-species-submit').attr('disabled', true);
                $('#id-species-submit').click(function()
                {
                    // If any button is click, all buttons should be disabled until the
                    // response prompts a refresh of this page.
                    $("#id-species-submit").attr('disabled', true);
                    // Show the loading icon.
                    $("#id-image-rects-loading").show();
                    if (bocks) {
                        var coords = bocks.getSelectionList();
                        args.target.checkSpecies(coords, cbSuccess, cbFailed);
                    }
                    else {
                        console.log("Error: It looks like the bocks class is missing.");
                    }
                });

                // Toggle between infrared and visible light images and modify the links for social sharing.
                $('#id-photo-toggle-infrared').click(function()
                {
                    // Toggle image
                    if ($('#picture-detailed').attr('src') == ce4.util.url_static(args.target.images.INFRARED)) {
                        $('#picture-detailed').attr('src', ce4.util.url_static(args.target.images.PHOTO));
                        ce4.ui.initPictureSocial(args.target, false);
                    }
                    else {
                        $('#picture-detailed').attr('src', ce4.util.url_static(args.target.images.INFRARED));
                        ce4.ui.initPictureSocial(args.target, true);
                    }

                    // Show loading div
                    if($("#image-container").find('.loading-underlay').length == 0) {
                        var hide_loading_underlay = function(){ $('.loading-underlay').hide(); $('#picture-detailed').off("load", hide_loading_underlay); };
                        $("#image-container").append($('<div/>').addClass('loading-underlay'));
                        $('#picture-detailed').on("load", hide_loading_underlay);
                    }
                });
            };

            $('id-species-submit').hide();
            // defer all our stuff until the big image loads
            $('#picture-detailed').load(picture_loaded);

            // Display thumbnail list
            ce4.ui.displayThumbStrip($("#thumbnails"), ce4.gamestate.user.processed_picture_targets_list(), args.target.target_id);

            // Update unviewed counts
            ce4.ui.update_unviewed_photo_count();

            $("#content").addClass("elastic");
            $("#content .xri-pane").addClass("elastic");
        },
        args: function(p) {
            // If we're in the simulator, mock up a dummy target with the appropriate parameters.
            if (p.id === "simulator") {
                return {target: new ce4.target.Target({target_id: "simulator",
                    start_time: 100,
                    arrival_time: 200,
                    picture: 1,
                    processed: 1,
                    classified: 1,
                    highlighted: 0,
                    // Set viewed_at to an epoch-like value so markViewed is a no-op for
                    // this dummy target.
                    viewed_at: 123,
                    can_abort_until: null,
                    lat: 0.0,
                    lng: 0.0,
                    yaw: 0.0,
                    pitch: 0.0,
                    images: {"PHOTO":ce4.util.url_static("/img/scenes/simulator_photo.jpg")},
                    metadata: {},
                    urls: {"public_photo":""}
                })};
            }
            return {target: ce4.gamestate.user.find_target(p.id)};
        },
        unload : function(){

            if(ce4.ui.is_fullscreen && !ce4.ui.reloading) ce4.ui.fullscreen(false);

            if(!ce4.ui.reloading) delete ce4.ui.current_panorama_position;

            ce4.gamestate.user.tutorial.abort(ce4.tutorial.ids.TUT04);
            $("#content").removeClass("elastic");
            $("#content .xri-pane").removeClass("elastic");
        }
    },
    // ==================== MOBILE_PICTURE ====================
    mobile_picture: {
        tabName : 'tab_home',

        load: function(args) {
            var picture_loaded = function() {
                // TODO: As the player zooms in, load the high-res photo in the background and
                // display it instead when loaded.

                var totalTags = args.target.image_rects.getCount();
                var cbFailed = function() {
                    // Hide the loading icon.
                    $("#id-image-rects-loading").hide();
                };
                var cbSuccess = function() {
                    // Reload to update the tags.
                    ce4.ui.reload_current_page();
                };

                // If we already have some image_rects, display them.
                var setSelect;
                if (!args.target.image_rects.isEmpty()) {
                    for (var i=0; i<args.target.image_rects.getCount(); i++) {
                        var rect = args.target.image_rects.get(i);

                        var discovery;
                        var species_url = '';
                        if (rect.species_id === null) {
                            discovery = ce4.ui.DISCOVERY_INSUFFICIENT;
                        }
                        else if (ce4.species.is_too_far_for_id(rect.species_id)) {
                            discovery = ce4.ui.DISCOVERY_TOO_FAR;
                        }
                        else {
                            discovery = ce4.gamestate.user.species.get(rect.species_id);
                            species_url = ce4.util.url_catalog({id: rect.species_id});
                        }
                        ce4.boxTagger.addLabeledBox(rect.xmin, rect.ymin, rect.xmax - rect.xmin, rect.ymax - rect.ymin, discovery.name);
                    }
                }

                ce4.gamestate.user.tutorial.begin(ce4.tutorial.ids.TUT04, {bocks: ce4.boxTagger, page: 'mobile_picture'});

                /*
                // TODO: Do something when mini tags in toolbar are clicked. Maybe highlight the tag?
                // Or jump to the species catalog.
                */

                // Mark the target image as having been viewed if not previously viewed.
                args.target.markViewed();

                // If we already have 3 tags, disable the "Add" button.
                if(ce4.boxTagger.boxes.length >= 3) {
                    $('#id-add-tag').attr('disabled', true);
                }

                $('#id-add-tag').click(function()
                {
                    // Maximum of 3 tags
                    if(ce4.boxTagger.boxes.length >= 2) {
                        // Adding our last tag now.
                        $('#id-add-tag').attr('disabled', true);
                    }
                    if(ce4.boxTagger.boxes.length < 3) {
                        ce4.boxTagger.addBox();

                        // Enable submit button
                        $("#id-species-submit").attr('disabled', false);
                    }
                });

                // The submit button is disabled until at least 1 selection region is added.
                $('#id-species-submit').attr('disabled', true);
                $('#id-species-submit').click(function()
                {
                    // If any button is click, all buttons should be disabled until the
                    // response prompts a refresh of this page.
                    $("#id-species-submit").attr('disabled', true);
                    // Show the loading icon.
                    $("#id-image-rects-loading").show();
                    var coords = ce4.boxTagger.getSelectionList();
                    args.target.checkSpecies(coords, cbSuccess, cbFailed);
                });


                // TODO: Toggle between infrared and visible light images and modify the links for social sharing.
                $('#id-photo-toggle-infrared').click(function()
                {
                    // Show the loading icon until the image is loaded.
                    $('#id-photo-loading').show();

                    // Toggle the infrared image. If the image is loaded, it will trigger the on_hide_loader callback.
                    ce4.boxTagger.toggleInfrared(args.target.images.INFRARED);
                });
            };

            // Callback function when a tag is added or deleted.
            var on_tag_change = function() {
                // Show the list of tags in the toolbar footer.
                for (var i=0; i<3; i++) {
                    if (i < ce4.boxTagger.boxes.length) {
                        $('#id-mini-photo-tag'+(i+1)).html(''+(i+1));
                        $('#id-mini-photo-tag'+(i+1)).addClass('submitted');
                    }
                    else {
                        $('#id-mini-photo-tag'+(i+1)).html('&nbsp');
                        $('#id-mini-photo-tag'+(i+1)).removeClass('submitted');
                    }
                }
                // If there are no unsubmitted tags, disable the submit button.
                if (ce4.boxTagger.boxes.length === 0 || ce4.boxTagger.boxes[ce4.boxTagger.boxes.length-1].is_locked) {
                    $('#id-species-submit').attr('disabled', true);
                }

                // If there are fewer than 3 tags, enable the add button.
                if (ce4.boxTagger.boxes.length < 3) {
                    $('#id-add-tag').attr('disabled', false);
                }
            }

            // Callback function to hide the loading icon.
            var hide_loader = function() {
                $('#id-photo-loading').hide();
            }

            // Initialize our boxTagger canvas and call the picture_loaded callback when the image is loaded.
            ce4.boxTagger.init(ce4.util.url_static(args.target.images.PHOTO), ce4.util.url_static(args.target.images.WALLPAPER), args.target.is_panorama(), picture_loaded, on_tag_change, hide_loader, args.target.yaw);

            $('id-species-submit').hide();
            // defer all our stuff until the big image loads
            //$('#picture-detailed').load(picture_loaded);

            // On resize, make sure our audio player fits on the screen.
            jQuery(window).on("resize", ce4.ui.mobile_resize_picture_content);
            ce4.ui.mobile_resize_picture_content();

            // Update unviewed counts
            ce4.ui.update_unviewed_photo_count();
        },
        args: function(p) {
            // If we're in the simulator, mock up a dummy target with the appropriate parameters.
            if (p.id === "simulator") {
                return {target: new ce4.target.Target({target_id: "simulator",
                    start_time: 100,
                    arrival_time: 200,
                    picture: 1,
                    processed: 1,
                    classified: 1,
                    highlighted: 0,
                    // Set viewed_at to an epoch-like value so markViewed is a no-op for
                    // this dummy target.
                    viewed_at: 123,
                    can_abort_until: null,
                    lat: 0.0,
                    lng: 0.0,
                    yaw: 0.0,
                    pitch: 0.0,
                    images: {"PHOTO":ce4.util.url_static("/img/scenes/simulator_photo.jpg")},
                    metadata: {},
                    urls: {"public_photo":""}
                })};
            }
            return {target: ce4.gamestate.user.find_target(p.id)};
        },
        unload : function(){
            jQuery(window).off("resize", ce4.ui.mobile_resize_picture_content);
            ce4.boxTagger.release();

            /*
            if(!ce4.ui.reloading) delete ce4.ui.current_panorama_position;
            */
            ce4.gamestate.user.tutorial.abort(ce4.tutorial.ids.TUT04);
        }
    },
    // ==================== MISSIONS ====================
    tasks: {
        tabName : "tab_home",

        load: function() {
           ce4.ui.update_unviewed_task_count();
           ce4.ui.populate_missions();
           $("#content .xri-pane").addClass("elastic");
        },
        unload: function() {
        }
    },
    // ==================== SINGLE MISSION ====================
    task: {
        tabName : "tab_home",

        load: function() {
            ce4.ui.update_unviewed_task_count();
            ce4.ui.populate_missions();
           $("#content .xri-pane").addClass("elastic");
        },
        unload: function() {
            if(!ce4.ui.reloading) delete ce4.ui.current_mission_id;
        }
    },
    // ==================== SPECIES CATALOG ====================
    catalog: {
        tabName : "tab_home",

        load: function(args) {

            var all_discoveries = ce4.gamestate.user.species_list();
            var categories = ["ALL"]

            var get_cid = function(cj) {
                return cj.slice("catalog,".length);
            };

            // Update unviewed counts
            ce4.ui.update_unviewed_catalog_count();

            // Was a specific species ID cached, or requested in the URL?
            var current_id = ce4.ui.current_species_id || get_cid(ce4.ui.current_page);
            var current_id_index = 0;

            // Populate catalog items
            $.each(all_discoveries, function(index, discovery) {
                if(ce4.ui.current_catalog_category == undefined || discovery.type == ce4.ui.current_catalog_category || ce4.ui.current_catalog_category == "ALL") {

                    var is_current = (current_id != undefined) && (discovery.species_id == current_id);
                    if(is_current) current_id_index = index;

                    $("#species-catalog").append(ce4.ui.create_catalog_item(discovery, {active: is_current }).click(ce4.ui.init_species_detail_handler(discovery.species_id)));
                }
                if($.inArray(discovery.type, categories) === -1) categories.push(discovery.type);
            });

            // Update the categories
            ce4.ui.populate_catalog_categories(categories, ce4.ui.current_catalog_category);
            if(current_id){
                $("#species-catalog li.active").removeClass('active').click();
            } else if (all_discoveries.length == 0) {
                $("#species-catalog").append('<p>To make new discoveries, click "Add Tag" on <a href="#gallery">Gallery</a> photos!</p> ');
            }

            if(!ce4.ui.is_mobile) {
                $('.xri-catalog').pajinate({
                    item_container_id : '#species-catalog',
                    nav_panel_id : '.page_navigation',
                    nav_label_info : 'Page {3} of {4}',
                    num_page_links_to_display : 0,
                    items_per_page : ce4.ui.PER_PAGE_SPECIES,
                    show_first_last: false,
                    nav_label_prev : 'Newer',
                    nav_label_next : 'Older',
                    nav_label_ellipse:'',
                    start_page : Math.floor((current_id_index) / ce4.ui.PER_PAGE_SPECIES)
                });
            }

            $("#content").addClass("elastic");
            $("#content .xri-pane").addClass("elastic");

        },
        unload: function() {
            if(!ce4.ui.reloading) {
                delete ce4.ui.current_species_id;
                delete ce4.ui.current_catalog_category;
            }
        },
        args: function(p) {
            return {species: ce4.gamestate.user.species_list()};
        }
    },
    // ==================== PROFILE ====================
    profile: {
        tabName : "tab_profile",

        load: function(args) {
            $("#content").addClass("elastic");
            $("#content .xri-pane").addClass("elastic");

            $("#logout-button").click(function() {
                ce4.ui.logout();
            });

            // Set up the function to handle notification settings changes
            if(!ce4.ui.is_mobile) ce4.ui.notification_settings_onchange();

            // Mark every achieved achievement as having been viewed if not previously viewed.
            ce4.gamestate.user.achievements.forEach(function(achievement) {
                if (achievement.was_achieved()) {
                    achievement.markViewed()
                }
            });

            var changeTooltipPosition = function(event) {
                var tooltipX = event.pageX - 8;
                var tooltipY = event.pageY + 8;
                $('div.description').css({top: tooltipY, left: tooltipX});
            };

            var showTooltip = function(event) {
              $(this).find('div').show();
              changeTooltipPosition(event);
            };

            var hideTooltip = function() {
              $(this).find('div').fadeOut(200);
            };

            $(".player-achievements li").bind({
               mouseenter : showTooltip,
               mouseleave: hideTooltip
            });
            ce4.ui.social.facebook.load();
            ce4.ui.social.twitter.load();
            ce4.ui.social.google.load();
        },
        unload : function(){
            // Mark all updates as having been viewed
            if(!ce4.ui.reloading) ce4.ui.clear_unviewed_alerts("profile");

            $("#content").removeClass("elastic");
            $("#content .xri-pane").removeClass("elastic");
        }
    },
    // ==================== ACCOUNT ====================
    account: {
        tabName : "tab_account",

        load: function(args) {
            $("#content").addClass("elastic");
            $("#content .xri-pane").addClass("elastic");

            $("#logout-button").click(function() {
                ce4.ui.logout();
            });

            // Set up the function to handle notification settings changes
            ce4.ui.notification_settings_onchange();

        },
        unload : function(){
            // Mark all updates as having been viewed
            if(!ce4.ui.reloading) ce4.ui.clear_unviewed_alerts("profile");

            $("#content").removeClass("elastic");
            $("#content .xri-pane").removeClass("elastic");
        }
    },
    // ==================== HOMEPAGE ====================
    home : {
        tabName : "tab_home",

        load: function(){

            if(!ce4.ui.is_mobile) {

                this.home_interval_id = setInterval(ce4.ui.updateThumbs, 1000);
                this.update_planet_status = setInterval(ce4.ui.homepage_surface_conditions, 10000);

                ce4.ui.populate_message_list($(".messages-holder"), ce4.ui.MAX_HOME_MESSAGES);
                ce4.ui.homepage_tasks_list();
                ce4.ui.homepage_thumbs_list();
                ce4.ui.homepage_surface_conditions();

                // Update unviewed counts
                ce4.ui.update_unviewed_message_count();
                ce4.ui.update_unviewed_photo_count();
                ce4.ui.update_unviewed_task_count();
                ce4.ui.update_unviewed_catalog_count();

                // Minimap: Set the crosshair position, and functionality for clicking coordinates
                 var showCross = function(e) { if(e.altKey) e.preventDefault(); $(".crosshairs img").toggleClass("crosshair", e.altKey); };
                $(".crosshairs img").css('backgroundPosition', ce4.ui.minimap_crosshair_position());
                $(".crosshairs img").click(function(e){
                    if(e.altKey) {
                        var coords = ce4.ui.minimap_position_coords(e.pageX - this.offsetLeft, e.pageY - this.offsetTop);
                        $(".crosshairs img").css('backgroundPosition', ce4.ui.minimap_crosshair_position([coords.lat, coords.lng]));
                    }
                    $(document).unbind("keydown", showCross);
                    $(document).unbind("keyup", showCross);
                    window.location.hash = ce4.util.url_map(coords || {});
                });
                $(".crosshairs img").hover(function() {
                        $(document).keydown(showCross);
                        $(document).keyup(showCross);
                    }, function() {
                        $(document).unbind("keydown", showCross);
                        $(document).unbind("keyup", showCross);
                   });

                // Species: Display the latest species IDed
                var latest_species = ce4.gamestate.user.species_list()[0] || ce4.ui.DISCOVERY_NONE;
                $("#catalog_preview").append(ce4.ui.create_catalog_item(latest_species, {url: ce4.util.url_catalog(latest_species.species_id && {id: latest_species.species_id})}));

                ce4.gamestate.user.tutorial.begin(ce4.tutorial.ids.TUT03, {page: 'home'});
            }
            else {
                ce4.ui.mobile_home_notifications();
            }
        },
        unload: function(){
            if(!ce4.ui.is_mobile) {
                // Mark all updates as having been viewed
                if(!ce4.ui.reloading) ce4.ui.clear_unviewed_alerts("home");

                ce4.gamestate.user.tutorial.abort(ce4.tutorial.ids.TUT03);
                clearInterval(this.home_interval_id);
                clearInterval(this.update_planet_status);
            }
        }
    },
    // ==================== CLASSROOM ====================
    classroom: {
        tabName : "tab_classroom",

        load: function() {
            if (ce4.gamestate.classroom == undefined) {
                return;
            }
            if (ce4.gamestate.classroom['error'] != undefined) {
                $('#classroom-data').html('Error loading classroom data: '+ce4.gamestate.classroom['error']);
                return;
            }

            // Format the data from ce4.gamestate.classroom as a table for each group.
            // We use the data in ce4.gamestate.classroom.columns as a guide for column labels and content.
            var html = "";
            var all_groups = ce4.gamestate.classroom.groups;
            var columns = ce4.gamestate.classroom.columns;
            for (var g=0; g<all_groups.length; g++) {
                group = all_groups[g];
                html += "<h3>"+group.title+"</h3><table border=1>";
                // First table row: labels.
                html += "<tr>";
                for (var c=0; c<columns.length; c++) {
                    html += "<td><strong>"+columns[c].label+"</strong></td>";
                }
                html += "</tr>";
                // One table row for each group member.
                for (var m=0; m<group.members.length; m++) {
                    var member = group.members[m];
                    html += "<tr>";
                    for (var c=0; c<columns.length; c++) {
                        html += "<td>";
                        if (columns[c].type == "string") {
                            html += member[columns[c].key] ? member[columns[c].key] : "";
                        }
                        else if (columns[c].type == "number") {
                            html += member[columns[c].key] ? member[columns[c].key].toString() : "0";
                        }
                        else if (columns[c].type == "check") {
                            html += member[columns[c].key] ? "&#x2713;" : "";  // Checkmark or empty.
                        }
                        else {
                            html += "unexpected type";
                        }
                        html += "</td>";
                    }
                    html += "</tr>";
                }
                html += "</table>";
            }
            $('#classroom-data').html(html);

            // Show a tooltip if you hover over any column.
            $("#classroom-data td").hover(
                function () {
                    $(this).css("background","#ffff80");
                    $('#classroom-tooltip').html("<strong>" + ce4.gamestate.classroom.columns[this.cellIndex].label
                        + "</strong>: " + ce4.gamestate.classroom.columns[this.cellIndex].tooltip);
                },
                function () {
                    $(this).css("background","");
                }
            );
        },
        unload: function() {

        }
    },
    // ==================== COPYRIGHTPAGE ====================
    copyright : {
        tabName : "tab_home",

        load: function(){

        },
        unload: function(){

        }
    },
    // ==================== UPGRADE ====================
    upgrade : {
        tabName : "tab_upgrade",

        load: function(){
            ce4.ui.store.mobileOpen();
        },
        unload: function(){
        }
    }

};


// ==================== UI Helper Funtions ====================

//------------------------------------------------------------------------------
// Create a species catalog item
ce4.ui.DISCOVERY_NONE         = { name: "None Identified", species_id: false, get_icon_url: function(){return ce4.assets.species.PENDING}, hasBeenViewed: function(){return true;}};
ce4.ui.DISCOVERY_INSUFFICIENT = { name: "Insufficient data for species ID ", species_id: false, get_icon_url: function(){return ce4.assets.species.PENDING}, hasBeenViewed: function(){return true;}, wrap: true};
ce4.ui.DISCOVERY_TOO_FAR      = { name: "Please get closer for accurate ID ", species_id: false, get_icon_url: function(){return ce4.assets.species.PENDING}, hasBeenViewed: function(){return true;}, wrap: true};
ce4.ui.DISCOVERY_NEWTAG       = { name: "Press Submit to begin analysis", species_id: false, get_icon_url: function(){return ce4.assets.species.UNKNOWN}, hasBeenViewed: function(){return true;}, wrap: true};

ce4.ui.create_catalog_item = function(discovery, options) {
        var item = $('  <li class="species-item clickable">\
                            <img src="'+ce4.util.url_static(discovery.get_icon_url(150, 150))+ (ce4.ui.is_mobile ? '" width="75" height="75"' : '" width="150" height="150"') + ' />\
                            <span class="title dwindle">'+discovery.name+'</span>\
                            <span class="notch-outer"></span>\
                            <span class="notch-inner"></span>\
                        </li>')
                    .toggleClass('active', options !== undefined && options.active !== undefined && options.active);

        if(discovery.wrap)                          item.find('.title').addClass('title-wrap');
        if(options !== undefined && options.tabid)  item.append('<span class="bocks-selIndex tabid">'+options.tabid+'</span>');
        if(!discovery.hasBeenViewed())              item.append('<span class="new-overlay"></span>');
        if(options !== undefined && options.url)    item.wrapInner('<a href="'+options.url+'"></a>');

        return item;
};

//------------------------------------------------------------------------------
// Reloads the currently displayed page.
ce4.ui.reload_current_page = function () {
    ce4.ui.reloading = true;
    ce4.ui.load_page(ce4.ui.current_page, true);
    delete ce4.ui.reloading;
};

//------------------------------------------------------------------------------
ce4.ui.find_nav_tabs = function (){
    var nav_links = $(".xri-tabs li a").attr("href");
    return nav_links;
};

//------------------------------------------------------------------------------
// Returns true if the current page name (e.g. 'map') matches the provided
// value. This ignores any additional history parts, e.g. UUIDs.
ce4.ui.is_current_page_name = function(page_name) {
    return page_name === ce4.ui.current_page_name;
};

//------------------------------------------------------------------------------
// Return true if the map interface has been loaded and displayed at least once. As it is
// lazily loaded this function is required to make sure it is available before use.
ce4.ui.is_map_loaded = function() {
    // Need to check to see if both the namespace exists and a valid function exists in the namespace
    // as Closure might have created the namespace even if the actual map object hasn't been loaded yet.
    return (ce4.ui.leaflet !== undefined && ce4.ui.leaflet.refreshUserData !== undefined);
};

//------------------------------------------------------------------------------
ce4.ui.history_callback = function(e) {
    var hash = window.location.hash.replace(/^#/, '');
    if (!hash) {
        // if no hash is supplied, choose a default page.
        if (!ce4.gamestate.user.progress.contains(ce4.tutorial.ids.TUT01)) {
            // If the first tutorial isn't done, start with the welcome message.
            hash = ce4.ui.MESSAGE + "," + ce4.gamestate.user.messages_list()[0].message_id;
        }
        else {
            hash = ce4.ui.HOME;
        }
    }
    if (ce4.ui.current_page !== hash) {
        // user hit back button (or first page load)
        ce4.ui.load_page(hash);
    }
};

//------------------------------------------------------------------------------
ce4.ui.get_cb = function(pagename, cbname) {
    var pageobj = ce4.ui.page_funcs[pagename];
    if(pageobj[cbname]) {
        return pageobj[cbname];
    } else {
        return function() {return [];};
    }
};

//------------------------------------------------------------------------------
// Previous messages url
ce4.ui.message_prev_url = function (message_id)
{
    var prev_message_url = '';
    if (ce4.gamestate.user.has_messages())
    {
        $.each(ce4.gamestate.user.messages_list(), function(i, message)
        {
            if(message.message_id == message_id) return false;
            prev_message_url = message.message_url();
        });
    }
    return prev_message_url;
};

//------------------------------------------------------------------------------
// Next messages url
ce4.ui.message_next_url = function (message_id)
{
    var next_message_url = '';
    var current_message_found = false;
    if (ce4.gamestate.user.has_messages())
    {
        $.each(ce4.gamestate.user.messages_list(), function(i, message)
        {
            if(current_message_found)
            {
                next_message_url = message.message_url();
                return false;
            }
            else if(message.message_id == message_id) current_message_found = true;
        });
    }
    return next_message_url;
};

//------------------------------------------------------------------------------
// homepage inbox list
ce4.ui.populate_message_list = function (messages_div, limit)
{
    var message_list = $("<table/>").addClass("messages-list");

    if (ce4.gamestate.user.has_messages())
    {
        $.each(ce4.gamestate.user.messages_list().slice(0, limit), function(i, message)
        {
           message_list.append(
                $("<tr id='"+ message.message_id +"'><td><img src='" + ce4.ui.get_sender_icon(message.sender_key) + "27x27.png' /> " + message.sender + "</td><td>" + message.icon() + message.subject + "</td><td>"+ message.format_sent_at() + "</td></tr>")
                    .click(function() {window.location.hash = message.message_url();})
                    .addClass(message.is_read() ? 'read': 'unread'));
        });
    }
    else
    {
        message_list.html("<p>No messages.</p>");
    }
    messages_div.append(message_list);
};


//------------------------------------------------------------------------------
ce4.ui.homepage_tasks_list = function (){

    //homepage missions list
    var notdone_missions = ce4.gamestate.user.notdone_missions("root");
    var done_mission = ce4.gamestate.user.done_missions("root");

    // Sort done missions by descending done_at time, not done missions by started_at time (secondary), and sort value (primary)
    notdone_missions.sort(function(a,b) {return b.started_at - a.started_at;});
    notdone_missions.sort(function(a,b) {return b.sort - a.sort;});
    done_mission.sort(function(a,b) {return b.done_at - a.done_at;});


    var max_total_missions = (notdone_missions.length && done_mission.length) ? 7 : 8; // show 8 messages if there is only 1 header
    var max_done_missions = done_mission.slice(0,(max_total_missions - notdone_missions.length));

    var create_task_item = function(mission) {
        return $("<li id='" + mission.mission_id + "'><a href='" + mission.mission_url() + "'><img src='"+mission.title_icon_url()+"'>&nbsp;" + mission.title + "</a></li>")
                            .click(function() {window.location.hash = mission.mission_url();})
                            .addClass('clickable')
                            .toggleClass('unviewed', !mission.hasBeenViewed());
    };

    $.each(max_done_missions, function(i, mission) { $(".messages-tasks #done_missions ul").append(create_task_item(mission)); });
    $.each(notdone_missions, function(i, mission){$(".messages-tasks #not_done_missions ul").append(create_task_item(mission)); });

    if (notdone_missions.length == 0) $(".messages-tasks #not_done_missions").hide();
    if (done_mission.length == 0)    $(".messages-tasks #done_missions").hide();
};


//------------------------------------------------------------------------------
ce4.ui.homepage_thumbs_list = function(){
    ce4.ui.thumbs_list(5);
    xri.ui.lazyLoad(); // TODO: this shouldn't be lazy loaded
    if (ce4.gamestate.user.picture_targets_list().length > 0) {
        var first_target = ce4.gamestate.user.picture_targets_list()[0];
        if (first_target.is_panorama() && first_target.images.THUMB_LARGE !== undefined) {
            $("section.rover-data ul li:first-child").addClass("bigger letterbox").find("img").attr("src", ce4.util.url_static(first_target.images.THUMB_LARGE));
        }
        else {
            $("section.rover-data ul li:first-child").addClass("bigger").find("img").attr("src", ce4.util.url_static(first_target.images.PHOTO));
        }
    }
};


//------------------------------------------------------------------------------
// Populate the gallery thumbnails
ce4.ui.thumbs_list = function(limit) {

    $.each(ce4.gamestate.user.picture_targets_list().slice(0, limit), function(i, target) {
        if(target.has_available_photo())
        {
            var thumb = xri.ui.makeThumbnail(ce4.util.url_static(target.images.THUMB || target.images.PHOTO), {
                    link:      target.picture_url(),
                    lazy:      true,
                    news:      !target.hasBeenViewed(),
                    sound:     target.has_sound(),
                    infrared:  target.has_infrared(),
                    tags:      target.image_rects.getCount(),
                    desc:      target.get_description(),
                    highlight: target.is_highlighted() });
        }
        else
        {
            // Create an empty span where we'll put a countdown timer.
            thumb = $('<li>'
                    + '<div id=\"pending-photo1\"><span id="arrival-time" class="arrival-text" data-arrival-time="'+(target.arrival_time)+'"></span>'
                    + (target.can_abort() && i == 0 ? '<span class="arrival-abort"><br><button class="gradient-button gradient-button-overlay" id="pending-photo-abort">Abort</button></span>' : '') + '</div>'
                    + '<div id=\"pending-photo2\" style=\"display:none;\">\
                        <span>uploading instructions<br>\
                        <img src=\"'+ce4.util.url_static('/img/XRI_logo_0001_satel-icn.png')+'\">\
                        <img src=\"'+ce4.util.url_static('/img/xri-loader.gif')+'\">\
                        <img src=\"'+ce4.util.url_static('/img/XRI_logo_0002_world-icn.png')+'\">\
                        <img src=\"'+ce4.util.url_static('/img/xri-loader.gif')+'\">\
                        <img src=\"'+ce4.util.url_static('/img/XRI_logo_0003_rover-icn.png')+'\">\
                       </span></div>'
                    + '<div id=\"pending-photo-fail\" style=\"display:none;\">\
                        <span class="arrival-text">Error while aborting photo.  Please try again.</span>\
                        <span class="arrival-abort"><button class=\"gradient-button gradient-button-overlay\" id=\"pending-photo-cancel\">OK</button></span>\
                       </div>'
                    +'<img src="'+ce4.util.url_static('/img/1x1.gif')+'"><p>Ready at '+ce4.util.localTimeAsStr(ce4.util.date_sans_millis(target.arrival_time_date()))+'</p></li>');
            thumb.addClass('unprocessed');
        }

        thumb.find('#pending-photo-cancel').click($.proxy(function() {ce4.util.toggleView('pending-photo', 'pending-photo1', 2); }, this));
        thumb.find("#pending-photo-abort").click($.proxy(function() {
                target.abort(function(){}, function(){ce4.util.toggleView('pending-photo', 'pending-photo-fail', 2);});
                ce4.util.toggleView('pending-photo', 'pending-photo1', 0);
                ce4.util.toggleView('pending-photo', 'pending-photo2', 1);
        }, this));

        $("#gallery-thumbnails").append(thumb);
    });
    if(ce4.ui.is_mobile) ce4.ui.mobile_gallery_thumbnail_size();
    ce4.ui.updateThumbs();
};


//------------------------------------------------------------------------------
// Populate the HTML for the social media section on the photo tab.  Adapt the
// data based on whether we want to show the standard or infrared picture.

ce4.ui.initPictureSocial = function(target, show_infrared) {
    if (!ce4.gamestate.user.is_social_enabled()) {
        return;
    }
    $('#id-picture-social').html('<span><a href="' + target.link_url_shared(show_infrared) + '" target="_blank"><img src="'+ce4.util.url_static('/img/link_share.png')+'"/></a></span>'
        + '<span class="facebook" style="display:none"><a href="#" id="id-picture-social-fb" onclick="return ce4.ui.social.facebook.share({link: \''
            + target.link_url_shared(show_infrared) + '\', picture: \'' + target.picture_url_shared(show_infrared)
            + '\', caption: \'A photo from the #extrasolar planet Epsilon Prime taken by my rover.\'});"><img src="'+ce4.util.url_static('/img/facebook_share.png')+'"/></a></span>'
        + '<span class="twitter"><a href="https://twitter.com/share" class="twitter-share-button" data-count="none" '
            + 'data-lang="en" data-size="small" data-via="ExoResearch" data-related="ExoResearch:The eXoplanetary '
            + 'Research Institute (XRI)" data-text="A photo from the #extrasolar planet Epsilon Prime taken by my rover." '
            + 'data-url="' + target.link_url_shared(show_infrared) + '"></a></span>'
        + '<span class="google"><div class="g-plus" data-action="share" data-annotation="none" data-href="'
            + target.link_url_shared(show_infrared) + '"></div></span>');

    ce4.ui.social.facebook.load();
    ce4.ui.social.twitter.load();
    ce4.ui.social.google.load();
};


//------------------------------------------------------------------------------
// Updates unprocessed photo thumnails with a countdown timer
// Called once per second
ce4.ui.updateThumbs = function() {

    // Iterate unprocessed images
    $('#gallery-thumbnails .unprocessed #arrival-time').each(function(index, self) {

        // Time left until done, note: This span's data-arrival-time is UTC Unix
        var doneTime = $(self).data('arrival-time') - ce4.gamestate.user.epoch_now();

        // Update countdown timer, or show waiting
        $(self).html(doneTime <= 0 ? "Waiting for probe data." : "Arriving in " + ce4.ui.formatDelay(doneTime));
    });
};


//------------------------------------------------------------------------------
// Pass a list of targets to generate the Thumbnail List
ce4.ui.displayThumbStrip = function (thumb_div, target_list, current_target_id){
    xri.ui.displayThumbStrip(thumb_div, target_list, current_target_id, function(target) {
        return {
            target_id:      target.target_id,
            thumb_url:      ce4.util.url_static(target.images.THUMB),
            thumb_link_url: ce4.util.url_static(target.picture_url())
        };
    });
};


//------------------------------------------------------------------------------
// Format the time remaining until a target will be ready.
ce4.ui.formatDelay = function(delay) {
    delay = Math.ceil(delay);  // Delay is remaining seconds
    seconds = delay%60;
    delay = (delay-seconds)/60;  // Delay becomes remaining minutes
    minutes = delay%60;
    delay = (delay-minutes)/60;  // Delay becomes remaining hours

    // Pad minutes and seconds with zeroes where appropriate
    strTime = delay + ":";
    if (minutes < 10) strTime += "0";
    strTime += minutes + ":";
    if (seconds < 10) strTime += "0";
    strTime += seconds;

    return strTime;
};


//------------------------------------------------------------------------------
ce4.ui.update_navbar = function() {
    if (ce4.gamestate.classroom != undefined) {
        $("#classroom_tab").show();
    }
    $("#user-controls .username").html(ce4.gamestate.user.first_name + " &lt;" + ce4.gamestate.user.email + "&gt;");
};


//------------------------------------------------------------------------------
// Display the number of unviewed mail messages
ce4.ui.update_unviewed_message_count = function() {
    var count = ce4.gamestate.user.unread_message_count();
    $("#id_unviewed_message_count").html((count == 0) ? "" : (ce4.ui.is_mobile ? count : " ("+count+")"));
};


//------------------------------------------------------------------------------
// Display the number of unviewed gallery photos
ce4.ui.update_unviewed_photo_count = function() {
    var count = ce4.gamestate.user.unviewed_photo_count();
    $("#id_unviewed_photo_count").html((count == 0) ? "" : (ce4.ui.is_mobile ? count : " ("+count+")"));
};


//------------------------------------------------------------------------------
// Display the number of unviewed mission tasks
ce4.ui.update_unviewed_task_count = function() {
    var count = ce4.gamestate.user.unviewed_task_count();
    $("#id_unviewed_task_count").html((count == 0) ? "" : (ce4.ui.is_mobile ? count : " ("+count+")"));
};


//------------------------------------------------------------------------------
// Display the number of unviewed catalog discoveries
ce4.ui.update_unviewed_catalog_count = function() {
    var count = ce4.gamestate.user.unviewed_species_count();
    $("#id_unviewed_catalog_count").html((count == 0) ? "" : (ce4.ui.is_mobile ? count : " ("+count+")"));
};


//------------------------------------------------------------------------------
// Spans with the ce4_crosslink class should be linked to other content based on
// their data values.  Supported crosslink classes:
//   <span class='ce4_crosslink_message' data-msg-type='message_id'>
//   <span class='ce4_crosslink_region' data-region-type='primary_key:secondary_key:etc.'>
//   <span class='ce4_crosslink_mission' data-mission-definition='mission_definition'>
//   <span class='ce4_crosslink_catalog' data-species-key='species_key'>
//   <span class='ce4_crosslink_store'>
//   <span class='ce4_crosslink_profile'>
//   <span class='ce4_crosslink_map'>
// Add an anchor within the span, or no anchor if the target cannot be found.
ce4.ui.update_crosslinks = function() {

    $('.ce4_crosslink_region').each(function(index) {
        var text_only = $(this).text();
        var arg_array = $(this).data('region-type').split(':');

        var region_index = 0;
        // Find the first region in the list that is in the gamestate.
        while (region_index < arg_array.length && !ce4.gamestate.user.regions.contains(arg_array[region_index])) {
            region_index++;
        }
        if (region_index < arg_array.length) {
            // A matching region was found.  Create a link to it.
            $(this).html('<a href="' + ce4.util.url_map({region:arg_array[region_index]}) + '">' + text_only + '</a>');
        }
        else {
            // No matching region was found.  Get rid of any prior anchor.
            $(this).html(text_only);
        }
    });

    $('.ce4_crosslink_message').each(function(index) {
        var text_only = $(this).text();
        var msg_type = $(this).data('msg-type');
        var message = ce4.gamestate.user.messages.by_type(msg_type);
        if (message)
            $(this).html('<a href="' + ce4.util.url_message(message.message_id) + '">' + text_only + '</a>');
        else  // No matching message was found.  Get rid of any prior anchor.
            $(this).html(text_only);
    });

    $('.ce4_crosslink_mission').each(function(index) {
        var text_only = $(this).text();
        var mission_definition = $(this).data('mission-definition');
        var mission = ce4.gamestate.user.missions.for_definition(mission_definition);
        if (mission)
            $(this).html('<a href="' + ce4.util.url_task(mission.mission_id) + '">' + text_only + '</a>');
        else  // No matching mission was found.  Get rid of any prior anchor.
            $(this).html(text_only);
    });

    $('.ce4_crosslink_catalog').each(function(index) {
        var text_only = $(this).text();
        var species_key = $(this).data('species-key');
        var species = ce4.gamestate.user.species.for_key(species_key);
        if (species)
            $(this).html('<a href="' + ce4.util.url_catalog({id: species.species_id}) + '">' + text_only + '</a>');
        else  // No matching species was found.  Get rid of any prior anchor.
            $(this).html(text_only);
    });

    $('.ce4_crosslink_store').each(function(index) {
        var text_only = $(this).text();
        $(this).html('<a href="#profile" onclick="ce4.ui.store.dialogOpen(); return false;">' + text_only + '</a>');
    });

    $('.ce4_crosslink_profile').each(function(index) {
        var text_only = $(this).text();
        $(this).html('<a href="#profile">' + text_only + '</a>');
    });

    $('.ce4_crosslink_map').each(function(index) {
        var text_only = $(this).text();
        $(this).html('<a href="#map">' + text_only + '</a>');
    });
};


//------------------------------------------------------------------------------
ce4.ui.populate_missions = function (){

    // Missions lists
    var notdone_missions = ce4.gamestate.user.notdone_missions("root");
    var done_missions = ce4.gamestate.user.done_missions("root");

    // Sort done missions by descending done_at time, not done missions by started_at time (secondary), and sort value (primary)
    notdone_missions.sort(function(a,b) {return b.started_at - a.started_at;});
    notdone_missions.sort(function(a,b) {return b.sort - a.sort;});
    done_missions.sort(function(a,b) {return b.done_at - a.done_at;});

    var mission_id = undefined;
    active_mission_id_offset = 0;

    if (ce4.ui.current_mission_id) {
        mission_id = ce4.ui.current_mission_id;
    }
    else if (ce4.ui.current_page_name === "tasks" && !ce4.ui.is_mobile) {
        // When no specific mission is requested, select the first (unless on mobile, select none)
        if (notdone_missions.length > 0)
            mission_id = notdone_missions[0].mission_id;
        else if (done_missions.length > 0)
            mission_id = done_missions[0].mission_id;
    }
    else if (ce4.ui.current_page_name === "task") {
        mission_id = ce4.ui.current_page.slice("task,".length);
    }

    var create_task_item = function(mission, i) {
        if (mission_id === mission.mission_id) active_mission_id_offset = i;

        return $('<li class="mission"><span class="mission-title dwindle"><span class="meta"><img src="'+mission.title_icon_url()+'"/></span>&nbsp;' + mission.title + '</span></li>')
                            .click(ce4.ui.init_mission_detail_handler(mission.mission_id))
                            .addClass('clickable')
                            .toggleClass('unviewed', !mission.hasBeenViewed())
                            .toggleClass('active', mission_id === mission.mission_id);
    };

    $.each(notdone_missions, function(i, mission) { $("#ongoing-missions ul").append(create_task_item(mission, i)); });
    $.each(done_missions, function(i, mission){$("#completed-missions ul").append(create_task_item(mission, i)); });

    if (notdone_missions.length == 0) $("#ongoing-missions").hide();
    if (done_missions.length == 0)    $("#completed-missions").hide();

    // Show the details for the selected mission in the right column.
    if (mission_id) {
        $('#ongoing-missions li.active, #completed-missions li.active').removeClass('active').click();
    }

    if(!ce4.ui.is_mobile) {
        // Do pajination
        var notdone_items = notdone_missions.length;
        var done_items = done_missions.length;

        // Add paging tabs if we have over 14 total missions
        if ((notdone_items + done_items) > ce4.ui.MAX_MISSION_TWO_TYPES )
        {
            // Add paging tab if we have over half the MAX_MISSION_TWO_TYPES not done, or we have none done and more than MAX_MISSION_ONE_TYPE
            if(notdone_items > (ce4.ui.MAX_MISSION_TWO_TYPES / 2) && (notdone_items > ce4.ui.MAX_MISSION_ONE_TYPE || done_items))
            {
                var ongoing_per_page = (done_items >= (ce4.ui.MAX_MISSION_TWO_TYPES / 2)) ? (ce4.ui.MAX_MISSION_TWO_TYPES / 2) : ((done_items > 0) ? ce4.ui.MAX_MISSION_TWO_TYPES  - done_items : ce4.ui.MAX_MISSION_ONE_TYPE);
                $('#ongoing-missions').pajinate({
                    item_container_id : '#active-missions-list',
                    nav_panel_id : '.page_navigation',
                    nav_label_info : 'Page {3} of {4}',
                    num_page_links_to_display : 0,
                    items_per_page : ongoing_per_page,
                    show_first_last: false,
                    nav_label_prev : 'Newer',
                    nav_label_next : 'Older',
                    nav_label_ellipse:'',
                    start_page : Math.floor(active_mission_id_offset / ongoing_per_page)
                });
            }
            // Add paging tab if we have over half the MAX_MISSION_TWO_TYPES not done, or we have none done and more than MAX_MISSION_ONE_TYPE
            if(done_items > (ce4.ui.MAX_MISSION_TWO_TYPES / 2) && (done_items > ce4.ui.MAX_MISSION_ONE_TYPE || notdone_items))
            {
                var completed_per_page = (notdone_items >= (ce4.ui.MAX_MISSION_TWO_TYPES / 2)) ? (ce4.ui.MAX_MISSION_TWO_TYPES / 2) : ((notdone_items > 0) ? ce4.ui.MAX_MISSION_TWO_TYPES  - notdone_items : ce4.ui.MAX_MISSION_ONE_TYPE);
                $('#completed-missions').pajinate({
                    item_container_id : '#completed-missions-list',
                    nav_panel_id : '.page_navigation',
                    nav_label_info : 'Page {3} of {4}',
                    num_page_links_to_display : 0,
                    items_per_page : completed_per_page,
                    show_first_last: false,
                    nav_label_prev : 'Newer',
                    nav_label_next : 'Older',
                    nav_label_ellipse:'',
                    start_page : Math.floor(active_mission_id_offset / completed_per_page)
                });
            }
        }
    }
};


//------------------------------------------------------------------------------
// This function is tied to the click event handler for items in the task list.  Note that
// this function doesn't actually display the task details.  Rather, it is used to create a
// function context (with the appropriate mission_id) for each item in the list.
ce4.ui.init_mission_detail_handler = function(mission_id)
{
    return function() {
        var mobile_closing = ce4.ui.is_mobile && $(this).hasClass('active');

        // Create the details box on mobile
        if(ce4.ui.is_mobile)
        {
            // Clean up the previous one
            $('#mission-list li.active .mission-title').show();
            $("#mission-details").remove();

            // If we aren't clicking to close, open
            if(!mobile_closing)
            {
                // Add the new detail box
                $(this).append('\
                    <div id="mission-details">\
                        <div class="mission-detail">\
                            <div class="mission-body"></div>\
                            <ul class="submissions"></ul>\
                        </div>\
                    </div>\
                ');
                $(this).find(".mission-title").hide();

                // Scroll element to top of the screen
                $('#content').animate({scrollTop: $(this).position().top + $(this).parents('#active-missions-list, #completed-missions-list').position().top}, ce4.ui.reloading ? 0 : 1000);
            }
        }

        // Remove the row highlight from the previously selected task and highlight the new row
        $('#ongoing-missions li').removeClass("active");
        $('#completed-missions li').removeClass("active");
        if(!mobile_closing) $(this).addClass("active");

        // Populate the right column with the details for the selected task
        ce4.ui.populate_mission_details(mission_id);
        ce4.ui.update_crosslinks();

        // Cache mission_id in case page reloads
        ce4.ui.current_mission_id = mission_id;
    };
};


//------------------------------------------------------------------------------
// Display the details of a specific task in the mission-detail div.
ce4.ui.populate_mission_details = function (mission_id) {
    var mission = ce4.gamestate.user.missions.get(mission_id);

    // Mark mission and child parts viewed
    mission.markViewed()

    $("#mission-details ").empty().append('<div class="mission-detail"></div><ul class="submissions"></ul>');
    $(".mission-detail").prepend('<h1><img src="'+mission.title_icon_url(true)+'"/>&nbsp;' + mission.title + '</h1><p>' + mission.summary + '</p>');

    if(mission.description) {
        $(".submissions").append('<li class="mission"><img src="'+mission.description_icon_url(true)+'"/> <div class="mission-body">'
            + mission.description + ' ' + mission.get_status() + '</div></div></li>');
    }

    if(mission.parts){
        $.each(mission.parts, function(i,part){
            // FUTU: switch to css icons? <img src="/img/1x1.gif" class="mission-icon ' + part.icon() + '" />
            $(".submissions").append('<li class="mission"><div class="title"><b>Step ' + (i+1) + ':</b> ' + part.title
                               + (part.summary ? '<div class="summary">' + part.summary + '</div>' : '')
                               + '</div><img src="'+part.description_icon_url(true)+'"/> <div class="mission-body">'
                               + part.description + ' ' + part.get_status() + '</div></li>');
        });
    }
};


//------------------------------------------------------------------------------
// This function is tied to the click event handler for items in the species catalog.  Note that
// this function doesn't actually display the species details.  Rather, it is used to create a
// function context (with the appropriate species_id) for each item in the catalog.
ce4.ui.init_species_detail_handler = function(species_id)
{
    return function()
    {
        var mobile_closing = ce4.ui.is_mobile && $(this).hasClass('active');

        // Create the details box on mobile
        if(ce4.ui.is_mobile)
        {
            // Clean up the previous one
            $('#species-catalog li.active img').show();
            $('#species-catalog li.active .title').show();
            $("#species-view").remove();
            if(!mobile_closing)
            {
                $(this).append('\
                    <div id="species-view">\
                        <div id="species-detail"></div>\
                        <div id="species-photos">\
                            <div id="species-photos-info"></div>\
                            <div id="species-photos-thumbnails"></div>\
                        </div>\
                    </div>\
                ');
                $(this).find("img").hide()
                $(this).find(".title").hide();

                // Scroll element to top of the screen
                $('#content').animate({scrollTop: $(this).position().top}, 1000);
            }
        }

        // Remove the row highlight from the previously selected task and highlight the new row.
        $('#species-catalog li').removeClass("active");
        if(!mobile_closing) $(this).addClass("active");

        // Populate the details box with selected species
        ce4.ui.show_species_details(species_id);

        // Cache species id in case page reloads
        ce4.ui.current_species_id = species_id;
    };
};


//------------------------------------------------------------------------------
// Display the details for a specific species in the species-detail div.
ce4.ui.show_species_details = function(species_id)
{
    var species = ce4.gamestate.user.species.get(species_id);
    // Mark this species viewed if not previously viewed.
    species.markViewed();

    var species_photos = species.get_targets();

    if(species){
        $("#species-detail").html('<div class="species-detail-item"><img src="' + ce4.util.url_static(species.get_icon_url(300,300)) + '" />\
                <h3>' + species.name + '</h3><h4>' + (species.science_name || '&nbsp;')+ '</h4></div>\
                <p>' + species.description +'</p>\
                <p><b>Discovered: </b>'+ ce4.util.format_time_since(species.detected_at_date().getTime()) + '</p>');

        $("#species-photos-info").html('<b>Tagged in '+species_photos.length+' photo'+(species_photos.length === 1 ? '':'s')+'</b>');

        // Display thumbnail list
        ce4.ui.displayThumbStrip($("#species-photos-thumbnails"), species_photos);
    }
};

//------------------------------------------------------------------------------
ce4.ui.logout = function()
{
    if (ce4.util.is_native()) {
        localStorage.removeItem('auto_login');
        window.location = "index.html";
    }
    else {
        $.ajax({
            type: 'POST',
            url: '/logout',
            success: function () {
                // If logged in with Facebook, logout there too. Then reload the page.
                if(ce4.gamestate.user.auth === 'FB' && typeof FB !== 'undefined') {
                    FB.getLoginStatus(function(response) {
                        if (response.status === 'connected') {
                            // Player is logged into via Facebook.
                            FB.logout(function(response){
                                location.reload();
                            });
                        }
                        else {
                            // Player is logged in to Facebook, but not the app.
                            location.reload();
                        }
                    });
                }
                else {
                    // Not logged in to Facebook.
                    location.reload();
                }
            }
        });
    }
}

//------------------------------------------------------------------------------
// Fetch the icon filename ("/static/img/user_icons/turing-") associated with the given sender_key ("TURING").
// Note that image dimensions ("27x27.png") should be appended to the result by the caller.
ce4.ui.get_sender_icon = function(sender_key) {
    var icon = ce4.assets.sender[sender_key];
    if (icon === undefined)
        icon = ce4.assets.sender["DEFAULT"];
    return icon;
};


//------------------------------------------------------------------------------
// Fetch the url ("/static/img/css/waiting_64x20.gif") associated with the given asset_key ("LOADING").
ce4.ui.get_ui_asset_url = function(asset_key) {
    var asset_url = ce4.assets.ui[asset_key];
    if (asset_url === undefined)
        console.log("Warning: Undefined UI asset " + asset_key);
    return asset_url;
};


//------------------------------------------------------------------------------
ce4.ui.light_phases = {
    intervalName : [
        "Midnight",
        "Predawn",
        "Sunrise",
        "Morning",
        "Midday",
        "Afternoon",
        "Sunset",
        "Dusk"
    ],
    intervalImage : [
        ce4.util.url_static("/img/planet_phases/planet-night.png"), // night
        ce4.util.url_static("/img/planet_phases/planet-predawn.png"), // predawn
        ce4.util.url_static("/img/planet_phases/planet-sunrise.png"), // sunrise
        ce4.util.url_static("/img/planet_phases/planet-morning.png"), // morning
        ce4.util.url_static("/img/planet_phases/planet-midday.png"), // midday
        ce4.util.url_static("/img/planet_phases/planet-afternoon.png"), // afternoon
        ce4.util.url_static("/img/planet_phases/planet-sunset.png"), // sunset
        ce4.util.url_static("/img/planet_phases/planet-evening.png") // evening
    ],
    majorMoon : [
        ce4.util.url_static("/img/moon_phases/major/moon1.png"), // new
        ce4.util.url_static("/img/moon_phases/major/moon2.png"), // waxing crescent
        ce4.util.url_static("/img/moon_phases/major/moon3.png"), // first quarter
        ce4.util.url_static("/img/moon_phases/major/moon4.png"), // waxing gibbous
        ce4.util.url_static("/img/moon_phases/major/moon5.png"), // full
        ce4.util.url_static("/img/moon_phases/major/moon6.png"), // waning gibbous
        ce4.util.url_static("/img/moon_phases/major/moon7.png"), // last quarter
        ce4.util.url_static("/img/moon_phases/major/moon8.png") // waning crescent
    ],
    minorMoon : [
        ce4.util.url_static("/img/moon_phases/minor/moon1.png"), // new
        ce4.util.url_static("/img/moon_phases/minor/moon2.png"), // waxing crescent
        ce4.util.url_static("/img/moon_phases/minor/moon3.png"), // first quarter
        ce4.util.url_static("/img/moon_phases/minor/moon4.png"), // waxing gibbous
        ce4.util.url_static("/img/moon_phases/minor/moon5.png"), // full
        ce4.util.url_static("/img/moon_phases/minor/moon6.png"), // waning gibbous
        ce4.util.url_static("/img/moon_phases/minor/moon7.png"), // last quarter
        ce4.util.url_static("/img/moon_phases/minor/moon8.png") // waning crescent
    ]
};


//------------------------------------------------------------------------------
ce4.ui.moon_phases = [ "New Moon",
                            "Waxing Crescent",
                            "First Quarter",
                            "Waxing Gibbous",
                            "Full Moon",
                            "Waning Gibbous",
                            "Last Quarter",
                            "Waning Crescent"
                          ]


//------------------------------------------------------------------------------
// crops png extension after the string and returns
ce4.ui.crop_png = function(somestring) {
    var rawName = somestring;
    var cropped = /.png$/;
    somestring.replace(cropped, "");
    return rawName;
};


//------------------------------------------------------------------------------
ce4.ui.homepage_surface_conditions = function(){

    var time_in_eris       = ce4.planet.now_in_eris();
    var time_until_sunrise = ce4.planet.next_solar_event(0.25);
    var time_until_sunset  = ce4.planet.next_solar_event(0.75);
    var major_lunar_phase  = ce4.planet.current_lunar_phase(0);
    var minor_lunar_phase  = ce4.planet.current_lunar_phase(1);
    var major_lunar_rise   = ce4.planet.next_lunar_event(0, 0.25);
    var major_lunar_set    = ce4.planet.next_lunar_event(0, 0.75);
    var minor_lunar_rise   = ce4.planet.next_lunar_event(1, 0.25);
    var minor_lunar_set    = ce4.planet.next_lunar_event(1, 0.75);

    var time_of_day = time_in_eris - Math.floor(time_in_eris);
    var sun_interval = Math.floor((time_of_day * 8.0) + 0.5);
    var major_moon_int = Math.floor((major_lunar_phase * 8) + 0.5);
    var minor_moon_int = Math.floor((minor_lunar_phase * 8) + 0.5);

    if (sun_interval > 7)   sun_interval = 0;
    if (major_moon_int > 7) major_moon_int = 0;
    if (minor_moon_int > 7) minor_moon_int = 0;

    // Planet surface image update
    var intervalName = ce4.ui.light_phases.intervalName[sun_interval];
    var intervalImage = ce4.ui.light_phases.intervalImage[sun_interval];
    $(".planet-phases img").attr('src', intervalImage);
    $(".planet-time").html(intervalName);

    if (time_until_sunrise < time_until_sunset) {
        $(".planet-sun-phase").html("Sunrise in " + ce4.util.format_time_hm(time_until_sunrise));
    } else {
        $(".planet-sun-phase").html("Sunset in " + ce4.util.format_time_hm(time_until_sunset));
    }

    // major moon update
    var majMoonName = ce4.ui.moon_phases[major_moon_int];
    var majorMoon = ce4.ui.light_phases.majorMoon[major_moon_int];
    $(".xri-main-Rcol .moon1 img").attr('src', majorMoon);
    $(".moon1 .moon_name").html(majMoonName);

    if(major_lunar_rise < major_lunar_set){
        $(".moon1 .moon_set").html("Rises in " + ce4.util.format_time_hm(major_lunar_rise)) ;
    } else {
        $(".moon1 .moon_set").html("Sets in " + ce4.util.format_time_hm(major_lunar_set)) ;
    }

    // minor moon update
    var minMoonName = ce4.ui.moon_phases[minor_moon_int];
    var minorMoon = ce4.ui.light_phases.minorMoon[minor_moon_int];
    $(".xri-main-Rcol .moon2 img").attr('src', minorMoon);
    $(".moon2 .moon_name").html(minMoonName);

    if(minor_lunar_rise < minor_lunar_set){
        $(".moon2 .moon_set").html("Rises in " + ce4.util.format_time_hm(minor_lunar_rise)) ;
    } else {
        $(".moon2 .moon_set").html("Sets in " + ce4.util.format_time_hm(minor_lunar_set)) ;
    }

};


//------------------------------------------------------------------------------
// Given a the time in eris, return a friendly name for the current time interval,
// such as "Morning" or "Afternoon".
ce4.ui.eri_interval_name = function(eris) {
    var time_of_day = eris - Math.floor(eris);
    var sun_interval = Math.floor((time_of_day * 8.0) + 0.5);
    if (sun_interval > 7)   sun_interval = 0;
    return ce4.ui.light_phases.intervalName[sun_interval];
};


//------------------------------------------------------------------------------
// Parses a string and returns an object of key: value pairs
ce4.ui.parse_args = function(args_string)
{
    if(args_string)
    {
        // Search the string for each instance key value pairs formatted as: "key1=value1&key2=value2" or as "value";
        var eval_string = args_string.replace(/([^?=&]+)(=([^&]*))?&?/g,  function($0, $1, $2, $3)
                                                                          {
                                                                              // If there is an "=" return the key:value pair
                                                                              if($2)  return escape($1)+":\""+escape($3)+"\",";

                                                                              // Otherwise return the value as the id
                                                                              else    return "id:\""+escape($0)+"\"";
                                                                          });

        // remove trailing ,
        eval_string = eval_string.replace(/,$/,"");

        // Turn it into an object and return it
        return eval("({"+ eval_string +"})");
    }

    return {};
};


//------------------------------------------------------------------------------
// Set up handler for changing notification delay
ce4.ui.notification_settings_onchange = function()
{
    // When the notification settings option changes send that to the server.
    $("#notification_settings").change(function() {
        var frequency = $("#notification_settings").val();
        ce4.util.json_post({
            url: ce4.gamestate.user.urls.settings_notifications,
            data: {activity_alert_frequency: frequency},
            success: function() {
                $('#notification_settings_result').text("Saved");
                $("#notification_settings_result").delay(1000).fadeOut('slow', function() {
                    $('#notification_settings_result').text("");
                    $('#notification_settings_result').show();
                });
            },
            error: function() {
                $('#notification_settings_result').text("Error");
                console.error("Error in changing user notification settings to " + frequency);
            }
        });
    });

    // Select the correct notification setting based on the gamestate.
    $("#notification_settings").val(ce4.gamestate.user.activity_alert_frequency);
};


//------------------------------------------------------------------------------
// Map coordinates corresponding to the top left, bottom right pixels of minimap image
ce4.ui.MINIMAP_BOUNDS = [[6.248976572213111, -109.42306637763976], [6.23964453673332,  -109.41332459449768]];


//------------------------------------------------------------------------------
// Calculates the crosshair image offset for the minimap
ce4.ui.minimap_crosshair_position = function(coords)
{
    // center pixel of the crosshair image
    var crosshair_center = [161, 161];

    // Coordinates of the default rover
    if(!coords) {
        var active_rover = ce4.gamestate.user.rovers.find(function(rover) { return rover.active === 1; });
        if (active_rover) {
            var coords = active_rover.getCoords();
        } else {
            // If there's no active rover, center the crosshairs on the map.
            var coords = [(ce4.ui.MINIMAP_BOUNDS[0][0] + ce4.ui.MINIMAP_BOUNDS[1][0])/2, (ce4.ui.MINIMAP_BOUNDS[0][1] + ce4.ui.MINIMAP_BOUNDS[1][1])/2];
        }
    }

    // Calculate the crosshair pixel offset
    var pos_x = Math.round($(".minimap .crosshairs img").prop("width")  * Math.abs(ce4.ui.MINIMAP_BOUNDS[0][1] - coords[1]) / Math.abs(ce4.ui.MINIMAP_BOUNDS[0][1] - ce4.ui.MINIMAP_BOUNDS[1][1]) - crosshair_center[1]);
    var pos_y = Math.round($(".minimap .crosshairs img").prop("height") * Math.abs(ce4.ui.MINIMAP_BOUNDS[0][0] - coords[0]) / Math.abs(ce4.ui.MINIMAP_BOUNDS[0][0] - ce4.ui.MINIMAP_BOUNDS[1][0]) - crosshair_center[0]);

    return pos_x + "px " + pos_y + "px";
};

//------------------------------------------------------------------------------
// Calculates the lat, lng coordinates for the map position based on the pixel coordinates of the image
ce4.ui.minimap_position_coords = function(x, y)
{
    // Calculate the lat, lng coordinates
    var lat = ((y + 0.5) / $(".minimap .crosshairs img").prop("height")) * (ce4.ui.MINIMAP_BOUNDS[1][0] - ce4.ui.MINIMAP_BOUNDS[0][0]) + ce4.ui.MINIMAP_BOUNDS[0][0];
    var lng = ((x + 0.5) / $(".minimap .crosshairs img").prop("width"))  * (ce4.ui.MINIMAP_BOUNDS[1][1] - ce4.ui.MINIMAP_BOUNDS[0][1]) + ce4.ui.MINIMAP_BOUNDS[0][1];

    return {'lat': lat, 'lng': lng};
};


//------------------------------------------------------------------------------
// Populate the categories with types of discoveries
ce4.ui.populate_catalog_categories = function(categories, current)
{
    var category_rename = function(c) { return {"PLANT": "PHOTOBIONT", "ANIMAL": "MOTOBIONT"}[c] || c;};

    if(categories.length > 2)
    {
        $("#catalog-categories").change(function(){ce4.ui.current_catalog_category = $(this).val(); ce4.ui.reload_current_page();});

        categories.sort(function(a, b){ return category_rename(a).localeCompare(category_rename(b)); }).forEach(function(category) {
            $('#catalog-categories')
               .append($("<option></option>")
               .attr("value", category)
               .text("Classification: " + category_rename(category).toLowerCase())
               .attr('selected',(current == category) ? true : false));
        });
    }
    else
    {
        $('#catalog-categories').hide();
    }
};


ce4.ui.ALERT_MISSION        = "MISSION";
ce4.ui.ALERT_MISSION_DONE   = "MISSION_DONE";
ce4.ui.ALERT_MESSAGE        = "MESSAGE";
ce4.ui.ALERT_PICTURE        = "PICTURE";
ce4.ui.ALERT_DISCOVERY      = "DISCOVERY";
ce4.ui.ALERT_ACHIEVEMENT    = "ACHIEVEMENT";
//------------------------------------------------------------------------------
// Toast unviewed alerts when the user logs in
ce4.ui.update_unviewed_alerts = function()
{
    ce4.util.forEach(ce4.gamestate.user.unviewed_alerts().slice(-5), ce4.ui.new_alert);
};


//------------------------------------------------------------------------------
// Called when a new alert comes in from a chip
ce4.ui.new_alert = function(alert_data)
{
    // Update new alert count
    ce4.ui.add_unviewed_alerts((alert_data.type == ce4.ui.ALERT_ACHIEVEMENT) ? "profile" : "home", 1);

    // Play toasts
    if(!ce4.ui.is_mobile)
    {
        ce4.ui.alert_toast(alert_data.type, alert_data.object);

        // Mark all alerts as having been viewed
        ce4.gamestate.user.update_viewed_alerts_at();
    }
};


//------------------------------------------------------------------------------
// Increase the tab count by val, ex tab counts: #profile_unviewed_alerts, #home_unviewed_alerts
ce4.ui.add_unviewed_alerts = function(tab, val)
{
    $("#"+tab+"_unviewed_alerts").html(parseInt($("#"+tab+"_unviewed_alerts").html()) + val).show();
    ce4.ui.update_title_unviewed_alerts();
};


//------------------------------------------------------------------------------
// Clear the tab count, ex tab counts: #profile_unviewed_alerts, #home_unviewed_alerts
ce4.ui.clear_unviewed_alerts = function(tab)
{
    if(tab == "home" && $("#home_unviewed_alerts").html() > 0)
    {
        // Mark all alerts as having been viewed
        ce4.gamestate.user.update_viewed_alerts_at();
    }

    $("#"+tab+"_unviewed_alerts").html(0).hide();
    ce4.ui.update_title_unviewed_alerts();
};


//------------------------------------------------------------------------------
// Update the document title with unviewed alerts count "(x) Extrasolar..."
ce4.ui.update_title_unviewed_alerts = function ()
{
    var unviewed_alerts_count = ce4.ui.count_unviewed_alerts();
    document.title = (unviewed_alerts_count > 0 ? "("+unviewed_alerts_count+") " : "") + document.title.replace(/^\(\d*\) /, "");
};


//------------------------------------------------------------------------------
// Count the unviewed alerts in tabs: #profile_unviewed_alerts, #home_unviewed_alerts
ce4.ui.count_unviewed_alerts = function()
{
    return parseInt($("#profile_unviewed_alerts").html()) + parseInt($("#home_unviewed_alerts").html());
};


//------------------------------------------------------------------------------
// Called when a new alert comes in from a chip
ce4.ui.alert_toast = function(type, object)
{
    ce4.ui.alert_display(type, object, ce4.ui.toast);
};


//------------------------------------------------------------------------------
// Displays an alert using a passed in function (toast, notification)
ce4.ui.alert_display = function(type, object, display_function)
{
    switch (type)
    {
        case ce4.ui.ALERT_MISSION:        display_function({url: ce4.util.url_task(object.mission_id), icon: object.title_icon_url(), title: "New Task", details: object.title, viewed: object.hasBeenViewed()});
            break;
        case ce4.ui.ALERT_MISSION_DONE:   display_function({url: ce4.util.url_task(object.mission_id), icon: object.title_icon_url(), title: "Done: " + object.title, details: object.get_done_notice(), viewed: object.hasBeenViewed()});
            break;
        case ce4.ui.ALERT_MESSAGE:        display_function({url: ce4.util.url_message(object.message_id), icon: ce4.ui.get_sender_icon(object.sender_key)+"72x72.png", title: "New Message", details: object.sender+"<br>"+object.subject, viewed: object.hasBeenViewed()});
            break;
        case ce4.ui.ALERT_PICTURE:        display_function({url: object.picture_url(), icon: ce4.util.url_static(object.images.THUMB || object.images.PHOTO), title: "New Photo", details: object.get_description(), viewed: object.hasBeenViewed()});
            break;
        case ce4.ui.ALERT_DISCOVERY:      display_function({url: ce4.util.url_catalog({id: object.species_id}), icon: object.get_icon_url(150, 150), title: "New Discovery", details: object.name, viewed: object.hasBeenViewed()});
            break;
        case ce4.ui.ALERT_ACHIEVEMENT:    display_function({url: "#profile", icon: object.url_icon(), title: "New Achievement", details: object.title, viewed: object.hasBeenViewed()});
            break;
    }
};


//------------------------------------------------------------------------------
// Displays a toast
// p = {url: , icon: , title: , details: }
ce4.ui.toast = function(p, replay)
{
    if(!replay)
    {
        ce4.ui.toastHistory = ce4.ui.toastHistory || [];
        ce4.ui.toastHistory.push(p);
    }

    $("#toasts-history").hide();

    var toast = $("<div><div class='toast-icon-border'><img src='"+p.icon+"'></div><span><p class='toast-title dwindle'><b>"+p.title+"</b></p><p class='toast-details'>"+p.details+"</p></span></div>").click(function(){window.location = p.url;});
    $("#toasts").prepend(toast);
    toast.show("slide", { direction: "left" }, 1000);

    window.setTimeout(function () {
        if($("#toasts:hover").length > 0)
        {
            window.setTimeout(arguments.callee, 1000);
        }
        else
        {
            toast.hide("slide", { direction: "left" }, 1000, function() {
                toast.remove();

                // If toasts are finished playing
                if($("#toasts > div").size() == 0) $("#toasts-history").show();
            });
        }
    }, 7000);
};


//------------------------------------------------------------------------------
// Replays toasts
ce4.ui.toast_replay = function(count)
{
    if(ce4.ui.toastHistory) $.each(ce4.ui.toastHistory.slice(-count), function(i, toast) { ce4.ui.toast(toast, true); });
};

//------------------------------------------------------------------------------
// Function to exit fullscreen on Esc keypress
ce4.ui.fullscreen_exit_on_esc = function(ev)
{
    if (ev.keyCode === 27 ) // Esc key
    {
        if(ce4.ui.is_current_page_name(ce4.ui.LEAFLET))
        {
            ce4.ui.leaflet.exitFullscreen();
        }
        else if(ce4.ui.is_current_page_name(ce4.ui.PICTURE))
        {
            ce4.ui.fullscreen(false)
        }
        $(document).unbind('keydown', ce4.ui.fullscreen_exit_on_esc);
    }
};


//------------------------------------------------------------------------------
// Enter or exit fullscreen
ce4.ui.fullscreen = function(fullscreen,p)
{
    // Enter fullscreen
    if(fullscreen === true && ce4.ui.is_fullscreen !== true)
    {
        $("#xri-wrapper").hide()
        $("#fullscreen").show();
        $("#fullscreen").append($('<div/>').addClass('loading-underlay'));
        $("#fullscreen-tabs").show();
        $('#fullscreen-tabs').append($("#xri-tabs").children());

        if(ce4.ui.is_current_page_name(ce4.ui.LEAFLET))
        {
            $("#fullscreen").append($("#leaflet-container").detach());
            $('#map-container').children().remove();
            ce4.ui.leaflet.onShow();
        }
        else if(ce4.ui.is_current_page_name(ce4.ui.PICTURE))
        {
            var content = '<div id="image-container-fullscreen">';

            if(p.is_panorama) {
                var image_height = Math.min($(window).height(),1280);
                var image_width = image_height * 4;
                var frame_height = image_height;
                var frame_width =  Math.min($(window).width(), image_width);
                var frame_position = (ce4.ui.current_panorama_position * image_width + image_width - frame_width / 2) % image_width;

                // TODO: Pass in lower resolution image and use it instead for frame_width / frame_height below a threshold
                content += '<ul id="image-drag-fullscreen"><li>\
                                <img src="'+p.image+'" height="'+image_height+'" width="'+image_width+'"/>\
                            </li></ul>\
                            <div class="pan-left-control" id="image-drag-pan-left"><div title="Pan image left" class="overlay-button-border"><div class="pan-left-button-interior"></div></div></div>\
                            <div class="pan-right-control" id="image-drag-pan-right"><div title="Pan image right" class="overlay-button-border"><div class="pan-right-button-interior"></div></div></div>';
            }
            else {
                content += '<img src="'+p.image+'" style="max-width: 100%; max-height: 100%;">';
            }

            content += '<div class="fullscreen-control" onclick="ce4.ui.fullscreen(false);">\
                            <div title="Full screen" class="overlay-button-border"><div class="fullscreen-exit-button-interior"></div></div>\
                        </div></div>';

            $("#fullscreen").append(content);
            if(p.is_panorama) $('#image-drag-fullscreen').jParadrag({width: frame_width, height: frame_height, startPosition: frame_position,
                onMomentumStop: function() {
                        var pos = $("#image-drag-fullscreen .ui-draggable").position().left;
                        ce4.ui.current_panorama_position = Math.abs(((pos - frame_width / 2) % image_width) / image_width);
                },
                loop: true, factor: 1, momentum: {avg: 3, friction: 0.4}, onLoad: xri.ui.panorama_pan_buttons});

        }

        $(document).keydown($.proxy(ce4.ui.fullscreen_exit_on_esc, this));
        ce4.ui.is_fullscreen = true;
    }
    // Exit fullscreen
    else if(ce4.ui.is_fullscreen === true)
    {
        $("#xri-wrapper").show()
        if(ce4.ui.is_current_page_name(ce4.ui.LEAFLET))
        {
            $('#map-container').append($("#leaflet-container").detach());
            ce4.ui.leaflet.onShow();
        }
        else if(ce4.ui.is_current_page_name(ce4.ui.PICTURE))
        {
            var pos = ce4.ui.current_panorama_position && (ce4.ui.current_panorama_position * -ce4.ui.IMAGE_PANORAMA_SMALL_WDITH -ce4.ui.IMAGE_PANORAMA_SMALL_WDITH + 800 / 2) || (-4 * 800);
            if (pos > (-3 * 800)) pos -= 3 * 800;
            ce4.ui.get_current_bocks().panoramaShift(pos, 800);
            $("#image-drag .ui-draggable").css({left: pos});
        }
        $('#xri-tabs').append($("#fullscreen-tabs").children());
        $("#fullscreen").hide();
        $("#fullscreen-tabs").hide();
        $("#fullscreen").children().remove();

        $(document).unbind('keydown', ce4.ui.fullscreen_exit_on_esc);
        ce4.ui.is_fullscreen = false;
    }
};

//------------------------------------------------------------------------------
// Store UI
ce4.ui.store = {
    isStoreEnabled: function()
    {
        return (ce4.gamestate.user && ce4.gamestate.user.is_store_enabled());
    },
    initStore: function()
    {
        this.shoppingCart = {product_keys:[], product_specifics_list:[]};
    },
    mobileOpen: function()
    {
        // Check if gamestate is being initialized or store is disabled
        if (!this.isStoreEnabled()) return;

        // Initialize our shopping cart
        this.initStore();

        var storeDiv = $('<div id="store_container"></div>');

        storeDiv.html(""
                +  "    <div id=\"store-front\" style=\"display:none;\">\
                            <div id='store-items' class='store-items'></div>\
                            </div>"
                +  "    <div id=\"store-friend-details\" style=\"display:none;\">\
                            <form id=\"friend-details-form\">\
                            <table width='100%'><tr>\
                            <td class='store-selected-item'></td>\
                            <td>\
                              <strong>Enter recipient information</strong><br><br>\
                              <table cellpadding='3px'>\
                                <tr><td style='vertical-align:middle;'>Sender:</td><td>" + ce4.gamestate.user.first_name + " " + ce4.gamestate.user.last_name + "</td></tr>\
                                <tr><td style='vertical-align:middle;'>Recipient's name:</td><td><input type=\"text\" id=\"recipient_first_name\" class='store-recipient-first-name' placeholder=\"First\" autocorrect=\"off\"> \
                                                <input type=\"text\" id=\"recipient_last_name\" class='store-recipient-last-name' placeholder=\"Last\" autocorrect=\"off\"></td></tr>\
                                <tr><td style='vertical-align:middle;'>Recipient's email:</td><td><input type=\"email\" id=\"recipient_email\" class='store-recipient-email' value=\"\"/></td></tr>\
                              </table><br><br>\
                              <table cellpadding='3px'><tr><td>\
                              Add personal message (optional):<br>\
                              <textarea id=\"recipient_message\" class='store-recipient-message'>I'd like to invite you to try out for the Extrasolar Program, an amazing experience in space exploration, and the chance of a lifetime!</textarea><br><br><br>\
                              <center><button id=\"store-recipient-button\" class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.validateRecipient();return false;\">Next</button></center>\
                              </td></tr></table>\
                            </td></tr></table>\
                            </form>\
                            </div>"
                +  "    <div id=\"store-purchase\" style=\"display:none;\">\
                            <table width='100%'><tr>\
                            <td class='store-selected-item'></td>\
                            <td style='padding: 20px;'><span id='store-purchase-message'></span>\
                            <center>\
                            <div id='store-card-new' style=\"display:none;\">\
                                <table class='store-payment'><tr><td><img src=\""+ce4.util.url_static("/img/store/credit_cards_wide.png")+"\"><br><br>\
                                    <a href=\"https://stripe.com/us/terms/\"><img src=\""+ce4.util.url_static("/img/store/powered_by_strip.png")+"\"></a></td></tr>\
                                <tr><td>Cardholder's Name:<br><input type=\"text\" id=\"store-credit-card-name\" style='width:14em' value=\"\"/ autocorrect=\"off\"></td></tr>\
                                <tr><td>Card Number:<br><input type=\"text\" id=\"store-credit-card-number\" style='width:14em' placeholder=\"xxxx xxxx xxxx xxxx\"/>\
                                    <br><span id=\"store-credit-card-save-span\" class=\"clickable\" alt=\"Save credit card information for future purchases.\"><input type=\"checkbox\"\ id=\"store-credit-card-save\" value=\"1\">Save This Card</span></td></tr>\
                                <tr><td>Expiration Date:<br><select id=\"store-credit-card-expiration-month\"></select> <select id=\"store-credit-card-expiration-year\"></select></td></tr>\
                                <tr><td>Security Code:<br><input type=\"text\" id=\"store-credit-card-cvc\" style='width:2.5em' placeholder=\"CVC\"/></td></tr>\
                                </table>\
                                <br><button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.purchaseWithNewCard();\">Send Payment</button>\
                            </div>\
                            <div id='store-card-saved' style=\"display:none;\">\
                                <table class='store-payment'><tr><td><img src=\""+ce4.util.url_static("/img/store/credit_cards_wide.png")+"\">\
                                    <br><br><a href=\"https://stripe.com/us/terms/\"><img src=\""+ce4.util.url_static("/img/store/powered_by_strip.png")+"\"></a></td></tr>\
                                <tr><td>Cardholder's Name:<br><span id=\"store-card-saved-name\"></span></td></tr>\
                                <tr><td>Card Number:<br><span id=\"store-card-saved-number\"></span><br><span id=\"store-credit-card-remove-span\" class=\"clickable\" alt=\"Removed saved credit card information from store.\">clear card info</span></td></tr>\
                                <tr><td>Expiration Date:<br><span id=\"store-card-saved-expiry\"></span></td></tr>\
                                </table>\
                                <br><button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.purchaseWithSavedCard();\">Send Payment</button>\
                            </div>\
                            </center></td></tr></table>\
                        </div>"
                +  "    <div id=\"store-purchase-processing\" style=\"display:none;\">\
                            <center><br>Processing payment, please wait...<br><br><img src=\"" + ce4.ui.get_ui_asset_url("UI_LOADING") + "\"><br></center>\
                        </div>"
                +  "    <div id=\"store-failure\" style=\"display:none;\">\
                            <center><br><span id=\"store-failure-message\"></span><br><br>\
                            <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.util.toggleView('str', 'store-purchase', 1);\">Okay</button></center>\
                        </div>"
                +  "    <div id=\"store-success\" style=\"display:none;\">\
                            <center><br>Payment complete, thank you for supporting XRI!<br><br>\
                            <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.dialogClose();\">Ok</button></center>\
                        </div>"
                +  "    <div id=\"store-invitation-processing\" style=\"display:none;\">\
                            <center><br>Sending invitation, please wait...<br><br><img src=\"" + ce4.ui.get_ui_asset_url("UI_LOADING") + "\"><br></center>\
                        </div>"
                +  "    <div id=\"store-invitation-success\" style=\"display:none;\">\
                            <center><br>Your invitation was successfully sent.<br><br>\
                            <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.dialogClose();\">Ok</button></center>\
                        </div>"
                +  "    <div id=\"store-invitation-failure\" style=\"display:none;\">\
                            <center><br>There was an error while sending your invitation.  You may want to reload the page and try again.<br><br>\
                            <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.dialogClose();\">Ok</button></center>\
                        </div>");

        $("#upgrade_container").empty().html(storeDiv);

        this.populateStore(storeDiv);

        // Toggle the store front
        ce4.util.toggleView('str', 'store-front', 1);
    },
    // Calls dialogOpen without passing any parameters (from a callback)
    dialogOpenSimple: function(e)
    {
        ce4.ui.store.dialogOpen.call(ce4.ui.store);
    },
    dialogOpen: function(p)
    {
        // Check if gamestate is being initialized or store is disabled
        if (!this.isStoreEnabled()) return;

        if(ce4.ui.is_mobile) {
            window.location.hash = "#upgrade";
        }
        else
        {
            // Initialize our shopping cart
            this.initStore();

            // Set up the onClose callback
            this.onClose = p && p.onClose;

            // Prepare the dialog ui element
            if(this.dialogDiv === undefined)
            {
                this.dialogDiv = $('<div id="store_container"></div>');
                this.dialogDiv.dialog({
                        width: 800,
                        autoOpen: false,
                        dialogClass: 'default-dialog-theme',
                        modal: true,
                        position: 'center',
                        closeOnEscape: true,
                        draggable: false,
                        resizable: false,
                        close: this.onClose,
                        open: function(event, ui) { /* $(".ui-dialog-titlebar-close").hide(); */ }});
                this.dialogDiv.dialog('widget').css({'max-height': 800, 'overflow-y': 'auto'});
                this.dialogDiv.html(""
                    +  "    <div id=\"store-front\" style=\"display:none;\">\
                                To get the most out of Extrasolar, please upgrade your account to obtain priority access to satellite bandwidth and rover hardware.  For more details, visit our <a href='http://www.whatisextrasolar.com/support' target='_blank'>FAQ</a><br><br>\
                                <div id='store-items' class='store-items'></div>\
                                </div>"
                    +  "    <div id=\"store-friend-details\" style=\"display:none;\">\
                                <form id=\"friend-details-form\">\
                                <table width='100%'><tr>\
                                <td class='store-selected-item'></td>\
                                <td>\
                                  <strong>Enter recipient information</strong><br><br>\
                                  <table cellpadding='3px'>\
                                    <tr><td style='vertical-align:middle;'>Sender:</td><td>" + ce4.gamestate.user.first_name + " " + ce4.gamestate.user.last_name + "</td></tr>\
                                    <tr><td style='vertical-align:middle;'>Recipient's name:</td><td><input type=\"text\" id=\"recipient_first_name\" style='width:8em' placeholder=\"First\" autocorrect=\"off\"> \
                                                    <input type=\"text\" id=\"recipient_last_name\" style='width:8em' placeholder=\"Last\" autocorrect=\"off\"></td></tr>\
                                    <tr><td style='vertical-align:middle;'>Recipient's email:</td><td><input type=\"email\" id=\"recipient_email\" style='width:16.7em' value=\"\"/></td></tr>\
                                  </table><br><br>\
                                  <table cellpadding='3px'><tr><td>\
                                  Add personal message (optional):<br>\
                                  <textarea id=\"recipient_message\" class='store-recipient-message'>I'd like to invite you to try out for the Extrasolar Program, an amazing experience in space exploration, and the chance of a lifetime!</textarea><br><br><br>\
                                  <center><button id=\"store-recipient-button\" class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.validateRecipient();return false;\">Next</button></center>\
                                  </td></tr></table>\
                                </td></tr></table>\
                                </form>\
                                </div>"
                    +  "    <div id=\"store-purchase\" style=\"display:none;\">\
                                <table width='100%'><tr>\
                                <td class='store-selected-item'></td>\
                                <td style='padding: 20px;'><span id='store-purchase-message'></span>\
                                <center>\
                                <div id='store-card-new' style=\"display:none;\">\
                                    <table class='store-payment'><tr><td><img src=\""+ce4.util.url_static("/img/store/credit_cards_wide.png")+"\"></td>\
                                        <td><a href=\"https://stripe.com/us/terms/\"><img src=\""+ce4.util.url_static("/img/store/powered_by_strip.png")+"\"></a></td></tr>\
                                    <tr><td>Cardholder's Name:<br><input type=\"text\" id=\"store-credit-card-name\" style='width:14em' value=\"\"/ autocorrect=\"off\"></td>\
                                        <td>Expiration Date:<br><select id=\"store-credit-card-expiration-month\"></select> <select id=\"store-credit-card-expiration-year\"></select></td></tr>\
                                    <tr><td>Card Number:<br><input type=\"text\" id=\"store-credit-card-number\" style='width:14em' placeholder=\"xxxx xxxx xxxx xxxx\"/>\
                                        <br><span id=\"store-credit-card-save-span\" class=\"clickable\" alt=\"Save credit card information for future purchases.\"><input type=\"checkbox\"\ id=\"store-credit-card-save\" value=\"1\">Save This Card</span></td>\
                                        <td>Security Code:<br><input type=\"text\" id=\"store-credit-card-cvc\" style='width:2.5em' placeholder=\"CVC\"/></td></tr>\
                                    </table>\
                                    <br><button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.purchaseWithNewCard();\">Send Payment</button>\
                                </div>\
                                <div id='store-card-saved' style=\"display:none;\">\
                                    <table class='store-payment'><tr><td><img src=\""+ce4.util.url_static("/img/store/credit_cards_wide.png")+"\"></td>\
                                        <td><a href=\"https://stripe.com/us/terms/\"><img src=\""+ce4.util.url_static("/img/store/powered_by_strip.png")+"\"></a></td></tr>\
                                    <tr><td>Cardholder's Name:<br><span id=\"store-card-saved-name\"></span></td>\
                                        <td>Expiration Date:<br><span id=\"store-card-saved-expiry\"></span></td></tr>\
                                    <tr><td>Card Number:<br><span id=\"store-card-saved-number\"></span></td>\
                                        <td><span id=\"store-credit-card-remove-span\" class=\"clickable\" alt=\"Removed saved credit card information from store.\">clear card info</span></td></tr>\
                                    </table>\
                                    <br><button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.purchaseWithSavedCard();\">Send Payment</button>\
                                </div>\
                                </center></td></tr></table>\
                            </div>"
                    +  "    <div id=\"store-purchase-processing\" style=\"display:none;\">\
                                <center><br>Processing payment, please wait...<br><br><img src=\"" + ce4.ui.get_ui_asset_url("UI_LOADING") + "\"><br></center>\
                            </div>"
                    +  "    <div id=\"store-failure\" style=\"display:none;\">\
                                <center><br><span id=\"store-failure-message\"></span><br><br>\
                                <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.util.toggleView('str', 'store-purchase', 1);\">Okay</button></center>\
                            </div>"
                    +  "    <div id=\"store-success\" style=\"display:none;\">\
                                <center><br>Payment complete, thank you for supporting XRI!<br><br>\
                                <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.dialogClose();\">Ok</button></center>\
                            </div>"
                    +  "    <div id=\"store-invitation-processing\" style=\"display:none;\">\
                                <center><br>Sending invitation, please wait...<br><br><img src=\"" + ce4.ui.get_ui_asset_url("UI_LOADING") + "\"><br></center>\
                            </div>"
                    +  "    <div id=\"store-invitation-success\" style=\"display:none;\">\
                                <center><br>Your invitation was successfully sent.<br><br>\
                                <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.dialogClose();\">Ok</button></center>\
                            </div>"
                    +  "    <div id=\"store-invitation-failure\" style=\"display:none;\">\
                                <center><br>There was an error while sending your invitation.  You may want to reload the page and try again.<br><br>\
                                <button class=\"gradient-button gradient-button-store\" onclick=\"ce4.ui.store.dialogClose();\">Ok</button></center>\
                            </div>");
            }

            this.populateStore(this.dialogDiv);

            // Open the dialog
            this.dialogDiv.dialog('option', 'title',"XRI Store");
            this.dialogDiv.dialog('open');
            this.dialogDiv.dialog('widget').position({my: 'top', at: 'top+80', of: $('#xri-wrapper'), collision: 'none'});

            // Toggle the store front
            ce4.util.toggleView('str', 'store-front', 1);
        }
    },
    populateStore: function(storeDiv)
    {
        // Set up credit card save / remove buttons
        $("#store-credit-card-save-span").click(ce4.util.selectRow);
        $("#store-credit-card-remove-span").click($.proxy(function() {
            ce4.gamestate.user.shop.stripeRemoveSavedCard(); // FUTU: Callbacks for success and failure?
            ce4.util.toggleView('str-save', 'store-card-new', 1);
        }));

        // Populate Expiration Date select boxes
        var selectMonth = $("#store-credit-card-expiration-month").empty();
        var selectYear  = $("#store-credit-card-expiration-year").empty();
        var currentYear = (new Date).getFullYear();
        for (var i = 1; i <= 12; i++) selectMonth.append($("<option value='"+i+"'>"+ce4.util.pad_int(i,2)+"</option>"));
        for (var i = 0; i < 11; i++) selectYear.append($("<option value='"+(i + currentYear)+"'>"+(i + currentYear)+"</option>"));

        // Dummy product for "Volunteer"
        var default_product = {name: "XRI Volunteer", description: "Limited access to rover features like infrared imaging, panoramas, accelerated photo scheduling, and high-resolution downloads.", icon: ce4.util.url_static("/img/products/sku_volunteer.png")};

        // TODO: When running either purchaseProduct or purchaseGift, display the selected product in div #purchase-item.
        this.purchaseProduct = $.proxy(function(product_key) {
            var product = ce4.gamestate.user.shop.available_products.get(product_key);
            $('#store-purchase-message').html("<b>"+ce4.ui.product.header[product_key]+"</b><br><br>Thank you for supporting XRI!  Your rover functionality will unlock immediately upon completion of payment. If you prefer, you may arrange payment with <a href='http://www.whatisextrasolar.com/payment_options/?email="+ce4.gamestate.user.email+"&item="+ce4.ui.product.header[product_key]+"&price="+product.price_display+"' target='_blank'>Paypal</a>.");
            $('.store-selected-item').html(this.storeItemHTML(ce4.gamestate.user.shop, product_key, false));
            $('.store-price').html(product.price_display).show();
            this.initTooltips();
            this.shoppingCart.product_keys = [product_key];
            ce4.util.toggleView('str', 'store-purchase', 1)
        }, this);

        this.purchaseGift = $.proxy(function(product_key) {
            var product = ce4.gamestate.user.shop.available_products.get(product_key);
            $('#store-purchase-message').html("<b>"+ce4.ui.product.header[product_key]+"</b><br><br>Thank you for supporting XRI!  Your invitation will be sent immediately upon completion of payment. If you prefer, you may arrange payment with <a href='http://www.whatisextrasolar.com/payment_options/?email="+ce4.gamestate.user.email+"&item="+ce4.ui.product.header[product_key]+"&price="+product.price_display+"' target='_blank'>Paypal</a>.");
            $('.store-selected-item').html(this.storeItemHTML(ce4.gamestate.user.shop, product_key, false));
            $('.store-price').html(product.price_display).show();
            $('#store-recipient-button').html('Next');
            this.initTooltips();
            this.shoppingCart.product_keys = [product_key];
            ce4.util.toggleView('str', 'store-friend-details', 1)
        }, this);

        this.sendInvitation = $.proxy(function(product_key) {
            $('#store-purchase-message').html("<b>"+ce4.ui.product.header[product_key]+"</b><br><br>Thank you for supporting XRI!  Your invitation will be sent immediately upon completion of payment.");
            $('.store-selected-item').html(this.storeItemHTML(ce4.gamestate.user.shop, 'SKU_INVITATION', false));
            $('#store-recipient-button').html('Send Invitation');
            this.initTooltips();
            this.shoppingCart.product_keys = [];  // No product key for invitations
            ce4.util.toggleView('str', 'store-friend-details', 1)
        }, this);

        this.storeItemHTML = function(shop, sku, show_buttons) {
            var item = ce4.ui.product.details[sku];
            if (item === undefined) console.error('Unexpected sku '+sku+' in ce4.ui.store');

            var html = "<div class='store-item "+item.div_class+"'>\
                <div class='store-tooltip store-tooltip-"+sku+"'></div>\
                <table width=100%>\
                <tr><td align='center' height=117 style='vertical-align:middle'><img src='"+item.icon+"'></td></tr>\
                <tr><td align='center' height=80 style='vertical-align:top;'><span class='store-item-title'>"+item.title+"</span><br>\
                    <span class='store-item-subtitle'>"+item.subtitle+"</span></td></tr>\
                <tr><td>\
                    <table>\
                        <tr><td class='store-activate-tooltip' data-tooltip='Scheduled moves' data-tooltip-class='.store-tooltip-"+sku+"'>\
                            <img src='"+ce4.util.url_static("/img/store/icon_moves.png")+"'></td><td>=</td>\
                            <td class='store-activate-tooltip' data-tooltip='Scheduled moves' data-tooltip-class='.store-tooltip-"+sku+"'>"+item.moves+"</td><td width=15px rowspan=5></td>\
                            <td rowspan=4 style='vertical-align:middle' class='store-activate-tooltip' data-tooltip='Minimum photo delay' data-tooltip-class='.store-tooltip-"+sku+"'><img src='/img/store/store_planetIcon.png'><br>"+item.min_time+"</td></tr>\
                        <tr><td class='store-activate-tooltip' data-tooltip='Camera flash' data-tooltip-class='.store-tooltip-"+sku+"'>\
                            <img src='"+ce4.util.url_static("/img/store/icon_flash.png")+"'></td><td>=</td>\
                            <td class='store-activate-tooltip' data-tooltip='Camera flash' data-tooltip-class='.store-tooltip-"+sku+"'><span class='large-text'>&infin;</span></td></tr>\
                        <tr><td class='store-activate-tooltip' data-tooltip='Panorama photos' data-tooltip-class='.store-tooltip-"+sku+"'>\
                            <img src='"+ce4.util.url_static("/img/store/icon_panorama.png")+"'></td><td>=</td>\
                            <td class='store-activate-tooltip' data-tooltip='Panorama photos' data-tooltip-class='.store-tooltip-"+sku+"'>"+item.panoramas+"</td></tr>\
                        <tr><td class='store-activate-tooltip' data-tooltip='Infrared photos' data-tooltip-class='.store-tooltip-"+sku+"'>\
                            <img src='"+ce4.util.url_static("/img/store/icon_infrared.png")+"'></td><td>=</td>\
                            <td class='store-activate-tooltip' data-tooltip='Infrared photos' data-tooltip-class='.store-tooltip-"+sku+"'>"+item.infrared+"</td></tr>\
                        <tr><td colspan=3>"+item.feature_description+"</td><td>"+item.min_time_description+"</td></tr>\
                    </table>\
                </td></tr>\
                <tr><td height=60 style='vertical-align:middle;'>"+item.final_description+"</td></tr>\
                <tr><td height=70 style='vertical-align:middle;'>";
            if (show_buttons) {
                if (sku === 'SKU_INVITATION') {
                    // Special case for the first column: Invitations.
                    if (ce4.gamestate.user.invites_left > 0) {
                        html += "<button class='gradient-button gradient-button-store' style='min-width: 220px; margin-top: 10px;' onclick='ce4.ui.store.sendInvitation();'>Invite Friend<br>"+ce4.gamestate.user.invites_left+" invitations left</button>";
                    }
                    else {
                        html += "<button class='gradient-button gradient-button-store-disabled' style='min-width: 220px; margin-top: 10px;'>Invite Friend<br>0 invitations left</button>";
                    }
                }
                else {
                    // Buy for user.
                    var product = shop.available_products.get(item.product_key)
                    if (product !== undefined) {
                        html += "<button class='gradient-button gradient-button-store'  style='min-width: 220px; margin-top: 10px;'onclick='ce4.ui.store.purchaseProduct(\""+item.product_key+"\");'>"+product.price_display+"</button><br>";
                    }
                    else {
                        html += "<button class='gradient-button gradient-button-store-disabled' style='min-width: 220px; margin-top: 10px;'>Active</button><br>";
                    }
                    // Buy as gift.
                    product = shop.available_products.get(item.product_key_gift)
                    if (product !== undefined) {
                        html += "<button class='gradient-button gradient-button-store' style='min-width: 220px; margin-top: 5px;' onclick='ce4.ui.store.purchaseGift(\""+item.product_key_gift+"\");'>Gift a Friend: "+product.price_display+"</button>";
                    }
                }
            }
            else {
                html += "<div class='store-price' style='display: none;'></div>";
            }
            html += "</td></tr></table></div>";
            return html;
        }

        // Initialize tooltips.  If you mouseover anything with class store-activate-tooltip,
        // show the desired content (from the data-tooltip field) in the desired div (from the
        // data-tooltip-class field).
        this.initTooltips = function() {
            $('.store-activate-tooltip').each(function(index, self) {
                $(self).mouseenter($.proxy(function() {
                    var tooltip = $(this).data('tooltip');
                    var tooltipClass = $(this).data('tooltip-class');
                    $(tooltipClass).html(tooltip).show();
                }, this));

                $(self).mouseleave($.proxy(function() {
                    var tooltipClass = $(this).data('tooltip-class');
                    $(tooltipClass).hide();
                }, this));
            });
        }

        storeDiv.find('#store-items').empty();
        var storeItemsHTML = "";
        storeItemsHTML += this.storeItemHTML(ce4.gamestate.user.shop, 'SKU_INVITATION', true);
        storeItemsHTML += this.storeItemHTML(ce4.gamestate.user.shop, 'SKU_S1_PASS', true);
        storeItemsHTML += this.storeItemHTML(ce4.gamestate.user.shop, 'SKU_ALL_PASS', true);
        storeDiv.find('#store-items').html(storeItemsHTML);
        this.initTooltips();

        // Display the saved card or new card input
        if(ce4.gamestate.user.shop.has_stripe_saved_card()) {
            storeDiv.find("#store-card-saved-name").html(ce4.gamestate.user.shop.stripe_customer_data.card_name);
            storeDiv.find("#store-card-saved-number").html("**** **** **** " + ce4.gamestate.user.shop.stripe_customer_data.card_last4 + " (" + ce4.gamestate.user.shop.stripe_customer_data.card_type + ")");
            storeDiv.find("#store-card-saved-expiry").html(ce4.util.pad_int(ce4.gamestate.user.shop.stripe_customer_data.card_exp_month,2) + " / " + ce4.gamestate.user.shop.stripe_customer_data.card_exp_year);

            ce4.util.toggleView('str-save', 'store-card-saved', 1);
        }
        else {
            ce4.util.toggleView('str-save', 'store-card-new', 1);
        }
    },
    dialogClose: function() // FUTU: Rename this to something not "dialog", like storeClose
    {
        if(ce4.ui.is_mobile) ce4.util.toggleView('str', 'store-front', 1);
        else this.dialogDiv.dialog('close');
    },
    validateRecipient: function()
    {
        var storeDiv = $("#store_container");

        // Recipient data.
        var product_specifics = {
            send_invite:            true,
            recipient_email:        ce4.util.trim(storeDiv.find("#recipient_email").val()),
            recipient_first_name:   ce4.util.trim(storeDiv.find("#recipient_first_name").val()),
            recipient_last_name:    ce4.util.trim(storeDiv.find("#recipient_last_name").val()),
            recipient_message:      ce4.util.trim(storeDiv.find("#recipient_message").val())
        }

        // Validation
        var is_valid_name  = xri.validation.isValidName(product_specifics.recipient_first_name, product_specifics.recipient_last_name)
        var is_valid_email = xri.validation.isValidEmail(product_specifics.recipient_email);

        // Highlight invalid fields
        storeDiv.find("#recipient_email").toggleClass("invalid", !is_valid_email);
        storeDiv.find("#recipient_first_name").toggleClass("invalid", !is_valid_name);
        storeDiv.find("#recipient_last_name").toggleClass("invalid", !is_valid_name);

        // If we're sending an invitation with no gift, show a "Sending invitation" dialog.
        if (this.shoppingCart.product_keys.length === 0) {
            if (is_valid_email && is_valid_name && ce4.gamestate.user.invites_left > 0) {
                // If the invitation is successfully sent, show the success dialog.
                var cbSuccess = $.proxy(function(event, value) {
                    $('#friend-details-form')[0].reset();
                    ce4.util.toggleView('str', 'store-invitation-success', 1);
                }, this);

                // If the server returns an error, show the failure dialog.
                var cbFailure = $.proxy(function(event, value) {
                    ce4.util.toggleView('str', 'store-invitation-failure', 1);
                }, this);

                ce4.invite.create_invite(product_specifics.recipient_email, product_specifics.recipient_first_name,
                    product_specifics.recipient_last_name, product_specifics.recipient_message, cbSuccess, cbFailure);
                ce4.util.toggleView('str', 'store-invitation-processing', 1);
            }
        }
        // Else we're purchasing a gift for this recipient.  Get payment info.
        else {
            if (is_valid_email && is_valid_name)  {
                this.shoppingCart.product_specifics_list = [product_specifics];
                ce4.util.toggleView('str', 'store-purchase', 1);
            }
        }
    },
    purchaseWithNewCard: function()
    {
        var storeDiv = $("#store_container");

        // Card Information
        var card = {
            number:     storeDiv.find("#store-credit-card-number").val(),
            cvc:        storeDiv.find("#store-credit-card-cvc").val(),
            exp_month:  storeDiv.find("#store-credit-card-expiration-month").val(),
            exp_year:   storeDiv.find("#store-credit-card-expiration-year").val(),
            name:       storeDiv.find("#store-credit-card-name").val()
        }

        // Validation
        var is_validCardNumber  = Stripe.card.validateCardNumber(card.number);
        var is_validCard        = Stripe.card.validateCVC(card.cvc);
        var is_validExpiry      = Stripe.card.validateExpiry(card.exp_month, card.exp_year);

        // Highlight invalid fields
        storeDiv.find("#store-credit-card-number").toggleClass("invalid", !is_validCardNumber);
        storeDiv.find("#store-credit-card-cvc").toggleClass("invalid", !is_validCard);
        storeDiv.find("#store-credit-card-expiration-month").toggleClass("invalid", !is_validExpiry);
        storeDiv.find("#store-credit-card-expiration-year").toggleClass("invalid", !is_validExpiry);

        // Submit purchase to stripe
        if(is_validCardNumber && is_validCard && is_validExpiry)  {
            this.beginPurchaseAttempt();
            ce4.util.toggleView('str', 'store-purchase-processing', 1);
            ce4.gamestate.user.shop.stripePurchaseWithNewCard(this.shoppingCart.product_keys, this.shoppingCart.product_specifics_list, card, storeDiv.find("#store-credit-card-save").is(':checked'), $.proxy(this.purchaseSuccess, this), $.proxy(this.purchaseFailure, this));
        }
    },
    purchaseWithSavedCard: function()
    {
        this.beginPurchaseAttempt();
        ce4.util.toggleView('str', 'store-purchase-processing', 1);
        ce4.gamestate.user.shop.stripePurchaseWithSavedCard(this.shoppingCart.product_keys, this.shoppingCart.product_specifics_list, $.proxy(this.purchaseSuccess, this), $.proxy(this.purchaseFailure, this));
    },
    beginPurchaseAttempt: function()
    {
        // TODO: Fill in this stub function to send an event to Google Analytics.
        // Since we're using the Google Tag Manager, we'll probably do this by pushing
        // an event to the dataLayer.
    },
    purchaseSuccess: function(data)
    {
        $('#friend-details-form')[0].reset();
        if(!ce4.ui.is_mobile) this.dialogDiv.dialog('option', 'title',"Priority Access Granted!");
        ce4.util.toggleView('str', 'store-success', 1);
        // TODO: Send an event to Google Analytics to record the purchase.
    },
    purchaseFailure: function(error)
    {
        var storeDiv = $("#store_container");
        storeDiv.find("#store-failure-message").html(error);
        ce4.util.toggleView('str', 'store-failure', 1);
    }
};


//------------------------------------------------------------------------------
// Upgrade Nag UI
ce4.ui.upgrade = {
    dialogOpen: function(variant, p)
    {
        this.onCancel = p && p.onCancel;
        var title = {
                        "upgrade-photo-download" : "Download High-Resolution Image?",
                        "upgrade-wizard-delay"   : "Upgrade account for accelerated photo scheduling?",
                        "upgrade-wizard-options" : "Photo Option Unavailable"
                    };

        // Prepare the dialog ui element
        if(this.dialogDiv === undefined)
        {
            this.dialogDiv = $('<div></div>');
            this.dialogDiv.dialog($.extend({
                    autoOpen: false,
                    dialogClass: 'default-dialog-theme',
                    modal: true,
                    position: 'center',
                    closeOnEscape: true,
                    draggable: false,
                    resizable: false,
                    close: $.proxy(function(event, ui) {if(this.onCancel) this.onCancel();},this),
                    open: function(event, ui) { /* $(".ui-dialog-titlebar-close").hide(); */ }}, ce4.ui.is_mobile ? {width: '85%'} : {width: '500'}));
            this.dialogDiv.dialog('widget').css({'max-height': 800, 'overflow-y': 'auto'});
            this.dialogDiv.html(""
                +  "    <div id=\"upgrade-photo-download\" style=\"display:none;\">\
                              X available\
                              <br><br>\
                              Standard users have limited downloads due to satellite bandwidth constraints.  Upgrade your account for unlimited downloads.\
                              <br><br><center>\
                              <button class=\"gradient-button gradient-button-standard\" onclick=\"ce4.ui.upgrade.dialogClose();\">Cancel</button>\
                              <button class=\"gradient-button gradient-button-standard\" onclick=\"ce4.ui.upgrade.dialogStore();\">Upgrade Account</button></center>\
                        </div>"
                +  "    <div id=\"upgrade-wizard-delay\" style=\"display:none;\">\
                              To schedule photos with less than a 4-hour delay, please consider upgrading your account.\
                              <br><br><center>\
                              <button class=\"gradient-button gradient-button-standard\" onclick=\"ce4.ui.upgrade.dialogClose();\">Cancel</button>\
                              <button class=\"gradient-button gradient-button-standard\" onclick=\"ce4.ui.upgrade.dialogStore();\">Upgrade Account</button></center>\
                        </div>"
                +  "    <div id=\"upgrade-wizard-options\" style=\"display:none;\">\
                              Please consider upgrading your account for unlimited access to infrared photos, high-resolution downloads, accelerated photo scheduling, and more.\
                              <br><br><center>\
                              <button class=\"gradient-button gradient-button-standard\" onclick=\"ce4.ui.upgrade.dialogClose();\">Cancel</button>\
                              <button class=\"gradient-button gradient-button-standard\" onclick=\"ce4.ui.upgrade.dialogStore();\">Upgrade Account</button></center>\
                        </div>");
        }

        // Open the dialog
        this.dialogDiv.dialog('option', 'title', title[variant]);
        this.dialogDiv.dialog('open');
        this.dialogDiv.dialog('widget').position({my: 'center', at: 'center', of: $('#xri-wrapper'), collision: 'none'});
        ce4.util.toggleView('str', variant, 1);
    },
    dialogClose: function()
    {
        this.dialogDiv.dialog('close');
    },
    dialogStore: function()
    {
        var onStoreClose = this.onCancel;
        this.onCancel = undefined;
        this.dialogClose();
        ce4.ui.store.dialogOpen({onClose: onStoreClose});
    }
};


//------------------------------------------------------------------------------
// Terminal UI
ce4.ui.terminal = {
    open: function(greeting, custom_command_list)
    {
        var terminal_div;
        var exit_action = ce4.ui.is_mobile ? function(){terminal_div.destroy(); $('#kryptex_mobile_terminal').remove();} : function(){ this.dialog('close');};

        var command_list = [{expression: /^exit$/i, action: exit_action}]
                            .concat(custom_command_list)
                            .concat([{expression: /^.+$/i,   action: function(echo, command){ echo("Unrecognized command: "+command); }}]);

        var command_term = function(command, term) {
                                $.each(command_list, function(i, command_item) {
                                    if(command_item.expression.test(command)) {
                                       command_item.action.apply(term, [term.echo, command].concat(command_item.params));
                                       return false;
                                   }
                                });
                            };

        if(!ce4.ui.is_mobile)
        {
            var terminal_div = $('<div></div>')
                .dterm(command_term, {
                    greetings: greeting,
                    width: 480,
                    height: 320,
                    dialogClass: 'terminal-dialog-theme',
                    autoOpen: false,
                    title: 'Terminal | ~kryptex/xri/scripts',
                    modal: true,
                    exit: false,
                    closeOnEscape: true,
                    draggable: false,
                    resizable: false,
                    altinput: ce4.ui.is_mobile
                })
               .dialog('open')
               .dialog('widget').position({my: 'center', at: 'center', of: $('#xri-wrapper'), collision: 'none'});
        }
        else
        {
            var terminal_div = $('<div id="kryptex_mobile_terminal" class="kryptex-mobile-terminal"></div>').append($('<div class="kryptex-mobile-terminal-header">Terminal</div>')
                .append($('<div class="kryptex-mobile-terminal-close clickable">X</div>').click(exit_action))).appendTo("body")
                .terminal(command_term, {
                    greetings: greeting,
                    exit: false,
                    title: 'Terminal | ~kryptex/xri/scripts',
                    altinput: ce4.ui.is_mobile
                });
        }
    }
};




//------------------------------------------------------------------------------
// MOBILE UI FUNCTIONS
//------------------------------------------------------------------------------


//------------------------------------------------------------------------------
// Toggle the mobile menu open and closed
ce4.ui.mobile_menu_toggle = function (hashtag) {

    // If the menu is sliding open or closed, ignore the button click
    if(ce4.ui.is_mobile_menu_active) return;
    else ce4.ui.is_mobile_menu_active = true;

    var animation_done = function() {ce4.ui.is_mobile_menu_active = false; if(hashtag !== undefined) window.location.hash = hashtag;};

    // Menu is open
    if(ce4.ui.is_mobile_menu_open)
    {
        $("#mobile-menu-button").animate({left:'-5px'});
        $("#mobile-menu").hide("slide", { direction: "left" }, 250, animation_done);

    }
    // Menu is closed
    else
    {
        // Update unviewed counts
        ce4.ui.update_unviewed_message_count();
        ce4.ui.update_unviewed_photo_count();
        ce4.ui.update_unviewed_task_count();
        ce4.ui.update_unviewed_catalog_count();

        $("#mobile-menu-button").animate({left:'-10px'});
        $("#mobile-menu").show("slide", { direction: "left" }, 250, animation_done);
    }

    // Clear unviewed alerts for home and profile
    if(hashtag == "#home")    ce4.ui.clear_unviewed_alerts("home");
    if(hashtag == "#profile") ce4.ui.clear_unviewed_alerts("profile");

    // Toggle the state
    ce4.ui.is_mobile_menu_open = !ce4.ui.is_mobile_menu_open;
};


//------------------------------------------------------------------------------
// Display alert history on home page
ce4.ui.mobile_home_notifications = function () {
    ce4.util.forEach(ce4.gamestate.user.unviewed_alerts(true).slice(-11).reverse(), ce4.ui.mobile_notification);
};


//------------------------------------------------------------------------------
// Called for the mobile home page
ce4.ui.mobile_notification = function(alert_data)
{
    // Display Notifications
    ce4.ui.mobile_alert_notification(alert_data.type, alert_data.object);
};


//------------------------------------------------------------------------------
// Call the alert_display function with the notify formatting
ce4.ui.mobile_alert_notification = function(type, object)
{
    ce4.ui.alert_display(type, object, ce4.ui.mobile_display_notification);
};


//------------------------------------------------------------------------------
// Displays a notification
// p = {url: , icon: , title: , details: }
ce4.ui.mobile_display_notification = function(p)
{
    var notification = $("<div class='notification-item'><div class='notification-icon-border'><img src='"+p.icon+"'></div><span><p class='notification-title dwindle'><b>"+p.title+"</b></p><p class='notification-details'>"+p.details+"</p></span></div>").click(function(){window.location = p.url;});
    if(!p.viewed) notification.append('<span class="new-overlay"></span>');
    $("#notification-list").append(notification);
};


//------------------------------------------------------------------------------
// Dynamically sets gallery thumbnail size
ce4.ui.mobile_gallery_thumbnail_size = function()
{
    var dynamic_size = ce4.ui.mobile_calculate_dynamic_thumb_size();
    $('.newest-data ul li>img, .newest-data ul li a>img').height(dynamic_size.height).width(dynamic_size.width);

};

//------------------------------------------------------------------------------
// Dynamically sets image and video sizes in messages
ce4.ui.resize_relative_to_width = function(item, scale) {
    if (item.original_width === undefined) {
        item.original_width = item.width;
        item.original_height = item.height;
    }
    // If the original size fits, use that.
    if (item.original_width <= $('#id-game-header-mobile').width()*scale) {
        item.width = item.original_width;
        item.height = item.original_height;
    }
    else {
        item.width = $('#id-game-header-mobile').width()*scale;
        item.height = item.width*(item.original_height/item.original_width);
    }
};

ce4.ui.mobile_resize_message_content = function()
{
    $('.message-image').children('img').each(function(index) {
        ce4.ui.resize_relative_to_width(this, 0.9);
    });

    $('.message-video').children('iframe').each(function(index) {
        ce4.ui.resize_relative_to_width(this, 0.9);
    });
};

ce4.ui.mobile_resize_picture_content = function()
{
    // Resize the sound control to fit within 90% of the screen width.
    var page_width = $('#id-game-header-mobile').width();
    var item_width = 360;
    if (item_width > page_width*0.9) {
        item_width = page_width*0.9;
    }
    $('.mobile-sound-control').width(item_width);
    $('.mobile-sound-control iframe').width(item_width);
    $('.mobile-sound-control').css({'margin-left': '-'+(item_width/2)+'px'});  // Recenter.
}

//------------------------------------------------------------------------------
// Calculate the size for thumbnail
ce4.ui.mobile_calculate_dynamic_thumb_size = function(){
    var dynamic_width = $('#photo-container').width() / Math.ceil($('#photo-container').width() / (ce4.ui.MOBILE_THUMB_IMAGE_DEFAULT_WIDTH + ce4.ui.MOBILE_THUMB_IMAGE_PADDING)) - ce4.ui.MOBILE_THUMB_IMAGE_PADDING;
    var dynamic_height = dynamic_width * 0.75;

    return {width: dynamic_width, height: dynamic_height};
};


