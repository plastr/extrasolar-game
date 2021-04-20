// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.invite contains the Invite model.
goog.provide("ce4.invite.Invite");
goog.provide("ce4.invite.InviteCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util.TimestampDateField');
goog.require('ce4.gamestate');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.invite.Invite = function Invite(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.invite.Invite, lazy8.chips.Model);

/** @override */
ce4.invite.Invite.prototype.fields = {
    invite_id: new lazy8.chips.Field({id_field:true}),
    sender_id: new lazy8.chips.Field({required:true}),
    recipient_id: new lazy8.chips.Field({required:true}),
    recipient_email: new lazy8.chips.Field({required:true}),
    recipient_last_name: new lazy8.chips.Field({required:true}),
    recipient_first_name: new lazy8.chips.Field({required:true}),
    sent_at: new ce4.util.TimestampDateField({required:true}),
    accepted_at: new ce4.util.TimestampDateField({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

ce4.invite.create_invite = function(recipient_email, recipient_first_name, recipient_last_name, recipient_message, cbSuccess, cbFailure) {
    // Issue the request to the server to create a new invite. The response will comeback
    // via a chip which will add the invite to the invitations collection.
    ce4.util.json_post({
        url: ce4.gamestate.urls.create_invite,
        data: {
            'recipient_email':recipient_email,
            'recipient_first_name':recipient_first_name,
            'recipient_last_name':recipient_last_name,
            'recipient_message':recipient_message
        },
        success: cbSuccess,
        error: cbFailure
    });
};

// Returns true if this invitation has been accepted by its recipient.
ce4.invite.Invite.prototype.was_accepted = function() {
    return this.recipient_id !== null;
};

// Returns a nicely formatted accepted string
ce4.invite.Invite.prototype.was_accepted_nice = function() {
    return this.was_accepted() ? "Yes" : "No";
};

// Returns a nicely formatted date
ce4.invite.Invite.prototype.sent_at_date_nice = function() {
    return (new Date(this.sent_at_date())).toDateString();
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.invite.InviteCollection = function InviteCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.invite.InviteCollection, lazy8.chips.Collection);

/** @override */
ce4.invite.InviteCollection.prototype.model_constructor = ce4.invite.Invite;
