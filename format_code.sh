#!/bin/sh

# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

command -v yapf >/dev/null 2>&1 || {
	echo Please install YAPF if you would like to format code.
	echo https://github.com/google/yapf
	exit 1
}

yapf -i -r .
echo Don\'t forget to \'git commit\' any changed files.

