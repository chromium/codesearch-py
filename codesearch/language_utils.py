# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

import re

TOKEN_BOUNDARIES = r'[-!"#%&\'()*+,./:;<=>?\[\\\]^{|}~ ]'


def CppIdentifierTokens(s):
    """Returns an array of C++ identifier tokens in |s|.

    >>> CppIdentifierTokens('abc')
    ['abc']

    >>> CppIdentifierTokens('abc::def')
    ['abc', 'def']

    >>> CppIdentifierTokens('abc def')
    ['abc', 'def']

    >>> CppIdentifierTokens('abc[def]ghi')
    ['abc', 'def', 'ghi']

    >>> CppIdentifierTokens('a&(b*c)[d^e/f]g{}h|i')
    ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i']
    """
    return [token for token in re.split(TOKEN_BOUNDARIES, s) if token]


def MatchSymbolSuffix(haystack_string, needle_string):
    """Returns true if the symbols in |haystack_string| ends with the symbols in
|needle_string|.

    >>> MatchSymbolSuffix("abc::def", "def")
    True

    >>> MatchSymbolSuffix("abc::def", "abc:def")
    True

    >>> MatchSymbolSuffix("xabc::def", "abc:def")
    False

    >>> MatchSymbolSuffix("foo|bar::baz", "bar baz")
    True

    >>> MatchSymbolSuffix("foo|bar::baz|quux", "bar baz")
    False

    >>> MatchSymbolSuffix("foo|bar  baz", "bar baz")
    True
    """
    haystack = CppIdentifierTokens(haystack_string)
    needle = CppIdentifierTokens(needle_string)
    return haystack[-len(needle):] == needle


class SymbolSuffixMatcher(object):
    """Like MatchSymbolSuffix, but caches preprocessed |needle|.

    >>> SymbolSuffixMatcher("def").Match("abc::def")
    True

    >>> SymbolSuffixMatcher("abc:def").Match("xabc::def")
    False

    >>> SymbolSuffixMatcher("abc::def").Match("abc")
    False

    >>> SymbolSuffixMatcher("abc::def").Match("a:abc def")
    True

    >>> SymbolSuffixMatcher("abc::def").Match("aabc def")
    False
    """
    def __init__(self, needle):
        self.needle = CppIdentifierTokens(needle)

    def Match(self, haystack):
        return CppIdentifierTokens(haystack)[-len(self.needle):] == self.needle


def IsIdentifier(s):
    """Returns True if |s| is a valid C++ identifier.

    >>> IsIdentifier('abc')
    True

    >>> IsIdentifier('abc ')
    False

    >>> IsIdentifier('abc:')
    False
    """
    return CppIdentifierTokens(s)[0] == s


# For running doctests.
if __name__ == "__main__":
    import doctest
    doctest.testmod()
