# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from datetime import timedelta

from front.lib import urls, gametime, utils

from front.tests import base
from front.tests.base import points

class TestFetchChips(base.TestCase):
    def setUp(self):
        super(TestFetchChips, self).setUp()
        self.create_user('testuser@example.com', 'pw')

    # This version of the test very precisely controls the value of last_seen_chip_time to assert
    # that jumping over a microsecond gap hides all chips before that gap.
    def test_fetch_chips_exact(self):
        self.create_target(**points.FIRST_MOVE)

        # Must look at least 1 microsecond in the past because a chip created AT last_seen_chip_time
        # will not be returned.
        last_seen_chip_time = utils.usec_js_from_dt(gametime.now() - timedelta(microseconds=1))
        response = self.json_get(urls.fetch_chips(), _last_seen_chip_time=last_seen_chip_time)
        # There should be at least one chip sent when creating a target.
        self.assertTrue(len(response['chips']) >= 1)

        last_seen_chip_time = utils.usec_js_from_dt(gametime.now() + timedelta(microseconds=1))
        response = self.json_get(urls.fetch_chips(), _last_seen_chip_time=last_seen_chip_time)
        # There should be no new chips since our last fetch.
        self.assertTrue(len(response) == 0)

    # This version of the test relies on the base.py implementation which emulates
    # the real client code much more accurately e.g. when chips come in the most recent
    # one updates the clients cached value of last_seen_chip_time
    def test_fetch_chips_like_client(self):
        self.create_target(**points.FIRST_MOVE)

        response = self.fetch_chips()
        # There should be at least one chip sent when creating a target.
        self.assertTrue(len(response['chips']) >= 1)

        response = self.fetch_chips()
        # There should be no new chips since our last fetch.
        self.assertTrue(len(response) == 0)

    def test_fetch_chips_no_auth(self):
        self.logout_user()
        response = self.fetch_chips(status=400)
        self.assertTrue(len(response['errors']) > 0)
