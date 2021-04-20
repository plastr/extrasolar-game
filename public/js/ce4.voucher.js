// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.voucher contains the Voucher model.
goog.provide("ce4.voucher.Voucher");
goog.provide("ce4.voucher.VoucherCollection");

goog.require('lazy8.chips.Model');
goog.require('lazy8.chips.Field');
goog.require('lazy8.chips.Collection');

goog.require('ce4.util.EpochDateField');

/**
 * @constructor
 * @extends {lazy8.chips.Model}
 */
ce4.voucher.Voucher = function Voucher(chip_struct) {
    lazy8.chips.Model.call(this, chip_struct);
};
goog.inherits(ce4.voucher.Voucher, lazy8.chips.Model);

/** @override */
ce4.voucher.Voucher.prototype.fields = {
    voucher_key: new lazy8.chips.Field({id_field:true}),
    name: new lazy8.chips.Field({required:true}),
    description: new lazy8.chips.Field({required:true}),
    delivered_at: new ce4.util.EpochDateField({required:true})
};

/**
 * @constructor
 * @extends {lazy8.chips.Collection}
 */
ce4.voucher.VoucherCollection = function VoucherCollection(chip_structs) {
    lazy8.chips.Collection.call(this, chip_structs);
};
goog.inherits(ce4.voucher.VoucherCollection, lazy8.chips.Collection);

/** @override */
ce4.voucher.VoucherCollection.prototype.model_constructor = ce4.voucher.Voucher;
