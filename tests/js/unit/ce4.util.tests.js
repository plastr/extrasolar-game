function ce4_util_tests() {
    goog.require('ce4.util');
    goog.require('ce4.planet');
    goog.require('xri.validation');

    module("Timestamp Serialization");

    test("ce4.util.from_ts", function() {
        var dateobj = ce4.util.from_ts(1280194362);
        ok(dateobj, "checking whether Date was created");
        equals(dateobj.toUTCString(), "Tue, 27 Jul 2010 01:32:42 GMT", 
           "parsed date");
        equals(dateobj.getMilliseconds(), 0, "parsed milliseconds");
        dateobj = ce4.util.from_ts(1280194362.123);
        equals(dateobj.toUTCString(), "Tue, 27 Jul 2010 01:32:42 GMT",
           "parsed date");
        equals(dateobj.getMilliseconds(), 0, "parsed milliseconds");
    });
    
    test("ce4.util.to_ts", function() {
        var ts = ce4.util.to_ts(new Date("Tue, 27 Jul 2010 01:32:42 GMT"));
        ok(ts, "checking whether timestamp was created");
        equals(ts, "1280194362", "serialized date");
        ts = ce4.util.to_ts(new Date(1280194362123));
        equals(ts, "1280194362", "serialized date with milliseconds");
    });

    module("Miscellaneous Utilities");

    test("ce4.util.is_chip_time_newer", function() {
        var last_seen_chip_time = "1352757445888589";
        var usec = "1352757445889000";
        equals(true, ce4.util.is_chip_time_newer(usec, last_seen_chip_time));
        equals(false, ce4.util.is_chip_time_newer(last_seen_chip_time, usec));
        equals(false, ce4.util.is_chip_time_newer(usec, usec));

        equals(false, ce4.util.is_chip_time_newer("123", "456"));
        equals(true, ce4.util.is_chip_time_newer("456", "123"));
        equals(false, ce4.util.is_chip_time_newer("02", "20"));
        equals(false, ce4.util.is_chip_time_newer("2", "20"));
        equals(true, ce4.util.is_chip_time_newer("20", "2"));
    });

    test("ce4.util.utc_now_in_ms", function() {
        // Fake the data we would normally have from the gamestate.
        ce4.util.server_time_diff = 123;
        var now = ce4.util.utc_now_in_ms();
        // Make sure the last three digits are 0.
        equals(now % 1000, 0);
    });

    test("ce4.util.date_sans_millis", function() {
        var date = ce4.util.date_sans_millis(1280194362123);
        // Make sure the millisecond value is 0.
        equals(date.getMilliseconds(), 0);
    });

    test("ce4.util.filter", function() {
        var array = [0, 1, 2, 3, 4, 5, 6];
        var filtered = ce4.util.filter(array, function(element) {
            return element < 3;
        });
        equal(filtered.length, 3);
    });

    test("ce4.util.sortBy", function() {
        var array = [{f1:2}, {f1:3}, {f1:0}, {f1:1}, {f1:5}, {f1:4}];
        ce4.util.sortBy(array, 'f1');
        for (var i = 0; i < array.length; i++) {
            equal(array[i].f1, i);
        }
        ce4.util.sortBy(array, 'f1', true);
        expected = (array.length - 1);
        for (i = 0; i < array.length; i++) {
            equal(array[i].f1, expected--);
        }
    });

    module("ajaxOnQueue");

    asyncTest("ce4.util.ajaxOnQueue", 1, function() {
        ce4.util.ajaxOnQueue(success_request);
        setTimeout(function() { start(); }, 200);
    });

    asyncTest("ce4.util.ajaxOnQueue multiple", 2, function() {
        ce4.util.ajaxOnQueue(success_request);
        ce4.util.ajaxOnQueue(success_request);
        setTimeout(function() { start(); }, 400);
    });

    asyncTest("ce4.util.ajaxOnQueue failure", 1, function() {
        ce4.util.ajaxOnQueue(failing_request);
        // This request in the queue should be aborted and removed
        // when the first request fails so we should never see its assertions.
        ce4.util.ajaxOnQueue(success_request);
        setTimeout(function() { start(); }, 400);
    });

    module("GMT <-> Eri Conversion");

    test("ce4.planet.date_to_eris", function() {
        var date = new Date("Tue, 27 Jul 2010 01:32:42 GMT");
        var eris = ce4.planet.date_to_eris(date);
        ok(eris, "eris created");
        equals(eris, 87.94411764705882, "eris value");
    });

    module("Validation Regular Expressions");

    // Keep in sync with patterns.py doctests.
    test("xri.validation.isValidEmail", function() {
        equals(true,  xri.validation.isValidEmail('test@example.com'));
        equals(true,  xri.validation.isValidEmail('test.this@long.domain.example.me'));
        equals(true,  xri.validation.isValidEmail('test.gmail.style+tag@gmail.com'));
        equals(false, xri.validation.isValidEmail('invalid@domain'));
        equals(false, xri.validation.isValidEmail('invalid&domain.com'));
        equals(false, xri.validation.isValidEmail('test@.domain.com'));
        equals(false, xri.validation.isValidEmail('test@domain..com'));
    });

    // These are $.ajax settings for use by the ce4.util.ajaxOnQueue tests.
    // This AJAX request is expected to succeed (200)
    var success_request = {
        url: '/',
        type: 'GET',
        success: function() {
            ok(true, "Queued request success.");
        },
        error: function() {
            ok(false, "Queued request failure.");
        }
    };
    // This AJAX request is expected to fail (404)
    var failing_request = {
        url: '/bogus',
        type: 'GET',
        success: function() {
            ok(false, "Queued request should not succeed.");
        },
        error: function() {
            ok(true, "Queued request should fail.");
        }
    };
}
