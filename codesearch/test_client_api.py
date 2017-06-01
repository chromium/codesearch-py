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
from .messages import CompoundRequest, CompoundResponse, FileInfoRequest, FileInfoResponse, NodeEnumKind
from .testing_support import InstallTestRequestHandler, LastRequest

SOURCE_ROOT = '/src/chrome/'


class TestCodeSearch(unittest.TestCase):

  def setUp(self):
    InstallTestRequestHandler()

  def Touch(self, path):
    with open(path, 'w'):
      pass

  def test_user_agent(self):
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

  def test_get_signatures_for_symbol(self):
    TARGET_FILE = '/src/chrome/src/base/files/file.h'
    cs = CodeSearch(source_root=SOURCE_ROOT)

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'File')
    self.assertEqual(8, len(signatures))

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'File',
                                           NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'File',
                                           NodeEnumKind.CONSTRUCTOR)
    self.assertEqual(6, len(signatures))


  def test_search_for_symbol(self):
      cs = CodeSearch(source_root='.')

      signatures = cs.SearchForSymbol('File', NodeEnumKind.CLASS)

      print(signatures)
      self.assertEqual(1, len(signatures))

      signatures = cs.SearchForSymbol('URLRequestJob', NodeEnumKind.CLASS)
      print(signatures)
      self.assertEqual(1, len(signatures))


if __name__ == '__main__':
  unittest.main()
