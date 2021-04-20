// Copyright (c) 2010-2012 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.leaflet.assets contains the map asset (icons/styles) constants.
goog.provide('ce4.leaflet.assets');
goog.provide('ce4.leaflet.assets.icons');
goog.provide('ce4.leaflet.assets.styles');
goog.require('ce4.util');


L.Icon.Default.imagePath = ce4.util.url_static('/img/leaflet'); // Default image location, used for the default marker (used by leaflet draw)

// TODO: add popupAnchor: to all icons.

// Defaults
ce4.leaflet.assets.TEMPLATE_ICON      = { iconSize: [48,48],
                                          iconAnchor: [19,47],
                                          shadowUrl: ce4.util.url_static("/img/map_icons/icon_shadow.png"),
                                          shadowSize: [48,48],
                                          shadowAnchor: [19,47]};

ce4.leaflet.assets.TEMPLATE_ICON_DONE = { iconSize: [40,40],
                                          iconAnchor: [15,39],
                                          shadowUrl: ce4.util.url_static("/img/map_icons/icon_shadow_done.png"),
                                          shadowSize: [40,40],
                                          shadowAnchor: [15,39]};


//TODO Cleanup ce4.region.marker_icons.GPS           = "";

// Leaflet Icons
ce4.leaflet.assets.icons = {
    DEFAULT                       : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/button_quest5.png")},   ce4.leaflet.assets.TEMPLATE_ICON)), // TODO: Put ugly icon in here

    // Marker Icons
    MARKER_ICON_ANIMAL            : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_animal.png")},        ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_ARTIFACT          : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-purple.png")},   ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_AUDIO_BLUE        : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_audio-blue.png")},    ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_AUDIO_GOLD        : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_audio-gold.png")},    ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_AUDIO_PURPLE      : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_audio-purple.png")},  ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_AUDIO_RED         : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_audio-red.png")},     ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_AUDIO_YELLOW      : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_audio-yellow.png")},  ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_EXC_BLUE          : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-blue.png")},      ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_EXC_GOLD          : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-gold.png")},      ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_EXC_PURPLE        : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-purple.png")},    ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_EXC_RED           : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-red.png")},       ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_EXC_YELLOW        : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-yellow.png")},    ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_GPS               : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_GPS.png")},           ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_MYSTERY           : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-yellow.png")},   ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_QUES_BLUE         : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-blue.png")},     ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_QUES_GOLD         : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-gold.png")},     ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_QUES_PURPLE       : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-purple.png")},   ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_QUES_RED          : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-red.png")},      ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_QUES_YELLOW       : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-yellow.png")},   ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_ROVER             : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_rover.png")},         ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_RUINS             : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-red.png")},       ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_RUINS_SIGNAL      : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc-yellow.png")},    ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_LANDER            : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_lander.png")},        ce4.leaflet.assets.TEMPLATE_ICON)), // TODO: Update to use region?
    MARKER_ICON_TRANSMISSION      : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_EMtransmission.png")},ce4.leaflet.assets.TEMPLATE_ICON)),
    MARKER_ICON_COMPASS           : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_compass.png")},       ce4.leaflet.assets.TEMPLATE_ICON)), // TODO: Not used?
    WAYPOINT                      : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques-yellow.png")},   ce4.leaflet.assets.TEMPLATE_ICON)), // TODO: PLACEHOLDER

    // Marker Icons DONE
    MARKER_ICON_ANIMAL_DONE       : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_animal_done.png")},   ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    MARKER_ICON_ARTIFACT_DONE     : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_artifact_done.png")}, ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    MARKER_ICON_AUDIO_DONE        : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_audio_done.png")},    ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    MARKER_ICON_EXC_DONE          : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_exc_done.png")},      ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    MARKER_ICON_GPS_DONE          : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_GPS_done.png")},      ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    MARKER_ICON_LANDER_DONE       : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_lander_done.png")},   ce4.leaflet.assets.TEMPLATE_ICON_DONE)), // TODO: Update to use region?
    MARKER_ICON_QUES_DONE         : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_ques_done.png")},     ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    MARKER_ICON_ROVER_DONE        : new L.Icon($.extend({iconUrl: ce4.util.url_static("/img/map_icons/icon_rover_done.png")},    ce4.leaflet.assets.TEMPLATE_ICON_DONE)),
    // TODO? MARKER_ICON_MYSTERY_DONE
    // TODO? MARKER_ICON_RUINS_DONE
    // TODO? MARKER_ICON_RUINS_SIGNAL_DONE
    // TODO? MARKER_ICON_TRANSMISSION_DONE

    // Landmark Icon
    MARKER_ICON_LANDMARK        : new L.Icon({ iconUrl: ce4.util.url_static("/img/map_icons/icon_flag.png"),                     iconSize: [48,48],  iconAnchor: [25,44],
                                               shadowUrl: ce4.util.url_static("/img/map_icons/icon_flag_shadow.png"),            shadowSize: [48,48],shadowAnchor: [25,44]}),

    // Control Icons
    PLAYER_ROVER                : new L.Icon({ iconUrl: ce4.util.url_static("/img/map_icons/map_playerRover.png"),               iconSize: [34,32],  iconAnchor: [17,17]}),
    DRAG_CONTROL                : new L.Icon({ iconUrl: ce4.util.url_static("/img/map_icons/map_moveArrows.png"),                iconSize: [54,54],  iconAnchor: [26,28]}),
    TARGET_POINT                : new L.Icon({ iconUrl: ce4.util.url_static("/img/dw/direction_targetPoint.png"),                iconSize: [12,12],  iconAnchor: [7,7]}),
    TARGET_PENDING              : new L.Icon({ iconUrl: ce4.util.url_static("/img/map_icons/map_target_pending.png"),            iconSize: [41,41],  iconAnchor: [20,20]}),
    TARGET_RECENT               : new L.Icon({ iconUrl: ce4.util.url_static("/img/map_icons/map_target_recent.png"),             iconSize: [65,65],  iconAnchor: [32,32]}),
    TARGET_DONE                 : new L.Icon({ iconUrl: ce4.util.url_static("/img/map_icons/map_target_done.png"),               iconSize: [13,13],  iconAnchor: [6,6]}),
    TARGET_ANGLE                : new L.Icon({ iconUrl: ce4.util.url_static("/img/dw/direction_groundIndicator_minimal.png"),    iconSize: [279,279],iconAnchor: [139,139]})
};

// Marker Styles
ce4.leaflet.assets.styles = {
    DRAG_CONTROL      : { icon: ce4.leaflet.assets.icons.DRAG_CONTROL,
                          title: "Drag to move",
                          clickable: true,
                          draggable: true,
                          zIndexOffset: 100},
    TARGET_PENDING    : { icon: ce4.leaflet.assets.icons.TARGET_PENDING,
                          title: "Click for details",
                          clickable: true,
                          draggable: false},

    TARGET_RECENT     : { icon: ce4.leaflet.assets.icons.TARGET_RECENT,
                          title: "Click for details",
                          clickable: true,
                          draggable: false},

    TARGET_DONE       : { icon: ce4.leaflet.assets.icons.TARGET_DONE,
                          title: "Click for details",
                          clickable: true,
                          draggable: false},

    TARGET_ANGLE      : { icon: ce4.leaflet.assets.icons.TARGET_ANGLE,
                          clickable: false,
                          draggable: false,
                          zIndexOffset: -100}
};
