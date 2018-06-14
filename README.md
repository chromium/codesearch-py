Chromium CodeSearch Library
===========================

The `codesearch` Python library provides an interface for talking to the
Chromium CodeSearch backend at https://cs.chromium.org/

The primary entry point into the library is the `CodeSearch` class. Various
message classes you are likely to encounter are defined in `messages.py`.

A quick example:

``` python
'''

Step 1 is to import codesearch.
>>> import codesearch

The following examples are written out as Python doctests and are run as a part
of the run_tests.sh suite. The InstallTestRequestHandler() sets up a test rig
that is used during testing to ensure that tests are reproducible and can be run
without a network connection. Feel free to use InstallTestRequestHandler() in
your own code if you need to test against the CodeSearch library. See
documentation for details.
>>> codesearch.InstallTestRequestHandler()

The plugin can optionally work with a local Chromium checkout (see the
documentation for CodeSearch.__init__()), but for this example, we are going use
the API without a local checkout. This is indicated by setting the |source_root|
to '.'.
>>> cs = codesearch.CodeSearch(source_root='.')

Let's look up a class:
The SearchForSymbol function searches for a symbol of a specific type. In this
case we are looking for a class named File. There may be more than one such
class, so the function returns an array. We only need the first one.
>>> file_class = cs.SearchForSymbol('FieldTrial$', codesearch.NodeEnumKind.CLASS)[0]

SearchForSymbol returns an XrefNode object. This is a starting point for cross
reference lookups.
>>> isinstance(file_class, codesearch.XrefNode)
True

We can look for references to this class.
>>> references = file_class.Traverse(codesearch.KytheXrefKind.REFERENCE)

There will be a number of these.
>>> len(references) > 30
True

In addition to the above, there are lower level APIs to talk to the unofficial
endpoints in the https://cs.chromium.org backend. One such API is
SendRequestToServer.

SendRequestToServer takes a CompoundRequest object ...
>>> response = cs.SendRequestToServer(codesearch.CompoundRequest(
...     search_request=[
...     codesearch.SearchRequest(query='hello world',
...                              return_line_matches=True,
...                              lines_context=0,
...                              max_num_results=10)
...     ]))

.. and returns a CompoundResponse
>>> isinstance(response, codesearch.CompoundResponse)
True

Both CompoundRequest and CompoundResponse are explained in
codesearch/messages.py. Since our request was a |search_request| which is a list
of SearchRequest objects, our CompoundResponse object is going to have a
|search_response| field ...
>>> hasattr(response, 'search_response')
True

.. containing a list of SearchResponse objects ...
>>> isinstance(response.search_response, list)
True

.. which contains exactly one element ...
>>> len(response.search_response)
1

.. whose type is SearchResponse.
>>> isinstance(response.search_response[0], codesearch.SearchResponse)
True

It should indicate an estimate of how many results exist. This could diverge
from the number of results included in this response message. If that's the
case, then |hit_max_results| would be true.
>>> response.search_response[0].hit_max_results
True

We can now examine the SearchResult objects to see what the server sent us. The
fields are explained in message.py.
>>> lines_left = 10
>>> for search_result in response.search_response[0].search_result:
...     assert isinstance(search_result, codesearch.SearchResult)
... 
...     for match in search_result.match:
...         print("{}:{}: {}".format(search_result.top_file.file.name,
...                                  match.line_number,
...                                  match.line_text.strip()))
...         lines_left -= 1
...         if lines_left == 0: break
...     if lines_left == 0: break
src/v8/samples/hello-world.cc:40: v8::String::NewFromUtf8(isolate, "'Hello' + ', World!'",
src/v8/samples/hello-world.cc:34: // Enter the context for compiling and running the hello world script.
src/gin/shell/hello_world.js:5: log("Hello World");
src/v8/test/fuzzer/parser/hello-world:1: console.log('hello world');
src/native_client/tests/hello_world/hello_world.c:13: void hello_world(void) {
src/native_client/tests/hello_world/hello_world.c:14: printf("Hello, World!\n");
src/native_client/tests/hello_world/hello_world.c:18: hello_world();
src/tools/gyp/test/hello/hello.c:9: printf("Hello, world!\n");
src/tools/gn/tutorial/hello_world.cc:8: printf("Hello, world.\n");
infra/go/src/go.chromium.org/luci/grpc/prpc/e2etest/helloworld_test.proto:19: service Hello {

Note that in the example above:
*  search_result.match was available because |return_line_matches| was set to
   True when making the server request. Otherwise the server response will not
   contain line matches.
*  The line matches will have multiple lines of context. This was suppressed in
   the example by setting |lines_context| to 0.
'''
```

In addition, the library also includes facilities for maintaining an ephemeral
or persistent cache in order to minimize generated network traffic.

**Note**: The library uses an unsupported interface to talk to the backend. If
you are using the library and it suddenly stops working, file an issue and/or
monitor the project on GitHub for updates.

**Note**: This is not an official Google product.

Support
-------

Feel free to submit issues on GitHub and/or contact the authors. This project is
not officially supported by Google or the Chromium project.

Contributing
------------

See [CONTRIBUTING](./CONTRIBUTING.md) for details on contributing.

[![Build Status](https://travis-ci.org/chromium/codesearch-py.svg?branch=master)](https://travis-ci.org/chromium/codesearch-py)

