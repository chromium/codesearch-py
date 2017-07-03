#!/bin/sh

# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

# Runs all the tests in the repo.

set -e

echo Running tests using Python2:
python -m unittest discover

# These files have doctests.
python codesearch/language_utils.py
python -m doctest README.md

# Exit if python3 is not installed.
command -v python3 >/dev/null 2>&1

echo Running tests using Python3:
python3 -m unittest discover
python3 codesearch/language_utils.py
python3 -m doctest README.md

