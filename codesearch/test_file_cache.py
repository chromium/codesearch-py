# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from __future__ import absolute_import

import os
import shutil
import tempfile
import unittest
from .file_cache import FileCache


class TestFileCache(unittest.TestCase):

  def test_with_no_cache_dir(self):
    try:
      f = FileCache()
      f.put('foo', 'hello'.encode('utf-8'))
      self.assertEqual('hello'.encode('utf-8'), f.get('foo'))
    finally:
      f.close()

  def test_with_cache_dir(self):
    f = None
    g = None
    test_dir = None
    try:
      test_dir = tempfile.mkdtemp()
      test_cache_dir = os.path.join(test_dir, 'cache')
      f = FileCache(cache_dir=test_cache_dir)
      f.put('foo', 'hello'.encode('utf-8'))
      f.close()
      f = None

      g = FileCache(cache_dir=test_cache_dir)
      self.assertEqual('hello'.encode('utf-8'), g.get('foo'))
      g.close()
      g = None

    finally:
      if f:
        f.close()
      if g:
        g.close()
      if test_dir:
        shutil.rmtree(test_dir)


if __name__ == '__main__':
  unittest.main()
