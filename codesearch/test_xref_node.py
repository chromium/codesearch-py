import unittest

from .client_api import CodeSearch, XrefNode
from .messages import FileSpec, XrefSingleMatch, EdgeEnumKind, NodeEnumKind


class TestXrefNode(unittest.TestCase):

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
    self.assertEqual('GURL',related[0].GetDisplayName())
    self.assertEqual(NodeEnumKind.CLASS, related[0].GetXrefKind())


if __name__ == '__main__':
  unittest.main()
