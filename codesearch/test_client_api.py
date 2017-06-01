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

from .client_api import CodeSearch, XrefNode
from .messages import CompoundRequest, CompoundResponse, FileInfoRequest, FileInfoResponse, NodeEnumKind, EdgeEnumKind
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

    self.assertEqual(1, len(signatures))
    self.assertTrue(isinstance(signatures[0], XrefNode))

    signatures = cs.SearchForSymbol('URLRequestJob', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))
    self.assertTrue(isinstance(signatures[0], XrefNode))

  def test_figment_display_name(self):
    cs = CodeSearch(source_root='.')

    signatures = cs.SearchForSymbol('File', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    file_class = signatures[0]
    declarations = file_class.GetEdges(EdgeEnumKind.DECLARES)

    ed = [
        d for d in declarations
        if ' created_' in d.single_match.line_text and
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
    self.assertEqual('std::unique_ptr<char, base::FreeDeleter>',
                     rd_type.GetDisplayName())

  def test_figment_display_name_3(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('PickledIOBuffer', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    gb_class = signatures[0]
    declarations = gb_class.GetEdges(EdgeEnumKind.DECLARES)

    p = [
        d for d in declarations
        if ' pickle_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    p_type = p.GetEdges(EdgeEnumKind.HAS_TYPE)
    self.assertEqual(0, len(p_type))

    reldefns = p.GetRelatedDefinitions()
    self.assertEqual(2, len(reldefns))

    class_defn = [d for d in reldefns
                  if d.GetXrefKind() == NodeEnumKind.CLASS][0]
    self.assertEqual('Pickle', class_defn.GetDisplayName())

  def test_get_type_1(self):
    cs = CodeSearch(source_root='.')

    signatures = cs.SearchForSymbol('File', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    file_class = signatures[0]
    declarations = file_class.GetEdges(EdgeEnumKind.DECLARES)

    ed = [
        d for d in declarations
        if ' created_' in d.single_match.line_text and
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
    self.assertEqual('std::unique_ptr<char, base::FreeDeleter>',
                     rd_type.GetDisplayName())

  def test_get_type_3(self):
    cs = CodeSearch(source_root='.')
    signatures = cs.SearchForSymbol('PickledIOBuffer', NodeEnumKind.CLASS)
    self.assertEqual(1, len(signatures))

    gb_class = signatures[0]
    declarations = gb_class.GetEdges(EdgeEnumKind.DECLARES)

    p = [
        d for d in declarations
        if ' pickle_' in d.single_match.line_text and
        d.GetXrefKind() == NodeEnumKind.FIELD
    ][0]
    p_type = p.GetType()
    self.assertEqual('Pickle', p_type.GetDisplayName())


if __name__ == '__main__':
  unittest.main()
