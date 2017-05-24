# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from __future__ import absolute_import

import os
import shutil
import socket
import tempfile
import unittest

from .client_api import CodeSearch
from .messages import CompoundRequest, CompoundResponse, FileInfoRequest, FileInfoResponse

try:
    from urllib.request import urlopen, Request
    from urllib.parse import urlencode
except ImportError:
    from urllib2 import urlopen, Request, OpenerDirector, install_opener
    from urllib import urlencode


class FakeOpenerDirector:
    def __init__(self):
        self.responses = {}
        self.requests = []

    def add_response(self, url, response):
        self.responses[url] = response

    def open(self, fullurl, data=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        if isinstance(fullurl, Request):
            request = fullurl
            self.requests.append(fullurl)
        else:
            request = Request(fullurl)
            if data:
                request.add_data(data)
            self.requests.append(request)
        assert request.get_full_url() in self.responses
        return self.responses[request.get_full_url()]


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body


class TestCodeSearch(unittest.TestCase):
    def Touch(self, path):
        with open(path, 'w'):
            pass

    def CreateFakeChromeCheckout(self):
        path = tempfile.mkdtemp()
        os.mkdir(os.path.join(path, 'src'))
        self.Touch(os.path.join(path, 'src', '.gn'))
        self.Touch(os.path.join(path, 'src', 'foo.cc'))
        return path

    def test_user_agent(self):
        mock_opener = FakeOpenerDirector()
        mock_opener.add_response(
                'https://cs.chromium.org/codesearch/json?annotation_request=b&type=b&id=4&type=e&file_spec=b&name=src%2Ffoo.cc&package_name=chromium&file_spec=e&annotation_request=e',
                FakeResponse('{ "annotation_response": [{ "return_code": 1 }] }'))

        install_opener(mock_opener)
        test_dir = None
        try:
            test_dir = self.CreateFakeChromeCheckout()
            base_path = os.path.join(test_dir, 'src', 'foo.cc')
            codesearch = CodeSearch(a_path_inside_source_dir=base_path)
            response = codesearch.GetAnnotationsForFile(base_path)

            self.assertTrue(isinstance(response, CompoundResponse))
            self.assertTrue(hasattr(response, 'annotation_response'))

            self.assertGreater(len(mock_opener.requests), 0)
            request = mock_opener.requests.pop()

            self.assertEqual('Python-CodeSearch-Client', request.get_header('User-agent'))

            codesearch = CodeSearch(a_path_inside_source_dir=base_path, user_agent_string='Foo')
            codesearch.GetAnnotationsForFile(base_path)

            self.assertGreater(len(mock_opener.requests), 0)
            request = mock_opener.requests.pop()

            self.assertEqual('Foo', request.get_header('User-agent'))

        finally:
            install_opener(OpenerDirector())
            if test_dir:
                shutil.rmtree(test_dir)


if __name__ == '__main__':
    unittest.main()
