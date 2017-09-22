#!/bin/bash

# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

set -e

remove=0
skip=1

while getopts rs opt; do
  case $opt in
    r) remove=1 ;;
    s) skip=0 ;;
    *) exit 1
  esac
done

if [[ ( $remove = 0 ) && ( $skip = 1 ) ]]; then
  cat <<EOF
You are about to purge all files from codesearch/testdata/responses/* and
replace them with fresh files from the current CodeSearch index. This is a
destructive operation. If you really meant to do this, rerun this command with
a '-r' or '-s' option.

The script will remove all the cached response files and rerun the tests.
Whenever one of the tests makes a request for a resource, that test will fail
and a *.missing file will be created. This .missing file contains all the
details necessary to make a network request for teh missing resource. Then the
script invokes codesearch/testing_support.py to fetch the missing resource.
This operation will repeat until there are no more missing resources.

Assuming the tests are successful, then you'll end up with a bunch of files
deleted from the git index, and also a bunch of files that were added. All the
tests should pass. If not, you'd need to figure out what's going on.
EOF
  exit 1
fi

if [ $remove = 1 ]; then
  git rm codesearch/testdata/responses/\* || echo No files in index.
  rm codesearch/testdata/responses/* || echo No unresolved files in cache.
fi

set +e

files_added=0

./run_tests.sh
while [ $? != 0 ]; do
  echo Attempting to resolve missing resources.
  python codesearch/testing_support.py
  if [ $? != 0 ]; then
    exit 1
  fi
  files_added=1
  ./run_tests.sh
done

if [ $files_added == 1 ]; then
  git add codesearch/testdata/responses
fi

