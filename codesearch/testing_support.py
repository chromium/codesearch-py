# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

import os
import sys
import hashlib
import json

from email.message import Message

try:
  from urllib.request import urlopen, Request, HTTPSHandler, install_opener, build_opener
except ImportError:
  from urllib2 import urlopen, Request, HTTPSHandler, install_opener, build_opener, addinfourl

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
RESPONSE_DATA_DIR = os.path.join(SCRIPT_DIR, 'testdata', 'responses')

class TestHttpHandler(HTTPSHandler):
    def __init__(self):
        pass

    def default_open(self, request):
        return None

    def https_open(self, request):
        url = request.get_full_url()
        data = request.get_data() if request.has_data() else ''
        digest = hashlib.sha1((url + data).encode('utf-8')).hexdigest()
        response_file_path = os.path.join(RESPONSE_DATA_DIR, digest)

        if os.path.exists(response_file_path):
            f = open(response_file_path, 'r')
            m = Message()
            m.add_header('Content-Type', 'application/json')
            resp = addinfourl(f, headers=m, url=url, code=200)
            resp.msg = 'Success'
            resp.code = 200
            return resp

        # The file was not there. Create a missing resource file.
        missing_response_file_path = os.path.join(RESPONSE_DATA_DIR, '{}.missing'.format(digest))
        with open(missing_response_file_path, 'w') as f:
            json.dump({ "url": url, "data": data, "digest": digest}, f, encoding='utf-8')

        return None

    def http_open(self, request):
        return self.https_open(request)

def InstallTestRequestHandler():
    """Any test that makes network requests to https://cs.codesearch.com (i.e.
    those that rely on making network requests) should call this function in
    their respective setUp() functions.
   
    Doing so installs a test request handler that will fail the first time it
    is called with a new URL, but will write out a file indicating which URL
    requests were seen. One can then run the testing_support.py script directly
    which resolves the URL requests, and adds a file to the |testdata|
    directory containing the expected response data.

    This mechanism prevents the tests from making direct network requests.
    """ 
    install_opener(build_opener(TestHttpHandler()))

if __name__ == '__main__':

    # Attempt to resolve all missing resource requests.
    for name in os.listdir(RESPONSE_DATA_DIR):
        if not name.endswith('.missing'):
            continue

        print 'Resolving {}'.format(name)

        with open(os.path.join(RESPONSE_DATA_DIR, name), 'r') as f:
            o = json.load(f, encoding='utf-8')

        url, data, digest = o["url"], o["data"], o["digest"]
        req = Request(url=url)
        if data != '':
            req.add_data(data)
        try:
            response = urlopen(req, timeout=3)
            result = response.read()

            with open(os.path.join(RESPONSE_DATA_DIR, digest), 'w') as f:
                f.write(result)

            os.unlink(os.path.join(RESPONSE_DATA_DIR, name))

            print '   Resolved. Wrote {}'.format(digest)
        except Exception as e:
            print '   FAILED.:{}'.format(e.message)
