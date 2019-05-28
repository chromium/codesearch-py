# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

import sys

if sys.version_info[0] < 3:

    def StringFromBytes(b):
        return str(b)

    def IsString(s):
        return isinstance(s, basestring)  # noqa

    def ToStringSafe(s):
        if isinstance(s, str):
            return s
        if isinstance(s, unicode):  # noqa
            return s.encode('utf-8')
        return str(s)

else:

    def StringFromBytes(b):
        return str(b, encoding='utf-8')

    def IsString(s):
        return isinstance(s, str)

    def ToStringSafe(s):
        if isinstance(s, str):
            return s
        return str(s)
