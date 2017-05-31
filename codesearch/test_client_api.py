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
from .testing_support import InstallTestRequestHandler, LastRequest


class TestCodeSearch(unittest.TestCase):

  def setUp(self):
    InstallTestRequestHandler()

  def Touch(self, path):
    with open(path, 'w'):
      pass

  def test_user_agent(self):
    SOURCE_ROOT = '/src/chrome/src'
    TARGET_FILE = '/src/chrome/src/net/http/http_version.h'

    codesearch = CodeSearch(source_root=SOURCE_ROOT)
    response = codesearch.GetAnnotationsForFile(TARGET_FILE)

    self.assertTrue(isinstance(response, CompoundResponse))
    self.assertTrue(hasattr(response, 'annotation_response'))

    request = LastRequest()
    self.assertEqual('Python-CodeSearch-Client',
                     request.get_header('User-agent'))

    codesearch = CodeSearch(source_root=SOURCE_ROOT, user_agent_string='Foo')
    codesearch.GetAnnotationsForFile(TARGET_FILE)

    request = LastRequest()
    self.assertEqual('Foo', request.get_header('User-agent'))


if __name__ == '__main__':
  unittest.main()
