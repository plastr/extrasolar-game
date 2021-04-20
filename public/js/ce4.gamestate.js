// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.gamestate namespace holds all parsed server side data, including the Model/Collection hierarchy.
goog.provide('ce4.gamestate');

// This holds the ce4.user.User instance for the currently logged in user.
// It will be populated when the gamestate is first parsed from the server.
ce4.gamestate.user = null;

// This holds various data and configuration provided by the server in the initial gamestate data.
ce4.gamestate.config = null;

// This holds various URLs provided by the server in the initial gamestate data.
ce4.gamestate.urls = null;
