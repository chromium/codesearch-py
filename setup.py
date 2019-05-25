#!/usr/bin/env python

# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from distutils.core import setup

setup(name='codesearch',
      version='0.1',
      description='Chromium Codesearch Library',
      author='Asanka Herath',
      author_email='asanka@chromium.org',
      url='https://github.com/chromium/codesearch',
      packages=['codesearch'],
      scripts=['ccs'])
