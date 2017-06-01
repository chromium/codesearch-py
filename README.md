Chromium CodeSearch Library
===========================

The `codesearch` Python library provides an interface for talking to the
Chromium CodeSearch backend at https://cs.chromium.org/

The primary entry point into the library is the `CodeSearch` class. Various
message classes you are likely to encounter are defined in `messages.py`.

A quick example:

``` python
import codesearch

# The plugin can optionally work with a local Chromium checkout (see the
# documentation for CodeSearch.__init__()), but for this example, we are going
# use the API without a local checkout. This is indicated by setting the
# |source_root| to '.'.
cs = codesearch.CodeSearch(source_root='.')

# Let's look up a class:
# The SearchForSymbol function searches for a symbol of a specific type. In
# this case we are looking for a class named File. There may be more than one
# such class, so the function returns an array. We only need the first one.
file_class = cs.SearchForSymbol('File', codesearch.NodeEnumKind.CLASS)[0]

# SearchForSymbol returns an XrefNode object. This is a starting point for cross
# reference lookups.
assert isinstance(file_class, XrefNode)

# Say we want to look at all the declared members of the File class. This
# includes both member functions and member variables:
members = file_class.GetEdges(codesearch.EdgeEnumKind.DECLARES)

# There'll be a bunch of these.
assert len(members) > 0

# ... and they are all XrefNode objects.
assert isinstance(members[0], XrefNode)

# We can find out what kind it is. The kinds that are known to CodeSearch are
# described in the codesearch.NodeEnumKind enumeration.
print(members[0].GetXrefKind())


# In addition to the above, there are lower level APIs to talk to the unofficial
# endpoints in the https://cs.chromium.org backend. One such API is 
# SendRequestToServer.

# SendRequestToServer takes a CompoundRequest object ...
response = cs.SendRequestToServer(codesearch.CompoundRequest(
    search_request=[
        codesearch.SearchRequest(query='hello world')
    ]))

# ... and returns a CompoundResponse
assert isinstance(response, codesearch.CompoundResponse)

# Both CompoundRequest and CompoundResponse are explained in
# codesearch/messages.py. Since our request was a |search_request| which is a
# list of SearchRequest objects, our CompoundResponse object is going to have a
# |search_response| field ...

assert hasattr(response, 'search_response')

# containing a list of SearchResponse objects ...

assert isinstance(response.search_response, list)
assert isinstance(response.search_response[0], codesearch.SearchResponse)

# Note there will be only one search_response object.
assert len(response.search_response) == 1

# We can now examine the contents of the SearchResponse object to see what the
# server sent us. The fields are explained in message.py.

for search_result in response.search_response[0].search_result:
    assert isinstance(search_result, codesearch.SearchResult)

    if not hasattr(search_result, 'snippet'):
        continue

    for snippet in search_result.snippet:
        assert isinstance(snippet, codesearch.Snippet)

	# Just print the text of the search result snippet.
        print(snippet.text.text)
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

