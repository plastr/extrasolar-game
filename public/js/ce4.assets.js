// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.assets provides a namespace for asset data (mostly icon URLs) to be shared between the
// server and client. The bulk of the contents of this namespace will be provided in game.html from
// the front/data/assets.json file. See that file to determine all that is available here, for example
// ce4.assets.species, ce4.assets.region, etc.
// It is still possible to provide functionality and additional data in this file, so long as the
// names added do not class with the top level names in assets.json.

goog.provide("ce4.assets");
goog.provide("ce4.assets.region");
goog.provide("ce4.assets.task");

// Notes from the asset data before it was moved to assets.json where there can be no comments.
    // REGION_ICON_ANIMAL          : "/img/region_icons/regionicon_animal.png", // TODO: PLACEHOLDER
    // REGION_ICON_ARTIFACT        : "/img/region_icons/regionicon_ques-yellow.png", // TODO: PLACEHOLDER
    // REGION_ICON_LANDMARK        : "/img/region_icons/regionicon_exc-blue.png", // TODO: PLACEHOLDER
    // REGION_ICON_MYSTERY         : "/img/region_icons/regionicon_ques-yellow.png", // TODO: PLACEHOLDER
    // REGION_ICON_RUINS           : "/img/region_icons/regionicon_exc-red.png", // TODO: PLACEHOLDER
    // REGION_ICON_RUINS_SIGNAL    : "/img/region_icons/regionicon_exc-yellow.png", // TODO: PLACEHOLDER
    // REGION_ICON_TRANSMISSION    : "/img/region_icons/regionicon_exc-yellow.png", // TODO: PLACEHOLDER
    // TODO "/img/region_icons/regionTASK_ICON_lander.png",
    //ce4.assets.region[ce4.region.styles.WAYPOINT]              = "/img/region_icons/button_quest.png"; // TODO: PLACEHOLDER
    //ce4.assets.region[ce4.region.styles.AUDIO]                 = "/img/region_icons/regionTASK_ICON_audio-purple.png"; // TODO: PLACEHOLDER
    //ce4.assets.region[ce4.region.styles.SURVEY]                = "/img/region_icons/button_quest3.png"; // TODO: PLACEHOLDER

    // Task icon notes:
    // DEFAULT                           : {active: "/img/task_icons/tasklist_tagUnknown.png",               done: "/img/task_icons/tasklist_tagUnknown-done.png"}, // TODO: PLACEHOLDER
