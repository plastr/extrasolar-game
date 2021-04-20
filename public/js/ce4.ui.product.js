// Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
// All rights reserved.
// ce4.product.details contains shop sku product details
goog.provide('ce4.ui.product');

ce4.ui.product.header = {
    'SKU_INVITATION': 'Invite a friend as an XRI Volunteer',
    'SKU_S1_PASS': 'Upgrade to XRI Associate',
    'SKU_ALL_PASS': 'Upgrade to XRI Pioneer',
    'SKU_S1_PASS_GIFT': 'Invite a friend as an XRI Associate',
    'SKU_ALL_PASS_GIFT': 'Invite a friend as an XRI Pioneer'
};

// Lookup table for product details.
ce4.ui.product.details = {
    'SKU_INVITATION': {  // This particular SKU exists only on the client.
        title: 'XRI Volunteer',
        subtitle:'',
        div_class: 'store-item-volunteer',
        icon: ce4.util.url_static('/img/store/store_bigicon_volunteer.png'),
        product_key: undefined,
        product_key_gift: undefined,
        panoramas: '10',
        infrared: '5',
        moves: '2',
        feature_description: 'Limited photo options',
        min_time: '4:00:00',
        min_time_description: '4 hours minimum per photo',
        final_description: ''
    },
    'SKU_S1_PASS': {
        title: 'XRI Associate',
        subtitle:'Priority Access: Artocos Island Missions',
        div_class: 'store-item-associate',
        icon: ce4.util.url_static('/img/store/store_bigicon_associate.png'),
        product_key: 'SKU_S1_PASS',
        product_key_gift: 'SKU_S1_PASS_GIFT',
        panoramas: '<span class="store-item-highlight large-text">&infin;</span>',
        infrared: '<span class="store-item-highlight large-text">&infin;</span>',
        moves: '<span class="store-item-highlight">3</span>',
        feature_description: 'No limit on photo options',
        min_time: '<span class="store-item-highlight">1:00:00</span>',
        min_time_description: 'Minimum time reduced to </strong>1 hour</strong>',
        final_description: 'Access to Artocos island<br>missions only.'
    },
    'SKU_ALL_PASS': {
        title: 'XRI Pioneer',
        subtitle:'Priority Access: All Epsilon Prime Missions',
        div_class: 'store-item-pioneer',
        icon: ce4.util.url_static('/img/store/store_bigicon_pioneer.png'),
        product_key: 'SKU_ALL_PASS',
        product_key_gift: 'SKU_ALL_PASS_GIFT',
        panoramas: '<span class="store-item-highlight large-text">&infin;</span>',
        infrared: '<span class="store-item-highlight large-text">&infin;</span>',
        moves: '<span class="store-item-highlight">4</span>',
        feature_description: 'No limit on photo options',
        min_time: '<span class="store-item-highlight">1:00:00</span>',
        min_time_description: 'Minimum time reduced to </strong>1 hour</strong>',
        final_description: 'Access to all current<br><span class="store-item-highlight">and future missions</span>.'
    }
};

// Duplicate the details for the gift SKUs.
ce4.ui.product.details['SKU_S1_PASS_GIFT']  = ce4.ui.product.details['SKU_S1_PASS'];
ce4.ui.product.details['SKU_ALL_PASS_GIFT'] = ce4.ui.product.details['SKU_ALL_PASS'];
