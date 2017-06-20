# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from __future__ import print_function

import os
import sys
import hashlib
import json

from email.message import Message

try:
  from urllib.request import urlopen, Request, HTTPSHandler, install_opener, build_opener
  from urllib.response import addinfourl
  from urllib.error import URLError
except ImportError:
  from urllib2 import urlopen, Request, HTTPSHandler, install_opener, build_opener, addinfourl, URLError

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, 'testdata')
RESPONSE_DATA_DIR = os.path.join(TEST_DATA_DIR, 'responses')

disable_network = False

if sys.version_info[0] < 3:

  def GetRequestData(request):
    return bytes(request.get_data()) if request.has_data() else bytes()

  def StringFromBytes(b):
    return str(b)

  def AddDataToRequest(req, d):
    req.add_data(d)

else:

  def GetRequestData(request):
    return request.data if request.data is not None else bytes()

  def StringFromBytes(b):
    return str(b, encoding='utf-8')

  def AddDataToRequest(req, d):
    req.data = d


requests_seen = []


def TestDataDir():
  return TEST_DATA_DIR


def DigestFromRequest(req):
  b = bytearray(req.get_full_url().encode('utf-8'))
  b.extend(GetRequestData(req))
  return hashlib.sha1(b).hexdigest()


class TestHttpHandler(HTTPSHandler):

  def __init__(self):
    pass

  def default_open(self, request):
    return None

  def https_open(self, request):
    global disable_network
    if disable_network:
      raise URLError('Network access is disabled')

    url = request.get_full_url()
    data = GetRequestData(request)
    digest = DigestFromRequest(request)
    response_file_path = os.path.join(RESPONSE_DATA_DIR, digest)

    requests_seen.append(request)

    if os.path.exists(response_file_path):
      f = open(response_file_path, mode='rb')
      m = Message()
      m.add_header('Content-Type', 'application/json')
      resp = addinfourl(f, headers=m, url=url, code=200)
      resp.msg = 'Success'
      resp.code = 200
      return resp

    # The file was not there. Create a missing resource file.
    missing_response_file_path = os.path.join(RESPONSE_DATA_DIR,
                                              '{}.missing'.format(digest))
    with open(missing_response_file_path, mode='wb') as f:
      s = json.dumps({
          "url": url,
          "data": StringFromBytes(data),
          "digest": digest
      })
      f.write(s.encode('utf-8'))

    raise URLError(
        'URL is not cached. Created missing request record: {}.missing'.format(
            digest))

  def http_open(self, request):
    return self.https_open(request)


def InstallTestRequestHandler():
  """Any test that makes network requests to https://cs.codesearch.com (i.e.
    those that rely on making network requests) should call this function in
    their respective setUp() functions.
   
    Doing so installs a test request handler that will fail the first time it
    is called with a new URL, but will write out a file indicating which URL
    requests were seen. One can then run the testing_support.py script directly
    which resolves the URL requests, and adds a file to the |testdata|
    directory containing the expected response data.

    This mechanism prevents the tests from making direct network requests.
    """
  install_opener(build_opener(TestHttpHandler()))


def DisableNetwork():
  global disable_network
  disable_network = True


def EnableNetwork():
  global disable_network
  disable_network = False


def LastRequest():
  if len(requests_seen) > 0:
    return requests_seen.pop()


if __name__ == '__main__':

  # Attempt to resolve all missing resource requests.

  resolved_count = 0

  for name in os.listdir(RESPONSE_DATA_DIR):
    if not name.endswith('.missing'):
      continue

    print('Resolving {}'.format(name))

    with open(os.path.join(RESPONSE_DATA_DIR, name), mode='r') as f:
      s = f.read()
      o = json.loads(s)

    url, data, digest = o["url"], o["data"], o["digest"]
    req = Request(url=url)
    if data != '':
      AddDataToRequest(req, data.encode('utf-8'))

    try:
      response = urlopen(req, timeout=3)
      result = response.read()

      with open(os.path.join(RESPONSE_DATA_DIR, digest), 'wb') as f:
        f.write(result)

      os.unlink(os.path.join(RESPONSE_DATA_DIR, name))

      print('   Resolved. Wrote {}'.format(digest))
      resolved_count += 1

    except Exception as e:
      print('   FAILED.:{} while looking at {}'.format(str(e), name))
      raise e

  if resolved_count > 0:
    print('\nDon\'t forget to \'git add\' the new files and commit them.')
