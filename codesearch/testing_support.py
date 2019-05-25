# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

from __future__ import print_function

import hashlib
import inspect
import json
import os
import sys

from email.message import Message

# Type annotations are only used during static analysis phase.
try:
    from typing import Dict
except ImportError:
    pass

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, 'testdata')
RESPONSE_DATA_DIR = os.path.join(TEST_DATA_DIR, 'responses')

disable_network = False

if sys.version_info < (3, 0):
    # Python 2
    from urllib2 import urlopen, Request, HTTPSHandler, install_opener, \
        build_opener, addinfourl, URLError
    from urlparse import urlparse, parse_qsl, urlunparse

    def GetRequestData(request):
        return bytes(request.get_data()) if request.has_data() else bytes()

    def StringFromBytes(b):
        return str(b)

    def AddDataToRequest(req, d):
        req.add_data(d)

    def GetLocationFromFrame(frame):
        _, fname, line, fn, _, _ = frame
        return (fname, line, fn)

else:
    # Python 3
    from urllib.request import urlopen, Request, HTTPSHandler, install_opener, \
        build_opener
    from urllib.response import addinfourl
    from urllib.error import URLError
    from urllib.parse import urlparse, parse_qsl, urlunparse

    def GetRequestData(request):
        return request.data if request.data is not None else bytes()

    def StringFromBytes(b):
        return str(b, encoding='utf-8')

    def AddDataToRequest(req, d):
        req.data = d

    def GetLocationFromFrame(frame):
        return (frame.filename, frame.lineno, frame.function)


class RequestInfo(object):

    FILE_PREFIXES = ['test_', 'client_api.py']

    def __init__(self, url, data):
        self.callers = []
        self.url = url
        self.data = data

    def AddCallers(self):
        frames = inspect.stack()
        for frame in frames:
            filename, lineno, function = GetLocationFromFrame(frame)
            basename = os.path.basename(filename)
            track = False
            for prefix in RequestInfo.FILE_PREFIXES:
                if basename.startswith(prefix):
                    track = True
                    break
            if not track:
                continue
            self.callers.append((filename, lineno, function))


last_request = None

# A map from the request digest string to RequestInfo.
requests_seen = {}  # type: Dict[str, RequestInfo]


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
        filename = digest + ".json"
        response_file_path = os.path.join(RESPONSE_DATA_DIR, filename)

        global requests_seen
        if digest not in requests_seen:
            requests_seen[digest] = RequestInfo(url, data)

        requests_seen[digest].AddCallers()

        global last_request
        last_request = request

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
                "filename": filename,
            })
            f.write(s.encode('utf-8'))

        raise URLError(
            'URL is not cached. Created missing request record: {}.missing'.
            format(digest))

    def http_open(self, request):
        return self.https_open(request)


def InstallTestRequestHandler(test_data_dir=None):
    """Any test that makes network requests to https://cs.codesearch.com (i.e.
    those that rely on making network requests) should call this function in
    their respective setUp() functions.

    Doing so installs a test request handler that will fail the first time it
    is called with a new URL, but will write out a file indicating which URL
    requests were seen. One can then run the testing_support.py script directly
    which resolves the URL requests, and adds a file to the |testdata|
    directory containing the expected response data.

    This mechanism prevents the tests from making direct network requests.

    test_data_dir -- If not None, should specify an abosolute path to a test
        data directory containing a 'responses' subdirectory. This will be used
        in the aforementioned fashion to store response data to be used during
        testing.
    """

    global TEST_DATA_DIR
    global RESPONSE_DATA_DIR

    if test_data_dir is not None:
        TEST_DATA_DIR = test_data_dir
        RESPONSE_DATA_DIR = os.path.join(TEST_DATA_DIR, 'responses')

    install_opener(build_opener(TestHttpHandler()))


def DumpCallers(callers_file=None):
    """\
  DumpCallers writes a trace of callers to a file named `callers.json`. The
  filename can be overridden by the `callers_file` argument.

  The file contains a JSON encoded mapping from each cached response file name
  to a list of maps. Each map consists of the three keys "file", "line",
  "function" which collectively describe an "interesting" call frame found in
  the call stack leading up to the request for the named file.

  The caller lists can be used to figure out which cached response file was
  accessed by which callers during a test run.
  """
    global RESPONSE_DATA_DIR
    global requests_seen

    if callers_file is None:
        callers_file = os.path.join(RESPONSE_DATA_DIR, 'callers.json')

    o = {}

    try:
        with open(callers_file, "r") as f:
            o = json.load(f, encoding='utf-8')
    except IOError:
        pass
    except ValueError:
        pass

    for digest, ri in requests_seen.items():
        req = {}
        callers = []
        query = ri.data if len(ri.data) > 0 else urlparse(ri.url).query
        req["query"] = parse_qsl(query)
        for caller in ri.callers:
            callers.append({
                "file": caller[0],
                "line": caller[1],
                "function": caller[2]
            })
        req["callers"] = callers

        o[digest] = req

    with open(callers_file, "w") as f:
        json.dump(o, f, separators=(', ', ': '), indent=2, sort_keys=True)


def DisableNetwork():
    global disable_network
    disable_network = True


def EnableNetwork():
    global disable_network
    disable_network = False


def LastRequest():
    return last_request


if __name__ == '__main__':
    # Attempt to resolve all missing resource requests.
    HOST_MAPPING = {'cs.chromium.org': 'cs-staging.chromium.org'}

    resolved_count = 0

    if len(sys.argv) == 2:
        TEST_DATA_DIR = sys.argv[1]
        RESPONSE_DATA_DIR = os.path.join(TEST_DATA_DIR, 'responses')

    for name in os.listdir(RESPONSE_DATA_DIR):
        if not name.endswith('.missing'):
            continue

        print('Resolving {}'.format(name))

        with open(os.path.join(RESPONSE_DATA_DIR, name), mode='r') as f:
            o = json.load(f, encoding='utf-8')

        url, data, filename = o["url"], o["data"], o["filename"]
        uq = urlparse(url)
        if uq.netloc in HOST_MAPPING:
            url = urlunparse([] + [uq[0], HOST_MAPPING[uq.netloc]] +
                             list(uq)[2:6])

        req = Request(url=url)
        if data != '':
            AddDataToRequest(req, data.encode('utf-8'))

        try:
            response = urlopen(req, timeout=3)
            result = response.read()
            data = json.loads(result, encoding='utf-8')

            with open(os.path.join(RESPONSE_DATA_DIR, filename), 'w') as f:
                json.dump(data,
                          f,
                          indent=2,
                          separators=(', ', ': '),
                          encoding='utf-8')

            os.unlink(os.path.join(RESPONSE_DATA_DIR, name))

            print('   Resolved. Wrote {}'.format(filename))
            resolved_count += 1

        except Exception as e:
            print('   FAILED.:{} while looking at {}'.format(str(e), name))
            raise e

    if resolved_count > 0:
        print('\nDon\'t forget to \'git add\' the new files and commit them.')
    else:
        print('\nNo URLs resolved\n')
        sys.exit(1)
