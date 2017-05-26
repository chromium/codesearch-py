import unittest

from .client_api import CodeSearch, XrefNode
from .messages import FileSpec, XrefSingleMatch, EdgeEnumKind


class TestXrefNode(unittest.TestCase):

  def test_simple_xref_lookup(self):

    cs = CodeSearch(a_path_inside_source_dir='/src/chrome/src')
    sig = cs.GetSignatureForSymbol(
        '/src/chrome/src/net/http/http_network_transaction.cc',
        'HttpNetworkTransaction')
    self.assertNotEqual(sig, "", "signature lookup failed")

    node = XrefNode.FromSignature(cs, sig)
    methods = node.GetEdges(EdgeEnumKind.DECLARES)
    self.assertTrue(methods)


if __name__ == '__main__':
  unittest.main()
