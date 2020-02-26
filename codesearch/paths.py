# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

import os
import re

# Type checking
try:
    from typing import List, Tuple, Dict
except ImportError:
    pass


class NoSourceRootError(Exception):
    """Exception raise when the CodeSearch library can't determine the location
of the local Chromium checkout."""
    pass


def GetPackageRelativePath(filename):
    """GetPackageRelativePath returns the path to |filename| relative to the root
  of the package as determined by GetSourceRoot()."""

    return os.path.relpath(filename, GetSourceRoot(filename)).replace('\\', '/')


def IsChromiumRoot(path):
    """Returns True if |path| exists and is the root of the Chromium source
    tree. The root of the Chromium tree is the directory above 'src'. I.e.
    '<root_path>/src/.gn' is the top level .gn file."""
    paths_to_check = ['.gn', 'chrome', 'content', 'net']
    return all(
        os.path.exists(os.path.join(path, 'src', p)) for p in paths_to_check)


def GetSourceRoot(filename):
    """Try to determine the root of the package which contains |filename|.

Root of the package for Chromium is the directory *above* src. I.e.
<root_path>/src/.gn is the top level .gn file.

The current heuristic attempts to determine the root of the Chromium source
tree by searching up the directory hierarchy until we find a directory
containing src/.gn.
"""

    # If filename is not absolute, then we are going to assume that it is
    # relative to the current directory.
    if not os.path.isabs(filename):
        filename = os.path.abspath(filename)
    if not os.path.exists(filename):
        raise NoSourceRootError('File not found: {}'.format(filename))
    source_root = os.path.dirname(filename)
    while True:
        if IsChromiumRoot(source_root):
            return source_root

        new_package_root = os.path.dirname(source_root)
        if new_package_root == source_root:
            raise NoSourceRootError("Can't determine package root")
        source_root = new_package_root


DEFAULT_REMOTE_OUT = '/out/Debug/'


class PathTransformer(object):
    def __init__(self, source_root, mappings):
        # type: (PathTransformer, str, List[Tuple[str,str]]) -> None
        """Initialize a PathTransformer.

        |source_root| is the root of the Chromium source tree.

        |mappings| is an ordered list of tuples where the each tuple consists of
        a regex and a string. The regex is one that matches a path of the form
        "/out/foo/" (note the leading and trailing '/'). The string is the
        target path also of the form "/out/foo/". Each tuple is used to map a
        localoutput directory to one that is understood by the CodeSearch
        backend.
        """

        out_dir = os.path.join(source_root, 'src', 'out')

        def _DirEntryToTime(d):
            # type: (str) -> float
            return os.stat(os.path.join(out_dir, d)).st_mtime

        def _DirEntryIsDir(d):
            # type: (str) -> bool
            return os.path.isdir(os.path.join(out_dir, d))

        self.source_root = source_root
        if not os.path.exists(out_dir):
            self.local_to_remote = {}  # type: Dict[str, str]
            self.remote_to_local = {}  # type: Dict[str, str]
            return

        build_dirs = sorted(filter(_DirEntryIsDir, os.listdir(out_dir)),
                            key=_DirEntryToTime,
                            reverse=True)

        # build_dirs is now a list of strings, ordered by their corresponding
        # mtime, of subdirectories under out.

        local_to_remote = {}  # type: Dict[str, str]
        remote_to_local = {}  # type: Dict[str, str]

        for d in build_dirs:
            candidate = '/out/{}/'.format(d)
            for (pattern, target) in mappings:
                # The target must start and end with a slash.
                assert target[-1] == '/'
                assert target[0] == '/'

                if re.match(pattern, candidate) is not None:
                    if candidate not in local_to_remote:
                        local_to_remote[candidate] = target
                    if target not in remote_to_local:
                        remote_to_local[target] = candidate

        self.local_to_remote = local_to_remote
        self.remote_to_local = remote_to_local

    def LocalToRemote(self, source):
        # type: (str) -> str

        source_abs = os.path.abspath(source)
        source_rel = os.path.relpath(source_abs,
                                     start=self.source_root).replace('\\', '/')

        out = source_rel
        for (local_fragment, remote_fragment) in self.local_to_remote.items():
            out = out.replace(local_fragment, remote_fragment, 1)

        return out

    def RemoteToLocal(self, source):
        # type: (str) -> str

        # This is the only case where this can work.
        assert source.startswith('src/')

        remote = source
        if '/out/' in remote:
            found = False
            for (remote_fragment,
                 local_fragment) in self.remote_to_local.items():
                if remote_fragment in remote:
                    remote = remote.replace(remote_fragment, local_fragment)
                    found = True

            if not found and DEFAULT_REMOTE_OUT in self.remote_to_local:
                remote = re.sub('/out/[^/]*/',
                                self.remote_to_local[DEFAULT_REMOTE_OUT],
                                remote)

        return os.path.join(self.source_root, remote)
