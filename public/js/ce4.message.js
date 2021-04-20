// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.message contains the Message model.
goog.provide("ce4.message.Message");
goog.provide("ce4.message.MessageCollection");
goog.provide("ce4.message.icons");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.assets');
goog.require('ce4.util.EpochDateField');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.message.Message = function Message(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.message.Message, lazy8.chips.Model);

/** @override */
ce4.message.Message.prototype.fields = {
    message_id: new lazy8.chips.Field({id_field:true}),
    msg_type: new lazy8.chips.Field({required:true}),
    style: new lazy8.chips.Field({required:true}),
    sender: new lazy8.chips.Field({required:true}),
    sender_key: new lazy8.chips.Field({required:true}),
    subject: new lazy8.chips.Field({required:true}),
    read_at: new ce4.util.EpochDateField({required:true}),
    sent_at: new ce4.util.EpochDateField({required:true}),
    locked: new lazy8.chips.Field({required:true}),
    needs_password: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

// Check if this message has been read by seeing if the read_at field is undefined.
ce4.message.Message.prototype.is_read = function is_read() {
    return (this.read_at !== null);
};

// Alias for is_read
ce4.message.Message.prototype.hasBeenViewed = ce4.message.Message.prototype.is_read;

// Check if this message is currently locked.
ce4.message.Message.prototype.is_locked = function is_locked() {
    return (this.locked !== 0);
};

ce4.message.Message.prototype.format_sent_at = function() {
    return ce4.util.format_time_since(this.sent_at_ms());
};

ce4.message.Message.prototype.icon_html = function(message_icon) {
    var icon = ce4.assets.message[message_icon];
    if (icon == undefined) {
        console.log("Unknown message_icon " + message_icon);
        return '';
    }
    return '<img src="' + icon.url + '" width="' + icon.width + '" height="' + icon.height + '"> ';
};

// Note: This logic should match the corresponding routine in message.py.
ce4.message.Message.prototype.icon = function() {
    if (this.style === "LIVE_CALL" && this.is_locked()) {
        return this.icon_html("CALL_LOCKED");
    } else if (this.style === "LIVE_CALL") {
        return this.icon_html("CALL_UNLOCKED");
    } else if (this.style === "LOCKED_DOCS" && this.is_locked()) {
        return this.icon_html("LOCKED");
    } else if(this.style === "LOCKED_DOCS") {
        return this.icon_html("UNLOCKED");
    } else if (this.style === "PASSWORD" && this.is_locked()) {
        return this.icon_html("LOCKED");
    } else if(this.style === "PASSWORD") {
        return this.icon_html("UNLOCKED");
    } else if(this.style === "VIDEO") {
        return this.icon_html("VIDEO");
    } else if(this.style === "AUDIO") {
        return this.icon_html("AUDIO");
    } else if(this.style === "ATTACHMENT") {
        return this.icon_html("ATTACHMENT");
    }
    return '';
};

ce4.message.Message.prototype.message_url = function() {
    return "#message," + this.message_id;
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.message.MessageCollection = function MessageCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.message.MessageCollection, lazy8.chips.Collection);

/** @override */
ce4.message.MessageCollection.prototype.model_constructor = ce4.message.Message;

// Return the first Message object for the given msg_type if it exists in the collection.
ce4.message.MessageCollection.prototype.by_type = function(msg_type) {
    return this.find(function(message) {
        return message.msg_type === msg_type;
    });
};
