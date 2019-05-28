# Copyright 2018 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

import unittest

from .client_api import CodeSearch
from .messages import CodeBlock, CodeBlockType
from .testing_support import InstallTestRequestHandler


class TestCodeBlocks(unittest.TestCase):
    def setUp(self):
        InstallTestRequestHandler()

    def test_get_codeblock(self):
        cs = CodeSearch(source_root='/src/chrome/')
        cs_file = cs.GetFileInfo('/src/chrome/src/net/http/http_auth.h')
        block = cs_file.GetCodeBlock()
        self.assertIsInstance(block, CodeBlock)
        self.assertNotEqual(0, len(block.child))
        self.assertIsInstance(block.child[0], CodeBlock)

    def test_find(self):
        cs = CodeSearch(source_root='/src/chrome/')
        cs_file = cs.GetFileInfo('/src/chrome/src/net/http/http_auth.h')
        block = cs_file.FindCodeBlock()
        self.assertIsNotNone(block)
        self.assertIsInstance(block, CodeBlock)
        self.assertEqual(block, cs_file.GetCodeBlock(), "should match root")

        block = cs_file.FindCodeBlock("net", CodeBlockType.NAMESPACE)
        self.assertIsNotNone(block)
        self.assertEqual(block.name, "net")

        block = cs_file.FindCodeBlock("HandleChallengeResponse",
                                      CodeBlockType.FUNCTION)
        self.assertIsNotNone(block)
        self.assertEqual(block.name, "HandleChallengeResponse")


if __name__ == '__main__':
    unittest.main()
