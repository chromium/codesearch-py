# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.
import unittest

from .client_api import CodeSearch, XrefNode
from .messages import FileSpec, XrefSingleMatch, KytheXrefKind, KytheNodeKind, \
    CodeBlockType, CodeBlock
from .testing_support import InstallTestRequestHandler, DumpCallers


class TestXrefNode(unittest.TestCase):

  def setUp(self):
    InstallTestRequestHandler()

  def tearDown(self):
    DumpCallers()

  def test_simple_xref_lookup(self):
    cs = CodeSearch(source_root='/chrome/')
    sigs = [
        'kythe://chromium?lang=c%2B%2B?path=src/net/http/http_transaction.h#CcZF9ULBJvZBNAWPWKhzZ7xbQc1vl21xLHnAyiu2B3Y%3D',
        'kythe://chromium?lang=c%2B%2B?path=src/net/http/http_transaction.h#HttpTransaction%3Anet%23c%23mw7xVzyyv7D',
        'kythe://chromium?lang=c%2B%2B?path=src/net/http/http_transaction.h#pGcqgSa0Alyp5vsTSxVwKkgW86AW0h7GTXQyJ4ry9IM%3D'
    ]
    sig = sigs[1]

    node = XrefNode.FromSignature(cs, sig)
    members = node.Traverse(KytheXrefKind.EXTENDED_BY)
    self.assertIsInstance(members, list)
    self.assertEqual(5, len(members))
    self.assertIsInstance(members[0], XrefNode)

    display_names = set([m.GetDisplayName() for m in members])
    self.assertSetEqual(
        display_names,
        set([
            'HttpNetworkTransaction', 'FailingHttpTransaction', 'Transaction',
            'MockNetworkTransaction', 'ThrottlingNetworkTransaction'
        ]))

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

  def test_traverse(self):
    cs = CodeSearch(source_root='/src/chrome/')
    cs_file = cs.GetFileInfo('/src/chrome/src/net/http/http_auth.h')
    sig_block = cs_file.FindCodeBlock(
        name='ChooseBestChallenge', type=CodeBlockType.FUNCTION)
    self.assertIsNotNone(sig_block)
    self.assertIsInstance(sig_block, CodeBlock)
    sig = cs_file.GetSignatureForCodeBlock(sig_block)
    self.assertIsNotNone(sig)
    node = XrefNode.FromSignature(cs, sig)

    callers = node.Traverse(KytheXrefKind.CALLED_BY)
    self.assertIsNotNone(callers)
    self.assertIsInstance(callers, list)
    self.assertEqual(2, len(callers))
    self.assertIsInstance(callers[0], XrefNode)
    self.assertIsInstance(callers[1], XrefNode)

    refs = node.Traverse(KytheXrefKind.REFERENCE)
    self.assertIsNotNone(refs)
    self.assertIsInstance(refs, list)
    self.assertEqual(2, len(refs))
    self.assertIsInstance(refs[0], XrefNode)

    decl = node.Traverse(KytheXrefKind.DECLARATION)
    self.assertIsInstance(decl, list)
    self.assertEqual(1, len(decl))


if __name__ == '__main__':
  unittest.main()
