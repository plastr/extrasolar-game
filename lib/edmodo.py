# The MIT License (MIT)
# 
# Copyright (c) 2014 Lazy 8 Studios, LLC
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


"""Python client library for the Edmodo API, based in part on Facebook's
official Python library.

Edmodo API documentation at https://<your_sandbox_name>.edmodobox.com/home#/developer/api
Example usage:

launch_key = ... # Fetch launch_key from the GET parameters of the server request
try:
    # Initialize the Edmodo API helper.
    edmodoAPI = edmodo.EdmodoAPI(server=<edmodo_server>, api_version='v1.1')
    # Make sure we've been passed a valid launch key
    profile = edmodoAPI.get_object('/launchRequests', api_key=<edmodo_secret_key>, launch_key=launch_key)
    
except edmodo.EdmodoAPIError, e:
    ... # Return error e

# We should now have a valid profile for an Edmodo user with unique id profile['user_id'].
# We can check our database to see if a user with this ID exists. If so, return the appropriate
# content for that user. If not, create a new account with the given user_id and then return content.
"""

import urllib
import urllib2
import socket

# Find a JSON parser
try:
    import simplejson as json
except ImportError:
    try:
        from django.utils import simplejson as json
    except ImportError:
        import json
_parse_json = json.loads


class EdmodoAPI(object):
    """A client for the Edmodo API.
    """
    def __init__(self, server='appsapi.edmodo.com', api_version='v1.1', timeout=None):
        self.server = server
        self.api_version = api_version
        self.timeout = timeout
        
    def get_object(self, id, **args):
        """Fetchs the given API object.
        For instance, to initialize the API And make a call to /launchRequests, we could use the following:
        edmodoAPI = edmodo.EdmodoAPI(server=edmodo_server, api_version='v1.1')
        profile = edmodoAPI.get_object('/launchRequests', api_key=edmodo_secret_key, launch_key=launch_key)
        """
        return self.request(id, args)

    def request(self, path, args=None, post_args=None):
        """Fetches the given path in the Edmodo API.

        We translate args to a valid query string. If post_args is
        given, we send a POST request to the given path with the given
        arguments.

        """
        args = args or {}
        post_data = None if post_args is None else urllib.urlencode(post_args)
        try:
            file = urllib2.urlopen("https://" + self.server + "/" + self.api_version + path + "?" +
                    urllib.urlencode(args), post_data, timeout=self.timeout)
        except urllib2.HTTPError, e:
            response = _parse_json(e.read())
            raise EdmodoAPIError(response)
        except TypeError:
            # Timeout support for Python <2.6
            if self.timeout:
                socket.setdefaulttimeout(self.timeout)
            file = urllib2.urlopen("https://" + self.server + "/" + self.api_version + path + "?" +
                    urllib.urlencode(args), post_data)
        try:
            fileInfo = file.info()
            if fileInfo.maintype == 'text' or fileInfo.maintype == 'application':
                response = _parse_json(file.read())
            elif fileInfo.maintype == 'image':
                mimetype = fileInfo['content-type']
                response = {
                    "data": file.read(),
                    "mime-type": mimetype,
                    "url": file.url,
                }
            else:
                raise EdmodoAPIError('Maintype was %s. Text, application, or image expected.' % fileInfo.maintype)
        finally:
            file.close()
        if response and isinstance(response, dict) and response.get("error"):
            raise EdmodoAPIError(response["error"]["code"],
                                response["error"]["message"])
        return response

class EdmodoAPIError(Exception):
    def __init__(self, result):
        #Exception.__init__(self, message)
        #self.type = type
        self.result = result
        try:
            self.type = result["code"]
        except:
            self.type = ""

        # OAuth 2.0 Draft 10
        try:
            self.message = result["error_description"]
        except:
            # OAuth 2.0 Draft 00
            try:
                self.message = result["error"]["message"]
            except:
                # REST server style
                try:
                    self.message = result["error_msg"]
                except:
                    self.message = result

        Exception.__init__(self, self.message)
