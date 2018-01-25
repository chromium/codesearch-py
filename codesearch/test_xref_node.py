# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.
import unittest

from .client_api import CodeSearch, XrefNode
from .messages import FileSpec, XrefSingleMatch, KytheXrefKind, KytheNodeKind
from .testing_support import InstallTestRequestHandler, DumpCallers


class TestXrefNode(unittest.TestCase):

  def setUp(self):
    InstallTestRequestHandler()

  def tearDown(self):
    DumpCallers()

  def test_simple_xref_lookup(self):
    cs = CodeSearch(source_root='/chrome/')
    sig = cs.GetSignatureForSymbol(
        '/chrome/src/net/http/http_network_transaction.cc',
        'HttpNetworkTransaction')
    self.assertNotEqual(sig, "", "signature lookup failed")

    node = XrefNode.FromSignature(cs, sig)
    members = node.Traverse(KytheXrefKind.EXTENDS)
    self.assertIsInstance(members, list)
    self.assertEqual(3, len(members))
    self.assertIsInstance(members[0], XrefNode)

    display_names = set([m.GetDisplayName() for m in members])
    self.assertSetEqual(display_names,
                        set(["ThrottleDelegate", "Delegate",
                             "HttpTransaction"]))

  def test_related_annotations(self):
    cs = CodeSearch(source_root='/chrome/')
    sig = cs.GetSignatureForSymbol(
        '/chrome/src/net/http/http_network_transaction.h',
        'HttpNetworkTransaction')
    self.assertNotEqual(sig, "", "signature lookup failed")
    node = XrefNode.FromSignature(cs, sig)
    related = node.GetRelatedAnnotations()

    found_class = False
    for annotation in related:
      if annotation.kythe_xref_kind == KytheNodeKind.RECORD_CLASS:
        found_class = True
    self.assertTrue(found_class)

  def test_related_definitions(self):
    cs = CodeSearch(source_root='/chrome/')
    sig = cs.GetSignatureForSymbol(
        '/chrome/src/net/http/http_network_transaction.h',
        'provided_token_binding_key_')
    self.assertNotEqual(sig, "", "signature lookup failed")
    node = XrefNode.FromSignature(cs, sig)
    related = node.GetRelatedDefinitions()

    self.assertEqual(2, len(related))
    definition = related[1]
    self.assertEqual(KytheXrefKind.DEFINITION, definition.single_match.type_id)
    self.assertEqual('ECPrivateKey', definition.GetDisplayName())


if __name__ == '__main__':
  unittest.main()
