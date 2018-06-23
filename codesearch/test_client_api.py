# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from __future__ import absolute_import

import os
import shutil
import socket
import sys
import tempfile
import tempfile
import unittest

from .client_api import CodeSearch, XrefNode
from .messages import CompoundRequest, CompoundResponse, FileInfoRequest, \
        FileInfoResponse, KytheNodeKind, KytheXrefKind, NodeEnumKind, \
        CallGraphRequest, CallGraphResponse, Node
from .testing_support import InstallTestRequestHandler, LastRequest, \
        TestDataDir, DisableNetwork, EnableNetwork, DumpCallers

SOURCE_ROOT = '/src/chrome/'


class TestCodeSearch(unittest.TestCase):

  def setUp(self):
    InstallTestRequestHandler()

  def tearDown(self):
    DumpCallers()

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
    self.assertIsNotNone(request)
    self.assertTrue(
        request.get_header('User-agent').startswith('Python-CodeSearch-Client'))

    codesearch = CodeSearch(source_root=SOURCE_ROOT, user_agent_string='Foo')
    codesearch.GetAnnotationsForFile(TARGET_FILE)

    request = LastRequest()
    self.assertEqual('Foo', request.get_header('User-agent'))

  def test_get_signatures_for_symbol(self):
    TARGET_FILE = '/src/chrome/src/base/metrics/field_trial.h'
    cs = CodeSearch(source_root=SOURCE_ROOT)

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'FieldTrial')
    self.assertEqual(7, len(signatures))

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'FieldTrial',
                                           KytheNodeKind.RECORD_CLASS)
    self.assertEqual(2, len(signatures))

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'FieldTrial',
                                           KytheNodeKind.FUNCTION_CONSTRUCTOR)
    self.assertEqual(3, len(signatures))

  def test_gob_revision(self):
    TARGET_FILE = '/src/chrome/src/README.md'
    cs = CodeSearch(source_root=SOURCE_ROOT)

    self.assertEqual('', cs.GetRevision())
    fi = cs.GetFileInfo(TARGET_FILE)
    self.assertEqual(40, len(cs.GetRevision()))

  def test_get_signature_for_symbol(self):
    # These values are likely to change pretty often. So this test will likely
    # fail each time we refresh the test data corpus. If that happens, open up
    # field_trial.h in https://cs.chromium.org and verify that the tickets that
    # get picked up by the API make sense.

    TARGET_FILE = '/src/chrome/src/base/metrics/field_trial.h'
    cs = CodeSearch(source_root=SOURCE_ROOT)

    # A class definition. The name appears numerous times in the file.
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'FieldTrial'),
        'kythe://chromium?lang=c%2B%2B?path=src/base/metrics/field_trial.h#FieldTrial%3Abase%23c%23cGxmCcu4cj8'
    )

    # An enum defined within the class.
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'RandomizationType'),
        'kythe://chromium?lang=c%2B%2B?path=src/base/metrics/field_trial.h#sffJe7wAnF2I9rS3Yd%2B8%2FcTJryczxcrLGG1xREnxhKU%3D'
    )

    # A struct field.
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'pickle_size'),
        'kythe://chromium?lang=c%2B%2B?path=src/base/metrics/field_trial.h#5j4rU1ruIZUCxPWsXAOsTjOIQPiJdmvDwkVVxoqsqT8%3D'
    )

    # A parameter to a function.
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'override_entropy_provider'),
        'kythe://chromium?lang=c%2B%2B?path=src/base/metrics/field_trial.h#lAGs5biYnnRyEje0KIGqTe4V5ZkjOY6%2B7I2jg8Jlxdk%3D'
    )

    # A builtin type.
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'uint32_t'),
        'kythe:?lang=c%2B%2B#9Q1Qo0dt%2BgETZA3AE5IlwTBVpnGb9lT0KTUS8YtMp7E%3D')

    # The absence of the "md5" parameter to the annotation_request was
    # puzzlingly causing the annotations for this file to be offset by a
    # constant amount.
    self.assertEqual(
        cs.GetSignatureForSymbol(
            '/src/chrome/src/chrome/browser/chrome_content_browser_client.cc',
            'IsURLWhitelisted'),
        'kythe://chromium?lang=c%2B%2B?path=src/chrome/browser/chrome_content_browser_client.cc#Fwd4bLZKrcXZ1sb8TmkFDxFtI76Z3V%2BWSTgS%2Bov3Ag8%3D'
    )

  def test_search_for_symbol(self):
    cs = CodeSearch(source_root='.')

    signatures = cs.SearchForSymbol('base::FieldTrial$', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))
    self.assertTrue(isinstance(signatures[0], XrefNode))

    signatures = cs.SearchForSymbol('URLRequestJob', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))
    self.assertTrue(isinstance(signatures[0], XrefNode))

    signatures = cs.SearchForSymbol('BackgroundSyncService::Register',
                                    NodeEnumKind.METHOD)
    self.assertEqual(1, len(signatures))

    signatures = cs.SearchForSymbol(
        'BackgroundSyncService::Register',
        NodeEnumKind.METHOD,
        return_all_results=True)
    self.assertEqual(2, len(signatures))

  def test_get_call_graph(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('HttpAuth::ChooseBestChallenge',
                                    NodeEnumKind.FUNCTION)
    self.assertEqual(1, len(signatures))
    self.assertIsInstance(signatures[0], XrefNode)
    cg_response = cs.GetCallGraph(signature=signatures[0].GetSignature())
    self.assertIsInstance(cg_response, CompoundResponse)
    self.assertIsInstance(cg_response.call_graph_response[0], CallGraphResponse)
    self.assertIsInstance(cg_response.call_graph_response[0].node, Node)

  def test_fixed_cache(self):
    fixed_cache_dir = os.path.join(TestDataDir(), 'fixed_cache')

    # There are no resources corresponding to the requests that are going to be
    # made under this test. Instead there are cached resources. The cache
    # expiration is set for 10 years, which should be long enough for anybody.

    # Note that whenever the request parameters change, the fixed cache will
    # stop working. Hence we need to regenerate the test data. To do that:
    #
    # - Remove all the files from testdata/fixed_cache/*
    # - Comment out the DisableNetwork() call below.
    # - Run the test in rebaseline mode.
    # - *DONT* add any of the new cache entries added to testdata/resource/*
    # - *DO* add the new files that show up in testdata/fixed_cache/*

    DisableNetwork()
    cs = CodeSearch(
        source_root='.',
        should_cache=True,
        cache_dir=fixed_cache_dir,
        cache_timeout_in_seconds=10 * 365 * 24 * 60 * 60)
    try:
      signatures = cs.SearchForSymbol(
          'URLRequestHttpJob', NodeEnumKind.CLASS, max_results_to_analyze=50)
    finally:
      EnableNetwork()
      cs.TeardownCache()
    self.assertEqual(1, len(signatures))

  def test_with_cache_dir(self):
    test_dir = tempfile.mkdtemp()
    try:
      cs = CodeSearch(source_root='.', should_cache=True, cache_dir=test_dir)
      try:
        signatures = cs.SearchForSymbol('URLRequestJob', NodeEnumKind.CLASS)
      finally:
        cs.TeardownCache()
      self.assertEqual(1, len(signatures))

      entries = os.listdir(test_dir)
      # Test the count of entries. The exact set of entries will change from
      # time to time due to changes in queries and repsonses.
      self.assertEqual(3, len(entries))

    finally:
      shutil.rmtree(test_dir)


if __name__ == '__main__':
  unittest.main()
