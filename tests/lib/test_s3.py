# Copyright (c) 2010-2011 Lazy 8 Studios, LLC.
# All rights reserved.
from front.tests import base

from front.lib import s3

TEST_BUCKET = "images.us-west-1.extrasolar.com"
EXAMPLE_IMAGE_URL = "https://s3-us-west-1.amazonaws.com/"+TEST_BUCKET+"/photos/3a/76/3a7671e2-28a3-11e2-9f62-123140007c6e_1920x1440.jpg"
NO_BUCKET_URL = "https://images.us-west-1.extrasolar.com.s3.amazonaws.com/photos/3a/76/3a7671e2-28a3-11e2-9f62-123140007c6e_1920x1440.jpg"

class TestS3(base.TestCase):
    def test_generate_download_url(self):
        filename = "testing.jpg"
        download_url = s3.generate_download_url(EXAMPLE_IMAGE_URL, filename)
        # Make sure the bucket in the path survived the transformation.
        self.assertTrue('/'+TEST_BUCKET+'/' in download_url)
        self.assertTrue(filename in download_url)
        self.assertTrue('attachment' in download_url)
        self.assertTrue('Signature' in download_url)

    def test_generate_download_url_no_bucket(self):
        # Test trying to sign an S3 URL in the normal format, which s3_download_image_url is not currently
        # equiped to deal with. This should return None to signal to the caller a URL could not be signed.
        filename = "testing.jpg"
        download_url = s3.generate_download_url(NO_BUCKET_URL, filename)
        self.assertIsNone(download_url)

        download_url = s3.generate_download_url('http://example.com', filename)
        self.assertIsNone(download_url)
