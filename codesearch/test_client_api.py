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
from .messages import CompoundRequest, CompoundResponse, FileInfoRequest, FileInfoResponse, NodeEnumKind, EdgeEnumKind
from .testing_support import InstallTestRequestHandler, LastRequest, TestDataDir, DisableNetwork, EnableNetwork

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
    TARGET_FILE = '/src/chrome/src/base/metrics/field_trial.h'
    cs = CodeSearch(source_root=SOURCE_ROOT)

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'FieldTrial')
    self.assertEqual(4, len(signatures))

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'FieldTrial',
                                           NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    signatures = cs.GetSignaturesForSymbol(TARGET_FILE, 'FieldTrial',
                                           NodeEnumKind.CONSTRUCTOR)
    self.assertEqual(2, len(signatures))

  def test_get_signature_for_symbol(self):

    TARGET_FILE = '/src/chrome/src/base/metrics/field_trial.h'
    cs = CodeSearch(source_root=SOURCE_ROOT)

    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'RandomizationType'),
        'cpp:base::class-FieldTrial::enum-RandomizationType@chromium/../../base/metrics/field_trial.h|def'
    )
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'pickle_size'),
        'cpp:base::class-FieldTrial::class-FieldTrialEntry::pickle_size@chromium/../../base/metrics/field_trial.h|def'
    )
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'randomization_seed'),
        'cpp:base::class-FieldTrial::class-EntropyProvider::GetEntropyForTrial(const std::__1::basic_string<char> &, unsigned int)-const::param-randomization_seed@chromium/../../base/metrics/field_trial.h:4960|decl'
    )
    self.assertEqual(
        cs.GetSignatureForSymbol(TARGET_FILE, 'uint32_t'),
        'cpp:uint32_t@chromium/../../build/linux/debian_jessie_amd64-sysroot/usr/include/stdint.h|def'
    )

  def test_search_for_symbol(self):
    cs = CodeSearch(source_root='.')

    signatures = cs.SearchForSymbol('FieldTrial$', NodeEnumKind.CLASS)
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

  def test_figment_display_name(self):
    cs = CodeSearch(source_root='.')

    signatures = cs.SearchForSymbol('FieldTrial$', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    file_class = signatures[0]
    declarations = file_class.GetEdges(EdgeEnumKind.DECLARES)

    ed = [
        d for d in declarations
        if ' enable_field_trial_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    ed_type = ed.GetEdges(EdgeEnumKind.HAS_TYPE)[0]
    self.assertEqual('bool', ed_type.GetDisplayName())

  def test_figment_display_name_2(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('GrowableIOBuffer', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    gb_class = signatures[0]
    declarations = gb_class.GetEdges(EdgeEnumKind.DECLARES)

    rd = [
        d for d in declarations
        if ' real_data_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    rd_type = rd.GetEdges(EdgeEnumKind.HAS_TYPE)[0]
    self.assertEqual('std::__1::unique_ptr<char, base::FreeDeleter>',
                     rd_type.GetDisplayName())

  def test_figment_display_name_3(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('GrowableIOBuffer', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    gb_class = signatures[0]
    declarations = gb_class.GetEdges(EdgeEnumKind.DECLARES)

    p = [
        d for d in declarations
        if ' real_data_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]

    reldefns = p.GetRelatedDefinitions()
    self.assertEqual(5, len(reldefns))

    class_defn = [
        d for d in reldefns
        if hasattr(d.single_match.grok_modifiers, 'is_figment') and
        d.single_match.grok_modifiers.is_figment
    ][0]
    self.assertEqual('std::__1::unique_ptr<char, base::FreeDeleter>',
                     class_defn.GetDisplayName())

  def test_get_type_1(self):
    cs = CodeSearch(source_root='.')

    signatures = cs.SearchForSymbol('FieldTrial$', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    file_class = signatures[0]
    declarations = file_class.GetEdges(EdgeEnumKind.DECLARES)

    ed = [
        d for d in declarations
        if ' enable_field_trial_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    ed_type = ed.GetType()
    self.assertTrue(ed_type)
    self.assertEqual('bool', ed_type.GetDisplayName())

  def test_get_type_2(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('GrowableIOBuffer', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    gb_class = signatures[0]
    declarations = gb_class.GetEdges(EdgeEnumKind.DECLARES)

    rd = [
        d for d in declarations
        if ' real_data_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    rd_type = rd.GetType()
    self.assertTrue(rd_type)
    self.assertEqual('std::__1::unique_ptr<char, base::FreeDeleter>',
                     rd_type.GetDisplayName())

  def test_get_type_3(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('base::AtExitManager', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    gb_class = signatures[0]
    declarations = gb_class.GetEdges(EdgeEnumKind.DECLARES)

    p = [
        d for d in declarations
        if ' next_manager_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    p_type = p.GetType()
    self.assertEqual('base::AtExitManager*', p_type.GetDisplayName())

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
