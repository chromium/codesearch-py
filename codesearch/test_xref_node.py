# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.
import unittest

from .client_api import CodeSearch, XrefNode
from .messages import FileSpec, XrefSingleMatch, EdgeEnumKind, NodeEnumKind
from .testing_support import InstallTestRequestHandler


class TestXrefNode(unittest.TestCase):

  def setUp(self):
    InstallTestRequestHandler()

  def test_simple_xref_lookup(self):
    cs = CodeSearch(source_root='/src/chrome/')
    sig = cs.GetSignatureForSymbol(
        '/src/chrome/src/net/http/http_network_transaction.cc',
        'HttpNetworkTransaction')
    self.assertNotEqual(sig, "", "signature lookup failed")

    node = XrefNode.FromSignature(cs, sig)
    members = node.GetEdges(EdgeEnumKind.DECLARES)
    self.assertTrue(members)

    saw_test_case_1 = False
    saw_test_case_2 = False
    saw_test_case_3 = False

    # file_info_request, annotation_request, xref_search_request
    self.assertEqual(3, cs.stats.cache_misses)

    for member in members:

      if member.GetSignature(
      ) == 'cpp:net::class-HttpNetworkTransaction::before_headers_sent_callback_@chromium/../../net/http/http_network_transaction.h|def':
        saw_test_case_1 = True
        self.assertEqual(NodeEnumKind.FIELD, member.GetXrefKind())
        self.assertEqual('before_headers_sent_callback_',
                         member.GetDisplayName())

      if member.GetSignature(
      ) == 'cpp:net::class-HttpNetworkTransaction::RestartWithCertificate(net::X509Certificate *, net::SSLPrivateKey *, const base::Callback<void (int), base::internal::CopyMode::Copyable, base::internal::RepeatMode::Repeating> &)@chromium/../../net/http/http_network_transaction.cc|def':
        saw_test_case_2 = True
        self.assertEqual(NodeEnumKind.METHOD, member.GetXrefKind())

      if member.GetSignature(
      ) == 'cpp:net::class-HttpNetworkTransaction::HandleIOError(int)@chromium/../../net/http/http_network_transaction.h|decl':
        saw_test_case_3 = True
        self.assertEqual(NodeEnumKind.METHOD, member.GetXrefKind())

    self.assertTrue(saw_test_case_1)
    self.assertTrue(saw_test_case_2)
    self.assertTrue(saw_test_case_3)

    # Previous 3 requests + (file_info_request, annotation_request) for http_network_transaction.h
    self.assertEqual(5, cs.stats.cache_misses)

  def test_related_annotations(self):
    cs = CodeSearch(source_root='/src/chrome/')
    node = XrefNode.FromSignature(
        cs,
        'cpp:net::class-HttpNetworkTransaction::url_@chromium/../../net/http/http_network_transaction.h|def',
        '/src/chrome/src/net/http/http_network_transaction.h')
    related = node.GetRelatedAnnotations()

    found_class = False
    for annotation in related:
      if annotation.xref_kind == NodeEnumKind.CLASS:
        found_class = True
    self.assertTrue(found_class)

  def test_related_definitions(self):
    cs = CodeSearch(source_root='/src/chrome/')
    node = XrefNode.FromSignature(
        cs,
        'cpp:net::class-HttpNetworkTransaction::url_@chromium/../../net/http/http_network_transaction.h|def',
        '/src/chrome/src/net/http/http_network_transaction.h')
    related = node.GetRelatedDefinitions()

    self.assertEqual(1, len(related))
    definition = related[0]
    self.assertTrue(definition.single_match.grok_modifiers.definition)
    self.assertEqual('GURL', definition.GetDisplayName())
    self.assertEqual(NodeEnumKind.CLASS, definition.GetXrefKind())

  def test_related_definitions_2(self):
    cs = CodeSearch(source_root='.')
    node = XrefNode.FromSignature(
        cs,
        'cpp:net::class-URLRequestContext@chromium/../../net/url_request/url_request_context.h|def',
        'src/net/url_request/url_request_context.h')
    edges = node.GetEdges(EdgeEnumKind.DECLARES)

    # Pick the line that looks like:   URLRequestBackoffManager* backoff_manager_;
    p = [
        e for e in edges
        if e.single_match.line_text.endswith(' backoff_manager_;')
    ][0]
    related = p.GetRelatedDefinitions()

    self.assertLessEqual(2, len(related))
    for r in related:
      self.assertTrue(hasattr(r.single_match, 'line_text'))

  def test_get_all_edges(self):
    cs = CodeSearch(source_root='/src/chrome/')
    node = XrefNode.FromSignature(
        cs,
        'cpp:net::class-HttpNetworkTransaction::RestartWithCertificate(net::X509Certificate *, net::SSLPrivateKey *, const base::Callback<void (int), base::internal::CopyMode::Copyable, base::internal::RepeatMode::Repeating> &)@chromium/../../net/http/http_network_transaction.cc|def',
        '/src/chrome/src/net/http/http_network_transaction.cc')
    all_edges = node.GetAllEdges(max_num_results=10)

    # Definitely more than 10 edges here. But can't check for an exact number
    # due to some results getting elided.
    self.assertLess(0, len(all_edges))


if __name__ == '__main__':
  unittest.main()
