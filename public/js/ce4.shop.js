// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.shop contains the Shop model.
goog.provide("ce4.shop.Shop");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');

goog.require('ce4.product.AvailableProductCollection');
goog.require('ce4.product.PurchasedProductCollection');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.shop.Shop = function Shop(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.shop.Shop, lazy8.chips.Model);

/** @override */
ce4.shop.Shop.prototype.fields = {
    shop_id: new lazy8.chips.Field({id_field:true}),
    stripe_has_saved_card: new lazy8.chips.Field({required:true}),
    // An object holding card_type, card_last4, card_exp_month, card_exp_year and card_name
    // (e.g. 'Visa', '1', '2014', '4242', 'Homer Simpson') or null.
    // Check stripe_has_saved_card to determine if this has data.
    stripe_customer_data: new lazy8.chips.Field({required:true}),
    stripe_publishable_key: new lazy8.chips.Field({required:true}),
    urls: new lazy8.chips.Field({required:true})
};

ce4.shop.Shop.prototype.has_stripe_saved_card = function has_stripe_saved_card() {
    return this.stripe_has_saved_card === 1;
};

// Purchase the given product keys (an array with possibly repeated product key elements) using the provided
// credit card details.
// The save_card parameter is a boolean which indicates whether the card being charged should be saved for this
// user to be used in subsequent purchases.
// Optionally provide a success or failure callback.
// The failure callback takes a single argument which is an error message to display to the user.
// Purchased products will be returned via chips.
ce4.shop.Shop.prototype.stripePurchaseWithNewCard = function(product_keys, product_specifics_list, card, save_card, success, failure) {
    // Lazily inform the stripe.js library what our public publishable key is to avoid having the admin
    // map depend on stripe.js.
    Stripe.setPublishableKey(this.stripe_publishable_key);

    var shop = this;
    // Create the stripe token base on the provided card information.
    Stripe.card.createToken({
        number: card.number,
        cvc: card.cvc,
        exp_month: card.exp_month,
        exp_year: card.exp_year,
        name: card.name
    }, function stripeResponseHandler(status, response) {
        if (response.error) {
            // Return the stripe API error message if there was one.
            if (failure !== undefined) failure(response.error.message);
        } else {
            ce4.util.json_post({
                url: shop.urls.stripe_purchase_products,
                data: {
                    'product_keys': product_keys,
                    'product_specifics_list': product_specifics_list,
                    'stripe_token_id': response['id'],
                    'stripe_save_card': save_card
                },
                success: function(data) {
                    if (success !== undefined) success();
                },
                error: ce4.shop._stripe_error_handler("stripePurchaseWithNewCard", failure)
            });
        }
    });
};

// Purchase the given product keys (an array with possibly repeated product key elements) using the user's
// saved credit card.
// Optionally provide a success or failure callback.
// The failure callback takes a single argument which is an error message to display to the user.
// Purchased products will be returned via chips.
ce4.shop.Shop.prototype.stripePurchaseWithSavedCard = function(product_keys, product_specifics_list, success, failure) {
    var shop = this;
    ce4.util.json_post({
        url: shop.urls.stripe_purchase_products,
        data: {'product_keys': product_keys, 'product_specifics_list': product_specifics_list},
        success: function(data) {
            if (success !== undefined) success();
        },
        error: ce4.shop._stripe_error_handler("stripePurchaseWithSavedCard", failure)
    });
};

// Remove the user's Stripe saved credit card.
// Optionally provide a success or failure callback.
// The failure callback takes a single argument which is an error message to display to the user.
// shop.stripe_has_saved_card will be changed via chips.
ce4.shop.Shop.prototype.stripeRemoveSavedCard = function(success, failure) {
    ce4.util.json_post({
        url: this.urls.stripe_remove_saved_card,
        success: function(data) {
            if (success !== undefined) success();
        },
        error: ce4.shop._stripe_error_handler("stripeRemoveSavedCard", failure)
    });
};

ce4.shop._stripe_error_handler = function(func_name, failure) {
    return function(data, status, error) {
        var errorMsg = "Something went wrong, please reload the page and try again.";
        // If a request specific error message was returned, use that.
        if (data.responseJSON && data.responseJSON.errors) errorMsg = data.responseJSON.errors[0];
        console.error("Error in " + func_name + " : " + errorMsg);
        if (failure !== undefined) failure(errorMsg);
    };
};

/** @override */
ce4.shop.Shop.prototype.collections = {
    available_products: ce4.product.AvailableProductCollection,
    purchased_products: ce4.product.PurchasedProductCollection
};
