# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base
from front.tests.base import PRODUCT_KEY_S1, VOUCHER_KEY_S1, PRODUCT_KEY_ALL, VOUCHER_KEY_ALL, PRODUCT_KEY_S1_GIFT, PRODUCT_KEY_ALL_GIFT
from front.tests.mock_stripe import ChargeAlwaysSuccess, ChargeCardError
from front.tests.mock_stripe import FAKE_MARKER, FAKE_CHARGE_ID_1, FAKE_CHARGE_ID_2
from front.tests.mock_stripe import FAKE_CARD_TYPE, FAKE_CARD_LAST4, FAKE_CARD_EXP_MONTH, FAKE_CARD_EXP_YEAR, FAKE_CARD_NAME

from front.models import chips
from front.backend.shop import invoice as invoice_module
from front.backend.shop import transaction as transaction_module

# NOTE: Test methods which have the suffix _stripe_api are using the live Stripe API
# (in testing mode) and thus requires a network connection to work.
class TestShop(base.TestCase):
    def setUp(self):
        super(TestShop, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    # Test purchasing the S1 and ALL passes using the live Stripe API.
    def test_shop_buy_s1_and_all_passes_stripe_api(self):
        # Check the initial shop gamestate.
        gamestate = self.get_gamestate()
        # There should be no saved Stripe card.
        self.assertEqual(gamestate['user']['shop']['stripe_has_saved_card'], 0)
        self.assertIsNone(gamestate['user']['shop']['stripe_customer_data'])
        # And no purchased products.
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 0)
        # And the expected available products.
        self.assertTrue(len(gamestate['user']['shop']['available_products']) > 0)
        self.assertTrue(PRODUCT_KEY_S1 in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL in gamestate['user']['shop']['available_products'])
        # And the expected voucher to be delivered is not present.
        self.assertTrue(VOUCHER_KEY_S1 not in gamestate['user']['vouchers'])
        self.assertTrue(VOUCHER_KEY_ALL not in gamestate['user']['vouchers'])
        # There should be no invoices for this new user.
        user = self.get_logged_in_user()
        self.assertEqual(len(user.shop.invoices), 0)

        # Purchase the first product, requesting to save the credit card.
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=True, gamestate=gamestate)

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()

        # The card used should now be saved, as requested.
        self.assertEqual(gamestate['user']['shop']['stripe_has_saved_card'], 1)
        self.assertEqual(gamestate['user']['shop']['stripe_customer_data']['card_type'], FAKE_CARD_TYPE)
        self.assertEqual(gamestate['user']['shop']['stripe_customer_data']['card_last4'], FAKE_CARD_LAST4)
        self.assertEqual(gamestate['user']['shop']['stripe_customer_data']['card_exp_month'], FAKE_CARD_EXP_MONTH)
        self.assertEqual(gamestate['user']['shop']['stripe_customer_data']['card_exp_year'], FAKE_CARD_EXP_YEAR)
        self.assertEqual(gamestate['user']['shop']['stripe_customer_data']['card_name'], FAKE_CARD_NAME)
        found_chips = self.chips_for_path(['user', 'shop'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['stripe_has_saved_card'], 1)
        self.assertEqual(found_chips[0]['value']['stripe_customer_data']['card_type'], FAKE_CARD_TYPE)
        self.assertEqual(found_chips[0]['value']['stripe_customer_data']['card_last4'], FAKE_CARD_LAST4)
        self.assertEqual(found_chips[0]['value']['stripe_customer_data']['card_exp_month'], FAKE_CARD_EXP_MONTH)
        self.assertEqual(found_chips[0]['value']['stripe_customer_data']['card_exp_year'], FAKE_CARD_EXP_YEAR)
        self.assertEqual(found_chips[0]['value']['stripe_customer_data']['card_name'], FAKE_CARD_NAME)

        # A new purchased product of the expected type should exist.
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 1)
        product = gamestate['user']['shop']['purchased_products'].values()[0]
        self.assertEqual(product['product_key'], PRODUCT_KEY_S1)
        self.assertIsNotNone(product['product_id'])
        self.assertIsNotNone(product['purchased_at'])
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_S1)
        self.assertIsNotNone(found_chips[0]['value']['product_id'])
        self.assertIsNotNone(found_chips[0]['value']['purchased_at'])

        # A voucher should have been delivered.
        self.assertTrue(VOUCHER_KEY_S1 in gamestate['user']['vouchers'])
        found_chips = self.chips_for_path(['user', 'vouchers', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['voucher_key'], VOUCHER_KEY_S1)

        # The product which was purchased (which was not repurchaseable) should no longer be available.
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        found_chips = self.chips_for_path(['user', 'shop', 'available_products', PRODUCT_KEY_S1], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.DELETE)
        self.assertEqual(found_chips[0]['path'][-1], PRODUCT_KEY_S1)

        # An invoice should have been created for this product purchase.
        user = self.get_logged_in_user()
        self.assertEqual(len(user.shop.invoices), 1)
        invoice = user.shop.invoices[0]
        # There should be one saved product.
        self.assertEqual(len(invoice.products), 1)
        purchased_product = invoice.products[0]
        self.assertEqual(purchased_product.product_key, PRODUCT_KEY_S1)
        self.assertEqual(invoice.total_amount, purchased_product.price)
        # Verify the price_display property is working.
        self.assertIsNotNone(purchased_product.price_display)
        self.assertEqual(invoice.currency, purchased_product.currency)
        # And one saved transaction.
        self.assertEqual(len(invoice.transactions), 1)
        transaction = invoice.transactions[0]
        charge_id = transaction.gateway_data[transaction_module.gateway_data_keys.STRIPE_CHARGE_ID]
        self.assertIsNotNone(charge_id)
        # Make sure the real Stripe API was used.
        self.assertTrue(FAKE_MARKER not in charge_id)

        # Advance time a bit to advance last seen chip time.
        self.advance_now(seconds=10)

        # Remove the Stripe saved credit card.
        remove_saved_card_url = str(gamestate['user']['shop']['urls']['stripe_remove_saved_card'])
        response = self.json_post(remove_saved_card_url)
        gamestate = self.get_gamestate()
        self.assertEqual(gamestate['user']['shop']['stripe_has_saved_card'], 0)
        self.assertIsNone(gamestate['user']['shop']['stripe_customer_data'])
        found_chips = self.chips_for_path(['user', 'shop'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['stripe_has_saved_card'], 0)
        self.assertIsNone(found_chips[0]['value']['stripe_customer_data'])

        # Attempting to remove the card again is an error.
        response = self.json_post(remove_saved_card_url, status=400)
        self.assertTrue('No saved credit card to remove' in response['errors'][0])

        # Advance time a bit to advance last seen chip time.
        self.advance_now(seconds=10)

        # Purchase the second product, requesting to NOT save the credit card this time.
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_ALL], save_card=False, gamestate=gamestate)

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()

        # The card used should not be saved, as requested.
        self.assertEqual(gamestate['user']['shop']['stripe_has_saved_card'], 0)
        found_chips = self.chips_for_path(['user', 'shop'], response)
        self.assertEqual(len(found_chips), 0)

        # A new purchased product of the expected type should exist.
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 2)
        purchased_products = sorted(gamestate['user']['shop']['purchased_products'].values(),
            key=lambda p: p['purchased_at'])
        self.assertEqual(purchased_products[0]['product_key'], PRODUCT_KEY_S1)
        self.assertEqual(purchased_products[1]['product_key'], PRODUCT_KEY_ALL)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_ALL)
        self.assertIsNotNone(found_chips[0]['value']['product_id'])
        self.assertIsNotNone(found_chips[0]['value']['purchased_at'])

        # A voucher should have been delivered.
        self.assertTrue(VOUCHER_KEY_ALL in gamestate['user']['vouchers'])
        found_chips = self.chips_for_path(['user', 'vouchers', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['voucher_key'], VOUCHER_KEY_ALL)

        # The product which was purchased (which was unique) should no longer be available.
        self.assertTrue(PRODUCT_KEY_ALL not in gamestate['user']['shop']['available_products'])
        found_chips = self.chips_for_path(['user', 'shop', 'available_products', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.DELETE)
        self.assertEqual(found_chips[0]['path'][-1], PRODUCT_KEY_ALL)

    # Test that purchasing the S1 pass before the ALL pass discounts the ALL product.
    def test_shop_buy_s1_pass_discounts_all_pass(self):
        # Grab the pre purchase gamestate.
        gamestate = self.get_gamestate()

        # Capture the pre-purchase price of the ALL product.
        product_all_price_before = gamestate['user']['shop']['available_products'][PRODUCT_KEY_ALL]['price']
        self.assertEqual(product_all_price_before, gamestate['user']['shop']['available_products'][PRODUCT_KEY_ALL]['initial_price'])

        # Purchase the S1 pass.
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=False, charge=charge)

        # Retreive the invoice so that the email receipt body can be checked.
        user = self.get_logged_in_user()
        self.assertEqual(len(user.shop.invoices), 1)
        invoice = user.shop.invoices[0]
        self.assertEqual(len(invoice.products), 1)
        purchased_product = invoice.products[0]

        # A receipt email should have been sent.
        self.assertEqual(len(self.get_sent_emails()), 1)
        email = self.get_sent_emails()[0]
        self.assertTrue("Receipt" in email.subject)
        self.assertTrue(str(invoice.invoice_id) in email.body_html)
        self.assertTrue(invoice.total_amount_display in email.body_html)
        self.assertTrue(purchased_product.name in email.body_html)

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()

        # A new purchased product of the expected type should exist.
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 1)
        product = gamestate['user']['shop']['purchased_products'].values()[0]
        self.assertEqual(product['product_key'], PRODUCT_KEY_S1)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_S1)

        # The ALL product should now be discounted by a fraction of the pre-purchase price of the S1 pass.
        product_all_price_after = gamestate['user']['shop']['available_products'][PRODUCT_KEY_ALL]['price']
        self.assertTrue(product_all_price_after < product_all_price_before)
        self.assertTrue(product_all_price_after > 0)
        self.assertNotEqual(product_all_price_after, gamestate['user']['shop']['available_products'][PRODUCT_KEY_ALL]['initial_price'])
        # A chip should have been sent with the pricing change.
        found_chips = self.chips_for_path(['user', 'shop', 'available_products', PRODUCT_KEY_ALL], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['price'], product_all_price_after)
        self.assertTrue('initial_price' not in found_chips[0]['value'])
        self.assertNotEqual(found_chips[0]['value']['price'], gamestate['user']['shop']['available_products'][PRODUCT_KEY_ALL]['initial_price'])
        self.assertIsNotNone(found_chips[0]['value']['price_display'])

    # Test that purchasing the ALL pass before the S1 pass makes the S1 product not available.
    def test_shop_buy_all_pass_removes_s1_pass(self):
        # Check the initial gamestate.
        gamestate = self.get_gamestate()
        self.assertIsNone(gamestate['user']['current_voucher_level'])

        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_ALL], save_card=False, charge=charge)

        # Grab the post purchase gamestate.
        gamestate = self.get_gamestate()

        # A new purchased product of the expected type should exist.
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 1)
        product = gamestate['user']['shop']['purchased_products'].values()[0]
        self.assertEqual(product['product_key'], PRODUCT_KEY_ALL)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_ALL)

        # The S1 product and the just purchased ALL should no longer be available.
        self.assertTrue(PRODUCT_KEY_S1 not in gamestate['user']['shop']['available_products'])
        self.assertTrue(PRODUCT_KEY_ALL not in gamestate['user']['shop']['available_products'])
        found_chips = self.chips_for_path(['user', 'shop', 'available_products', '*'], response)
        self.assertEqual(len(found_chips), 2)
        self.assertEqual(found_chips[0]['action'], chips.DELETE)
        self.assertEqual(found_chips[0]['path'][-1], PRODUCT_KEY_S1)
        self.assertEqual(found_chips[1]['action'], chips.DELETE)
        self.assertEqual(found_chips[1]['path'][-1], PRODUCT_KEY_ALL)

        # A voucher should have been delivered.
        self.assertTrue(VOUCHER_KEY_ALL in gamestate['user']['vouchers'])
        # And the current_voucher_level should have changed.
        self.assertEqual(gamestate['user']['current_voucher_level'], VOUCHER_KEY_ALL)
        found_chips = self.chips_for_path(['user'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['current_voucher_level'], VOUCHER_KEY_ALL)

    # Test that it is possible to buy two products at the same time.
    def test_shop_buy_multiple_products(self):
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        gift_product_specifics1 = self.gift_product_specifics(PRODUCT_KEY_S1_GIFT, recipient_email="testrecipient1@example.com")
        gift_product_specifics2 = self.gift_product_specifics(PRODUCT_KEY_ALL_GIFT, recipient_email="testrecipient2@example.com")
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1_GIFT, PRODUCT_KEY_ALL_GIFT],
                                                      product_specifics_list=[gift_product_specifics1, gift_product_specifics2],
                                                      save_card=False, charge=charge)

        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 2)
        purchased_product_keys = set([p['product_key'] for p in gamestate['user']['shop']['purchased_products'].itervalues()])
        self.assertTrue(PRODUCT_KEY_S1_GIFT in purchased_product_keys)
        self.assertTrue(PRODUCT_KEY_ALL_GIFT in purchased_product_keys)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(len(found_chips), 2)
        self.assertEqual(found_chips[0]['action'], chips.ADD)
        self.assertTrue(found_chips[0]['value']['product_key'] in [PRODUCT_KEY_S1_GIFT, PRODUCT_KEY_ALL_GIFT])
        self.assertEqual(found_chips[1]['action'], chips.ADD)
        self.assertTrue(found_chips[1]['value']['product_key'] in [PRODUCT_KEY_S1_GIFT, PRODUCT_KEY_ALL_GIFT])

    # Test that sending the wrong number of product_specifics when purchasing multiple products is an exception.
    def test_shop_wrong_product_specifics(self):
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        self.assertRaises(invoice_module.InvoiceError, self.shop_stripe_purchase_products, save_card=True,
                                                       product_keys=[PRODUCT_KEY_S1, PRODUCT_KEY_S1_GIFT],
                                                       # Only one specifics but two products.
                                                       product_specifics_list=[{}],
                                                       charge=charge)

    # Test attempting to buy a non-repurchaseable product twice, either combined in an initial purchase
    # or after it has already been purchased, results in an exception.
    def test_shop_cannot_buy_non_repurchaseable_products_twice(self):
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        # Try and buy two non-repurchaseable products together in one purchase
        self.assertRaises(invoice_module.InvoiceError, self.shop_stripe_purchase_products, save_card=True,
                                                       product_keys=[PRODUCT_KEY_S1, PRODUCT_KEY_S1], charge=charge)

        # Now purchase one non-repurchaseable product.
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=True, charge=charge)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_S1)

        # Try and buy that same non-repurchaseable product again.
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_2)
        self.assertRaises(invoice_module.InvoiceError, self.shop_stripe_purchase_products, save_card=False, 
                                                       product_keys=[PRODUCT_KEY_S1], charge=charge)

        # Make sure only one product was purchased.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 1)

    def test_shop_deny_cannot_purchase_after_products_together(self):
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        # Try and buy two products which are exclusive of each other in one purchase
        self.assertRaises(invoice_module.InvoiceError, self.shop_stripe_purchase_products, save_card=True,
                                                       product_keys=[PRODUCT_KEY_S1, PRODUCT_KEY_ALL], charge=charge)

        # Now purchase one exclusive product.
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_ALL], save_card=True, charge=charge)
        found_chips = self.chips_for_path(['user', 'shop', 'purchased_products', '*'], response)
        self.assertEqual(found_chips[0]['value']['product_key'], PRODUCT_KEY_ALL)

        # And try and buy a product which is exclusive from it (which is actually not available anymore anyway)
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_2)
        self.assertRaises(invoice_module.InvoiceError, self.shop_stripe_purchase_products, save_card=False,
                                                       product_keys=[PRODUCT_KEY_S1], charge=charge)

        # Make sure only one product was purchased.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 1)

    # Test a saved card that has expired (fake the expired error) and make sure the card is deleted and a specific
    # error message is returned to the client.
    def test_shop_expired_saved_card(self):
        # Make an initial purchase to save the card/customer_id
        charge = ChargeAlwaysSuccess(FAKE_CHARGE_ID_1)
        self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=True, charge=charge)

        # Verify the card was saved.
        gamestate = self.get_gamestate()
        self.assertEqual(gamestate['user']['shop']['stripe_has_saved_card'], 1)

        # Advance time a bit to advance last seen chip time.
        self.advance_now(seconds=10)

        # Expect a warning log message.
        self.expect_log('front.resource.stripe_node', '.*expired_card.*')

        # Now attempt to make another purchase which raises the fake expired_card error.
        expired_error = ChargeCardError("expired_card", "This card has expired. Fake error.")
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_ALL], charge=expired_error, status=400)

        # There should have been a specific user error message.
        self.assertTrue('saved credit card has expired' in response['errors'][0])

        # And the card should have been removed
        gamestate = self.get_gamestate()
        self.assertEqual(gamestate['user']['shop']['stripe_has_saved_card'], 0)
        found_chips = self.chips_for_path(['user', 'shop'], response)
        self.assertEqual(len(found_chips), 1)
        self.assertEqual(found_chips[0]['action'], chips.MOD)
        self.assertEqual(found_chips[0]['value']['stripe_has_saved_card'], 0)

    # Test an example CardError without using the Stripe API, since the stripe.js or token generation code
    # below does not really permit us to create data that the backend will raise these errors for.
    def test_shop_invalid_card_error(self):
        # Expect a warning log message.
        self.expect_log('front.resource.stripe_node', '.*invalid_number.*')

        # Attempt to purchase the products with the fake charge object which will raise the CardError.
        charge_error = ChargeCardError("invalid_number", "This card number is invalid. Fake error.")
        response = self.shop_stripe_purchase_products(product_keys=[PRODUCT_KEY_S1], save_card=False, charge=charge_error, status=400)
        # Make sure no chips were issued and an error was returned to the client.
        self.assertTrue('chips' not in response)
        self.assertTrue('Fake error' in response['errors'][0])
        # Make sure no products were purchased.
        gamestate = self.get_gamestate()
        self.assertEqual(len(gamestate['user']['shop']['purchased_products']), 0)
