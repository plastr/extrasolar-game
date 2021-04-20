// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.product contains the AvailableProduct and PurchasedProduct models.
goog.provide("ce4.product.AvailableProduct");
goog.provide("ce4.product.PurchasedProduct");
goog.provide("ce4.product.AvailableProductCollection");
goog.provide("ce4.product.PurchasedProductCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util.EpochDateField');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.product.AvailableProduct = function AvailableProduct(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.product.AvailableProduct, lazy8.chips.Model);

/** @override */
ce4.product.AvailableProduct.prototype.fields = {
    product_key: new lazy8.chips.Field({id_field:true}),
    name: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    price: new lazy8.chips.Field({required:true}),
    currency: new lazy8.chips.Field({required:true}),
    price_display: new lazy8.chips.Field({required:true}),
    initial_price: new lazy8.chips.Field({required:true}),
    initial_price_display: new lazy8.chips.Field({required:true}),
    icon: new lazy8.chips.Field({required:true}),
    sort: new lazy8.chips.Field({required:true}),
    repurchaseable: new lazy8.chips.Field({required:true}),
    cannot_purchase_after: new lazy8.chips.Field({required:true})
};

ce4.product.AvailableProduct.prototype.is_repurchaseable = function is_repurchaseable() {
    return this.repurchaseable === 1;
};

ce4.product.AvailableProduct.prototype.was_discounted = function was_discounted() {
    return this.price < this.initial_price;
};

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.product.PurchasedProduct = function PurchasedProduct(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.product.PurchasedProduct, lazy8.chips.Model);

/** @override */
ce4.product.PurchasedProduct.prototype.fields = {
    product_id: new lazy8.chips.Field({id_field:true}),
    product_key: new lazy8.chips.Field({required:true}),
    name: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    price: new lazy8.chips.Field({required:true}),
    currency: new lazy8.chips.Field({required:true}),
    price_display: new lazy8.chips.Field({required:true}),
    icon: new lazy8.chips.Field({required:true}),
    sort: new lazy8.chips.Field({required:true}),
    repurchaseable: new lazy8.chips.Field({required:true}),
    purchased_at: new ce4.util.EpochDateField({required:true}),
    cannot_purchase_after: new lazy8.chips.Field({required:true})
};

ce4.product.PurchasedProduct.prototype.is_repurchaseable = function is_repurchaseable() {
    return this.repurchaseable === 1;
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.product.AvailableProductCollection = function AvailableProductCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.product.AvailableProductCollection, lazy8.chips.Collection);

/** @override */
ce4.product.AvailableProductCollection.prototype.model_constructor = ce4.product.AvailableProduct;

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.product.PurchasedProductCollection = function PurchasedProductCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.product.PurchasedProductCollection, lazy8.chips.Collection);

/** @override */
ce4.product.PurchasedProductCollection.prototype.model_constructor = ce4.product.PurchasedProduct;
