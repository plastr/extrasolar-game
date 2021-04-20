# Copyright (c) 2010-2014 Lazy 8 Studios, LLC.
# All rights reserved.
# This module is a thin wrapper around the S3 functionality of the boto library
import urlparse, re

from boto.s3.connection import S3Connection

# This S3Connection object is used for signing URLs ONLY and should not be used to perform
# any network requests as it is most likely not thread safe to do so.
S3_SIGN = None
def init_module(download_access, download_secret):
    global S3_SIGN
    # is_secure means https is used for the signed URLs.
    S3_SIGN = S3Connection(download_access, download_secret, is_secure=True)

def generate_download_url(source_url, filename, timeout=3600):
    """
    Returns a signed Amazon S3 URL based on the provided source_url with the content-disposition set to
    attachment which will cause a web browser to attempt to download the object, e.g. popup Save As dialog. 
    The provided filename parameter will be set in the content-disposition header and will be the suggested
    filename for the user in the Save As dialog.
    The optional timeout value is the number of seconds the signed URL will be valid.
    NOTE: It is assumed the source_url is the 'fully qualified' S3 URL pattern e.g. https://s3-{REGION}/{BUCKET}/{KEY_PATH}
    so that the S3 wildcard SSL certificate will work with buckets with .'s in the name.
    NOTE: Returns None if the provided source_url cannot be parsed into its expected components.
    """
    base_url, bucket, key_name = parse_bucket_url(source_url)
    if base_url is None: return None

    disposition = 'attachment; filename="%s"' % filename
    response_headers = { 'response-content-disposition': disposition }
    # Use boto to sign generate the signed URL, though we are only going to use the path and query parameters.
    # Even though this is called the S3Connection object, just calling generate_url does NOT perform
    # any network requests.
    signed_url = S3_SIGN.generate_url(timeout, 'GET', bucket=bucket, key=key_name, response_headers=response_headers)
    signed_url_parsed = urlparse.urlparse(signed_url)

    # Recombine the the original base URL (s3+REGION/BUCKET) and the signed key path + query parameters.
    download_url = base_url + signed_url_parsed.path + '?' + signed_url_parsed.query
    return download_url

# The pattern used to match S3 image object URLs for signing.
# Matches the 'base' S3 URL and key path as two components: (https://s3-{REGION}/{BUCKET})(/{KEY_PATH})
# The bucket name is also pulled out as well.
S3_URL_RE = re.compile(r'(https?://s3-.+?/(.+?))(/.*)')
def parse_bucket_url(url):
    """
    Parse an S3 URL in region/bucket/key format into three components: base_url (inc. bucket_name), bucket_name, key_name.
    Returns None, None, None if the URL could not be parsed.
    e.g.:
    https://s3-us-west-1.amazonaws.com/bucket.name/key/path.jpg ->
        ('https://s3-us-west-1.amazonaws.com/bucket.name', 'bucket.name', '/key/path.jpg')

    >>> parse_bucket_url('https://s3-us-west-1.amazonaws.com/bucket.name/key/path.jpg')
    ('https://s3-us-west-1.amazonaws.com/bucket.name', 'bucket.name', '/key/path.jpg')

    >>> parse_bucket_url('https://bucket.name.s3.amazonaws.com/key/path.jpg')
    (None, None, None)
    """
    # Parse the source_url into its base URL (S3 host + bucket), bucket and path (S3 key name) components.
    match = S3_URL_RE.match(url)
    # If the regex failed to parse the URL, return None to signal to the caller something went wrong.
    if match is None: return None, None, None
    base_url, bucket, key_name = match.groups()
    return base_url, bucket, key_name
