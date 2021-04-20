// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.util contains various useful utilities.
goog.provide("ce4.util");
goog.provide("ce4.util.EpochDateField");
goog.provide("ce4.util.TimestampDateField");

goog.require('goog.structs');

goog.require('lazy8.chips.Field');

// Holds the time difference (in seconds) that should be added to Date().getTime()
// to get the server's UTC time. Generated from the initial gamestate data. Must be
// set to a real value before ce4.util.utc_now_in_ms is called.
ce4.util.server_time_diff = null;
ce4.util.ops_server = null;

/** Generically useful utilites. */
ce4.util.assert = function(condition) {
    if (!condition) {
        throw new Error("ASSERT");
    }
};

/**
 * Calls a function for each value in a collection. The function takes
 * three arguments; the value, the key and the collection.
 * Use this to safely iterate over Arrays and Objects.
 * NOTE: Currently just a wrapper around goog.structs.forEach.
 *
 * @param {Object} collection The collection-like object.
 * @param {Function} func The function to call for every value. This function takes
 *     3 arguments (the value, the key or undefined if the collection has no
 *     notion of keys, and the collection) and the return value is irrelevant.
 * @param {Object=} opt_this The object to be used as the value of 'this'
 *     within {@code func}.
 */
ce4.util.forEach = function(collection, func, opt_this) {
    return goog.structs.forEach(collection, func, opt_this);
};

/**
 * Calls a function for every value in the collection (Array, Object, etc). When a call
 * returns true, adds the value to a new collection (Array is returned by default).
 * NOTE: Currently just a wrapper around goog.structs.filter.
 *
 * @param {Object} collection The collection-like object. Might be an Array, an Object,
       or a goog.struct or other Google collection.
 * @param {Function} func The function to call for every value. This function takes
 *     3 arguments (the value, the key or undefined if the collection has no
 *     notion of keys, and the collection) and should return a Boolean. If the
 *     return value is true the value is added to the result collection. If it
 *     is false the value is not included.
 * @param {Object=} opt_this The object to be used as the value of 'this'
 *     within {@code func}.
 * @return {!Object|!Array} A new collection where the passed values are
 *     present. If collection is a key-less collection an array is returned.  If
 *     collection has keys and values a plain old JS object is returned.
 */
ce4.util.filter = function(collection, func, opt_this) {
    return goog.structs.filter(collection, func, opt_this);
};

/**
 * Sort the supplied Array of Objects and return it as an Array in ascending order
 * using the supplied field/property of the Objects contained within.
 * Optionally, opt_descend can be set to true and the array will be sorted in descending
 * order. Additionally, opt_compareFn can be defined as the comparison function. If this is
 * defined, opt_descend will be ignored. If no opt_compareFn is specified, elements are
 * compared using the default comparison function, which compares the elements using the
 * built in < and > operators.
 *
 * This sort is not guaranteed to be stable.
 *
 * Description based on goog.array.sort.
 *
 * @param {Array} Array The Array to sort.
 * @param {string} field The field/property of the Objects to sort on.
 * @param {boolean=} opt_descend If true, sort the array in descending order.
 * @param {Function=} opt_compareFn Optional comparison function by which the
 *     array is to be ordered. Should take 2 Object arguments to compare, and return a
 *     negative number, zero, or a positive number depending on whether the
 *     first argument is less than, equal to, or greater than the second.
 */
ce4.util.sortBy = function(array, field, opt_descend, opt_compareFn) {
    if (array.sort === undefined) {
        throw new TypeError("Array to sort does not have a sort() function.");
    }
    var compareFn;
    // If the compareFn was passed in, use that.
    if (opt_compareFn !== undefined) {
        compareFn = opt_compareFn;
    // Otherwise use the default descend compare if requested.
    } else if (opt_descend === true) {
        compareFn = function(a, b) {
            return a[field] < b[field] ? 1 : a[field] > b[field] ? -1 : 0;
        };
    // Or fallback on the default ascending compare.
    } else {
        compareFn = function(a, b) {
            return a[field] > b[field] ? 1 : a[field] < b[field] ? -1 : 0;
        };
    }
    array.sort(compareFn);
    return array;
};

/*
 * Trim spaces off the beginning and end of a string.
 */
ce4.util.trim = function (str) {
    return str.replace(/^\s\s*/, '').replace(/\s\s*$/, '');
}

/*
 * Pad a Number (assumed to be an integer) with the given length of 0's.
 */
ce4.util.pad_int = function(number, length) {
    var result = '' + number;
    while (result.length < length) {
        result = '0' + result;
    }
    return result;
};

/*
 * Given a min and a max value, returns a no-args function that returns an
 * series of exponential backoff delays, with substantial randomness.
 * E.g.:
 *   var eb = exponential_backoff(1, 10);
 *   console.log(eb());     => 1.5
 *   console.log(eb());     => 2.4
 *   console.log(eb());     => 3.8
 *   console.log(eb());     => 9.1
 *   console.log(eb());     => 8.2
 *
 * The values are not guaranteed to be monotonically increasing, only that they
 * will be between the min and max.
 */
ce4.util.exponential_backoff = function(bmin, bmax) {
    var delay = bmin;
    return function() {
        delay = Math.min(delay * 2, bmax);
        return bmin + (delay - bmin) * Math.random();
    };
};

// Issue an AJAX POST with a JSON payload which will send last_seen_chips_time and be able to handle
// any chips in the response. This function can handle the same options as jQuery $.ajax().
// Example usage:
// ce4.util.json_post({
//     url: '/handler',
//     data: {'key': 'value'},
//     success: function(data, textStatus, jqXHR) {},
//     error: function(jqXHR, textStatus, errorThrown) {}
// });
ce4.util.json_post = function(options) {
    options.type = 'POST';
    options.contentType = 'application/json';
    // last_seen_chip_time will be inserted into options when this request is popped off
    // queue and runs so it has the most current value of last_seen_chip_time
    ce4.util.json_chips_request(options);
};

// Issue an AJAX GET which will send last_seen_chips_time as a query parameter and be able to handle
// any chips in the response. This function can handle the same options as jQuery $.ajax().
ce4.util.json_get = function(options) {
    options.type = 'GET';
    options.cache = false;
    // last_seen_chip_time will be inserted into options when this request is popped off
    // queue and runs so it has the most current value of last_seen_chip_time
    ce4.util.json_chips_request(options);
};

// A helper which wraps the jQuery .ajax() function. All requests will have the last_seen_chip_time
// sent as a request parameter (for GET as a query parameter, all others in the JSON body) and all
// successful requests will have any chips data processed before executing any subsequent success handlers.
ce4.util.json_chips_request = function(options) {
    // Set some default values. If no success callbacks were provided, default to it being a list.
    var defaults = { dataType: "json", success: [], error: [] };
    var settings = $.extend({}, defaults, options);

    // If only a single success callback was provided, turn it into an array so the chips
    // success or error handler can be inserted first in the callbacks list.
    if(!$.isArray(settings.success))
        settings.success = [settings.success];
    if(!$.isArray(settings.error))
        settings.error = [settings.error];
    // Insert a success handler at the start of the success handler list which processes any
    // chips data returned by the request.
    settings.success.unshift(function chips_success(data) {
        ce4.chips.process_chips(data);
    });
    // Insert an error handler at the start of the success handler list which processes any
    // chips data returned by the request and logs the error message.
    // NOTE: Currently, chips do not come back with errors usually.
    settings.error.unshift(function chips_error(data, status, error) {
        // NOTE: This is not converted from JSON string to real JS object automatically.
        // Is this a jQuery 1.5 issue or do we have to deserialize this ourselves?
        // data['responseText']['errors']
        ce4.chips.process_chips(data);
    });

    // When a queued request is popped off the queue and ran, insert the current
    // last_seen_chip_time just before the request is run.
    add_last_seen_chip_time = function(ajaxOpts) {
        if (ajaxOpts.type === 'POST') {
            if (ajaxOpts.data === undefined) {
                ajaxOpts.data = {};
            }
            ce4.chips.insert_last_seen_chip_time(ajaxOpts.data);
            ajaxOpts.data = JSON.stringify(ajaxOpts.data);
        } else if (ajaxOpts.type === 'GET') {
            ajaxOpts.data = $.extend({}, ajaxOpts.data, ce4.chips.last_seen_chip_time_query_param());
        }
    }

    // Add the AJAX request to the queue and run if the only item.
    ce4.util.ajaxOnQueue(settings, add_last_seen_chip_time);
};

ce4.util._ajaxQueue = $({});
// Run all requests run through json_chips_request on a serial queue.
// Only one request is run at a time, but still asynchronously so the UI thread is not blocked.
// If any request fails, the queue is cleared and all requests in the queue will not run.
// @param {Object} ajaxOpts The object of options compatible with the jQuery.ajax function.
// @param {Function=} opt_modify_options An optional function to process the ajaxOpts when they are
//   popped off the queue just before the request is run.
//
// Modified from jQuery.ajaxQueue
// (c) 2011 Corey Frang
// Dual licensed under the MIT and GPL licenses.
// http://gnarf.net/2011/06/21/jquery-ajaxqueue/
ce4.util.ajaxOnQueue = function(ajaxOpts, opt_modify_options) {
    var jqXHR,
        dfd = $.Deferred(),
        promise = dfd.promise();

    // Add the ajax request to the queue.
    ce4.util._ajaxQueue.queue(doRequest);

    // Add the abort method to the deferred promise. The promise is acting as a proxy object
    // for the jquery ajax object so this is intercepting the call to $.ajax.abort() essentially.
    // If the actual jquery xhr object is aborted by some other code, this code
    // will also be triggered and remove that request from the queue.
    promise.abort = function(statusText) {
        // Proxy abort to the jqXHR if it is active
        if (jqXHR) {
            return jqXHR.abort( statusText );
        }

        // If there wasn't already a jqXHR we need to remove from queue.
        var queue = ce4.util._ajaxQueue.queue(),
            index = $.inArray(doRequest, queue);
        if (index > -1) {
            queue.splice(index, 1);
        }

        // And then reject the deferred.
        dfd.rejectWith(ajaxOpts.context || ajaxOpts, [promise, statusText, ""]);
        return promise;
    };

    // If this request fails, clear the remaining requests from the queue
    // as these are chip related requests and it is somewhat unpredictable what will happen
    // if the next request fires if this one failed. E.g. creating a target fails and the
    // next target is in the queue.
    promise.fail(function() {
        ce4.util._ajaxQueue.clearQueue();
    });

    // Run the actual ajax request. The next item is run when this one finishes.
    function doRequest(next) {
        if (opt_modify_options !== undefined) {
            opt_modify_options(ajaxOpts);
        }
        jqXHR = $.ajax(ajaxOpts)
                 .done(dfd.resolve)
                 .fail(dfd.reject)
                 .then(next, next);
    }
    return promise;
};

/**
 * A Field subclass which is intended to wrap time values in the gamestate which represent seconds
 * that have elapsed since the user epoch. Note that these conversions are performed every time these
 * computed methods are called, meaning is user.epoch changes, the returned values are still correct.
 * Any field wrapped by this object will have added to its Model object the following two computed field methods:
 *    'field_name'_ms: Provide the number of milliseconds that have elapsed since the 1970 epoch
                       based on the value of the field (seconds since user epoch).
 *    'field_name'_date: Provide a Date object which represents the 'real' moment in wall-clock time
                         that this field value represents (seconds since user epoch).
 *
 */
ce4.util.EpochDateField = function EpochDateField(field_spec) {
    lazy8.chips.Field.call(this, field_spec);
};
goog.inherits(ce4.util.EpochDateField, lazy8.chips.Field);

/** @override */
ce4.util.EpochDateField.prototype.create_computed_field = function(model, field_name) {
   model[field_name + "_date"] = function() {
       if (this[field_name] === undefined || this[field_name] === null) {
           return this[field_name];
       }
       return ce4.util.from_ts(ce4.gamestate.user.epoch + this[field_name]);
   };
   model[field_name + "_ms"] = function() {
       if (this[field_name] === undefined || this[field_name] === null) {
           return this[field_name];
       }
       return (ce4.gamestate.user.epoch + this[field_name]) * 1000;
   };
};

/**
 * A Field subclass which is intended to wrap time values in the gamestate which represent seconds
 * that have elapsed since the 1970 user epoch.
 * Any field wrapped by this object will have added to its Model object the following computed field method:
 *    'field_name'_date: Provide a Date object which represents the 'real' moment in wall-clock time
                         that this field value represents.
 *
 */
ce4.util.TimestampDateField = function TimestampDateField(field_spec) {
    lazy8.chips.Field.call(this, field_spec);
};
goog.inherits(ce4.util.TimestampDateField, lazy8.chips.Field);

/** @override */
ce4.util.TimestampDateField.prototype.create_computed_field = function(model, field_name) {
   model[field_name + "_date"] = function() {
       if (this[field_name] === undefined || this[field_name] === null) {
           return this[field_name];
       }
       return ce4.util.from_ts(this[field_name]);
   };
};

// Get the current UTC time in milliseconds, synced with the server.
ce4.util.utc_now_in_ms = function() {
    var now_sync = new Date().getTime() + ce4.util.server_time_diff;
    now_sync -= now_sync % 1000;
    return now_sync;
};

// Given a POSIX time (millseconds), return a date object with milliseconds stripped off.
ce4.util.date_sans_millis = function(millis) {
    return new Date(millis - (millis%1000));
};

/**
 * Returns a javascript Date object parsed from a string, excluding milliseconds.
 */
ce4.util.from_ts = function(val) {
    var ival = parseInt(val);
    var millis = ival * 1000;
    return new Date(millis);
};

/**
 *  Serializes a Date object to a string.
 */
ce4.util.to_ts = function(val) {
    var millis = val.getTime();
    return '' + Math.floor(millis/1000);
};

// Returns True if the first chip.time is newer than the second value.
ce4.util.is_chip_time_newer = function(chip_time, last_seen_chip_time) {
    // If the strings are identical length, then the Javascript > comparison will work correctly
    // as the the bigger number will be 'newer'/bigger in lexical order.
    // Otherwise whichever string is longer is bigger/newer.
    if (chip_time.length === last_seen_chip_time.length)
        return (chip_time > last_seen_chip_time);
    else if (chip_time.length > last_seen_chip_time.length)
        return true;
    else
        return false;
};

// Compute the elapsed time and return it as a friendly string.
// e.g. "7 minutes ago" or "yesterday"
ce4.util.format_time_since = function(millis) {
    var now = ce4.util.utc_now_in_ms();
    var time_in_minutes = (now - millis)/60000;
    if (time_in_minutes < 1.0)  return 'just now';
    if (time_in_minutes < 1.5)  return 'one minute ago';
    if (time_in_minutes < 60.5) return '' + Math.floor(time_in_minutes+0.5) + ' minutes ago';
    var time_in_hours = (now - millis)/3600000;
    if (time_in_hours < 1.5)    return 'one hour ago';
    if (time_in_hours < 24.5)   return '' + Math.floor(time_in_hours+0.5) + ' hours ago';
    var time_in_days = (now - millis)/86400000;
    if (time_in_days < 2.0)     return 'yesterday';
    return '' + Math.floor(time_in_days) + ' days ago';
};

// Compute the remaining time and return it as a friendly string.
// e.g. "7 minutes" or "tomorrow"
ce4.util.format_time_until = function(millis) {
    var now = ce4.util.utc_now_in_ms();
    var time_in_minutes = (millis - now)/60000;
    if (time_in_minutes < 1.0)  return 'less than 1 minute';
    if (time_in_minutes < 1.5)  return 'one minute';
    if (time_in_minutes < 60.5) return '' + Math.floor(time_in_minutes+0.5) + ' minutes';
    var time_in_hours = (millis - now)/3600000;
    if (time_in_hours < 1.5)    return 'one hour';
    if (time_in_hours < 24.5)   return '' + Math.floor(time_in_hours+0.5) + ' hours';
    var time_in_days = (millis - now)/86400000;
    if (time_in_days < 2.0)     return 'tomorrow';
    return '' + Math.floor(time_in_days) + ' days';
};

// Format the time delta as a friendly string.
// e.g. "7 minutes" or "12 days"
ce4.util.format_time_approx = function(millis) {
    var time_in_minutes = millis/60000;
    if (time_in_minutes < 1.0)  return 'less than 1 minute';
    if (time_in_minutes < 1.5)  return 'one minute';
    if (time_in_minutes < 60.5) return '' + Math.floor(time_in_minutes+0.5) + ' minutes';
    var time_in_hours = millis/3600000;
    if (time_in_hours < 1.5)    return 'one hour';
    if (time_in_hours < 24.5)   return '' + Math.floor(time_in_hours+0.5) + ' hours';
    var time_in_days = millis/86400000;
    if (time_in_days < 2.0)     return 'one day';
    return '' + Math.floor(time_in_days) + ' days';
};

// Format the selected time delay as "2h 12m".
ce4.util.format_time_hm = function(ms)
{
    var hours = ms/(60*60*1000);
    var strHours = Math.floor(hours).toString();
    var minutes = Math.floor((hours-Math.floor(hours))*60);
    var strMinutes = minutes.toString();
    if (minutes < 10)
        strMinutes = '0'+strMinutes;
    return strHours + 'h ' + strMinutes + 'm';
};

// Convery a Number in degrees in radians.
ce4.util.toRadians = function(degrees) {
    return degrees * Math.PI / 180;
};

/**
 *  Convert a yaw angle (in radians) to a compass direction
 */
ce4.util.yaw_to_compass = function(val) {
    // Convert the input (in radians) to an angle (in degrees) between 0 and 360
    while (val < 0.0)
        val += 2.0*Math.PI;
    while (val > 2.0*Math.PI)
        val -= 2.0*Math.PI;
    var angle = val * 180.0/Math.PI;

    if (angle < 11.25)       return 'N';
    else if (angle < 33.75)  return 'NNE';
    else if (angle < 56.25)  return 'NE';
    else if (angle < 78.75)  return 'ENE';
    else if (angle < 101.25) return 'E';
    else if (angle < 123.75) return 'ESE';
    else if (angle < 146.25) return 'SE';
    else if (angle < 168.75) return 'SSE';
    else if (angle < 191.25) return 'S';
    else if (angle < 213.75) return 'SSW';
    else if (angle < 236.25) return 'SW';
    else if (angle < 258.75) return 'WSW';
    else if (angle < 281.25) return 'W';
    else if (angle < 303.75) return 'WNW';
    else if (angle < 326.25) return 'NW';
    else if (angle < 348.75) return 'NNW';
    else                     return 'N';
};


// Used to toggle or set DIVs to hidden or visible
// sID:     The tab group ID, 'notab' is used if grouping is not needed (this feature is useful for tabs, only one can be selected)
// szDivID: id of the DIV to toggle or set
// iState:  1 visible, 0 hidden, 2 toggle
// disVal:  optional string to set the display value to, "inline", "block", "inline-block", etc.
ce4.util.toggleView = function(sID, szDivID, iState, disVal)
{
    if (ce4.util.toggleView.lastTab === undefined) ce4.util.toggleView.lastTab = [];

    if (document.getElementById)
    {
        if (sID != 'notab' && ce4.util.toggleView.lastTab[sID] && document.getElementById( ce4.util.toggleView.lastTab[sID] ))
        {
            document.getElementById( ce4.util.toggleView.lastTab[sID] ).style.display = "none";
        }
        ce4.util.toggleView.lastTab[sID] = szDivID;
        var obj = document.getElementById( szDivID );
        obj.style.display = ((iState == 2) && obj.style.display == "none" || iState == 1) ? (disVal || "inline") : "none";
    }
    return false;
};


// Returns true if two angles (a, b) are within error of each other
// In radians
ce4.util.angle_closeness = function(a, b, error) {
    if(Math.abs(a - b) < error) {
        return true;
    } else {
        if (a < 0) {
            a += Math.PI * 2;
        } else if (b < 0) {
            b += Math.PI * 2;
        }
        return Math.abs(a - b) < error;
    }
};

// Constructs a URL for the message tab
ce4.util.url_message = function(message_id) {
    return "#message," + message_id;
}

// Constructs a URL for the tasks tab
ce4.util.url_task= function(mission_id) {
    return "#task," + mission_id;
}

// Constructs a URL for the map tab
ce4.util.url_map = function(p) {
    var url_params = "";

    // Add each parameter to the url
    if(p.id)            url_params += p.id;
    if(p.target)        url_params += ((url_params !== "") ? "&" : "") + "t=" + p.target;
    if(p.region)        url_params += ((url_params !== "") ? "&" : "") + "r=" + p.region;
    if(p.lat && p.lng)  url_params += ((url_params !== "") ? "&" : "") + "lat=" + p.lat + "&lng=" + p.lng;

    // return the url
    return "#map," + url_params;
};

// Constructs a URL for the catalog tab
ce4.util.url_catalog = function(p) {
    var url_params = "";

    // Add each parameter to the url
    if(p.id)            url_params += p.id;

    // return the url
    return "#catalog," + url_params;
};

//------------------------------------------------------------------------------
// TODO: should consider replacing calls to this with url_full
// Constructs the full url
ce4.util.url_base = function (path) {
   return location.protocol + "//" + location.host + (path || "/");
};

//------------------------------------------------------------------------------
// Only accept commonly trusted protocols:
// Only data-image URLs are accepted, Exotic flavours (escaped slash,
// html-entitied characters) are not supported to keep the function fast
// ref: http://stackoverflow.com/questions/7544550/javascript-regex-to-change-all-relative-urls-to-absolute
ce4.util.url_full = function (url){
  if(/^(https?|file|ftps?|mailto|javascript|data:image\/[^;]{2,9};):/i.test(url))
         return url; //Url is already absolute

    var base_url = location.href.match(/^(.+)\/?(?:#.+)?$/)[0]+"/";
    if(url.substring(0,2) == "//")
        return location.protocol + url;
    else if(url.charAt(0) == "/")
        return location.protocol + "//" + location.host + url;
    else if(url.substring(0,2) == "./")
        url = "." + url;
    else if(/^\s*$/.test(url))
        return ""; //Empty = Return nothing
    else url = "../" + url;

    url = base_url + url;
    var i=0
    while(/\/\.\.\//.test(url = url.replace(/[^\/]+\/+\.\.\//g,""))) {};

    /* Escape certain characters to prevent XSS */
    url = url.replace(/\.$/,"").replace(/\/\./g,"").replace(/"/g,"%22")
            .replace(/'/g,"%27").replace(/</g,"%3C").replace(/>/g,"%3E");
    return url;
};

//------------------------------------------------------------------------------
// Given a path to a resource, return the path that's appropriate for the platform.
ce4.util.url_static = function(path) {
    // If this is a native app, paths starting with '/' can cause problems.
    // TODO: Ideally, we would create full path to these resources, but for now,
    // just strip off the leading '/' to make the path relative from the current location.
    if (ce4.util.is_native() && path.charAt(0) == '/') {
        return path.substring(1);
    }
    return path;
};

//------------------------------------------------------------------------------
// For API calls made via ajax requests, the native app must use the full path.
ce4.util.url_api = function(path) {
    // If this is the native app, we can't use relative URLs for API calls.
    if (ce4.util.is_native()) {
        // We expect that ops_server does not end with a slash.
        if (path.charAt(0) == '/') {
            return ce4.util.ops_server + path;
        }
        else {
            return ce4.util.ops_server + '/ops/' + path;
        }
    }
    return path;
};

//------------------------------------------------------------------------------
// Return true if this is running as a native app rather than in a browser.
ce4.util.is_native = function() {
    return (typeof window.is_native !== 'undefined' && window.is_native)
}

//------------------------------------------------------------------------------
// Selects contained checkbox when a table row is clicked
ce4.util.latLngToArray = function(latLng) {
    return [latLng.lat, latLng.lng];
};

//------------------------------------------------------------------------------
// Selects contained checkbox when a table row is clicked
ce4.util.selectRow = function(event) {
    if(!$(event.target).is('input:checkbox')) {
        $(this.getElementsByTagName('input')[0]).trigger('click');
    }
};

//------------------------------------------------------------------------------
// jQuery preload images
$.fn.preload = function() {
    this.each(function(){
        $('<img/>')[0].src = this;
    });
};

//------------------------------------------------------------------------------
// IE8 Support for lack of console
if (typeof console == "undefined") { console = {log: function() {}}; }

//------------------------------------------------------------------------------
// IE8 Support for lack of Array forEach
if (!Array.prototype.forEach) {
    Array.prototype.forEach = function (fn, scope) {
        'use strict';
        var i, len;
        for (i = 0, len = this.length; i < len; ++i) {
            if (i in this) {
                fn.call(scope, this[i], i, this);
            }
        }
    };
}

//------------------------------------------------------------------------------
// Return a nicely formatted string of a Date object. "H:MM AM/PM on Mmm D"
ce4.util.localTimeAsStr = function(date)
{
    var months = new Array("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec");
    m = date.getMonth();
    hrs = date.getHours();
    min = date.getMinutes();

    // Format the hours
    ampm = (hrs < 12) ? " AM" : " PM";
    if (hrs === 0) hrs = 12;
    if (hrs > 12)  hrs -= 12;

    // Pad the minutes with an extra 0 if necessary
    if (min < 10)  min = "0" + min;

    return hrs + ":" + min + ampm + ", " + months[m] + " " + date.getDate();
};
