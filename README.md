Chromium CodeSearch Library
===========================

The `codesearch` Python library provides an interface for talking to the
Chromium CodeSearch backend at https://cs.chromium.org/

The primary entry point into the library is the `CodeSearch` class. Various
message classes you are likely to encounter are defined in `messages.py`.

A quick example:

``` python
import codesearch

# The plugin needs to locate a local Chromium checkout. We are passing '.' as a
# path inside the source directory, which works if the current directory is
# inside the Chromium checkout. The configuration mechanism is likely to change.
cs = codesearch.CodeSearch(a_path_inside_source_dir='.')

# The backend takes a CompoundRequest object ...
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

# We can now examine the contents of the SearchResponse object to see what the
# server sent us. The fields are explained in message.py.

for search_result in response.search_response[0].search_result:
    assert isinstance(search_result, codesearch.SearchResult)

    if not hasattr(search_result, 'snippet'):
        continue

    for snippet in search_result.snippet:
        assert isinstance(snippet, codesearch.Snippet)

	# Just print the text of the search result snippet.
        print snippet.text.text
```

In addition, the library also includes facilities for maintaining an ephemeral
or persistent cache in order to minimize generated network traffic.

**Note**: This is not an official Google product.

See [CONTRIBUTING](./CONTRIBUTING.md) for details on contributing.

