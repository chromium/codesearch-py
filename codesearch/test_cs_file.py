import unittest

from .client_api import CsFile, CodeSearch
from .messages import FileInfo, TextRange, NodeEnumKind


class TestCsFile(unittest.TestCase):

  def test_text_range(self):
    cs = CodeSearch(a_path_inside_source_dir='/src/chrome/src')
    cs_file = cs.GetFileInfo('/src/chrome/src/LICENSE')

    self.assertEqual(
        "// Redistribution and use",
        cs_file.Text(
            TextRange(start_line=3, start_column=1, end_line=3, end_column=25)))

    self.assertEqual(
        "CONTRIBUTORS\n/",
        cs_file.Text(
            TextRange(
                start_line=17, start_column=59, end_line=18, end_column=1)))

    self.assertEqual(
        """CONTRIBUTORS
// "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
//""",
        cs_file.Text(
            TextRange(
                start_line=17, start_column=59, end_line=19, end_column=2)))

  def test_path(self):
    cs = CodeSearch(a_path_inside_source_dir='/src/chrome/src')
    cs_file = cs.GetFileInfo('/src/chrome/src/LICENSE')
    self.assertEqual(cs_file.Path(), 'src/LICENSE')

  def test_display_name(self):
    cs = CodeSearch(a_path_inside_source_dir='/src/chrome/src')
    cs_file = cs.GetFileInfo('/src/chrome/src/net/http/http_auth.h')
    self.assertEqual(
        cs_file.GetDisplayName(
            'cpp:net::class-HttpAuth@chromium/../../net/http/http_auth.h|def'),
        'HttpAuth')


if __name__ == '__main__':
  unittest.main()
