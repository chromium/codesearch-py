Chromium CodeSearch Library: Changes Since Kythe Migration
==========================================================

`https://cs.chromium.org` went through a substantial change at the end of 2017
which involved multiple behavior changes to the JSON RPC endpoints used by
`codesearch-py`. These resulted in breaking API changes as described below.

There's no real supported API for external libraries such as this one to
communicate with the `https://cs.chromium.org` backend. Instead, this library
relies on a set of reverse-engineered JSON endpoints that are meant to support
the CodeSearch web UI. Chrome Infra is aware of this use, but is in no way
required to support it. Hence breakages such as what was observed during the
Grok->Kythe backened migration are expected and supposed to be dealt with the
`codesearch-py` and `vim-codesearch` maintainers.

## Signatures are different

Signatures are how CodeSearch identifies various entities relevant to the source
index. These identify locations in source as well as abstract symbols as
identified by the compiler. While the format of the signature is supposed to be
opaque, it is nonetheless used by `codesearch-py` as well as `vim-codesearch`
as a means of bridging certain feature gaps.

For example, the codesearch "API" didn't have a mechanism to reliably extract
the type of a C++ symbol. The `codesearch-py` library attempted to extract this
information from the old-style Grok signature. Some examples of these are
reproduced below:

  * **Class BackgroundSyncService** :
    `cpp:blink::mojom::class-BackgroundSyncService@chromium/gen/third_party/WebKit/public/platform/modules/background_sync/background_sync.mojom.h|def`

  * **Method BackgroundSyncService::Register** :
    `cpp:blink::mojom::class-BackgroundSyncService::Register(mojo::InlinedStructPtr<blink::mojom::SyncRegistration>, long, base::OnceCallback<void (blink::mojom::BackgroundSyncError, mojo::InlinedStructPtr<blink::mojom::SyncRegistration>)>)@chromium/gen/third_party/WebKit/public/platform/modules/background_sync/background_sync.mojom.h|decl` 

  * **Method parameter named 'options'**:
    `cpp:blink::mojom::class-BackgroundSyncService::Register(mojo::InlinedStructPtr<blink::mojom::SyncRegistration>, long, base::OnceCallback<void (blink::mojom::BackgroundSyncError, mojo::InlinedStructPtr<blink::mojom::SyncRegistration>)>)::param-options@chromium/gen/third_party/WebKit/public/platform/modules/background_sync/background_sync.mojom.h:3620|decl`

  * **Class declaration**:
    `cpp:blink::mojom::class-BackgroundSyncServiceRequestValidator@chromium/gen/third_party/WebKit/public/platform/modules/background_sync/background_sync.mojom.h|decl`

After the migration, the signatures now look like this:

    kythe://chromium?lang=c%2B%2B?path=src/base/metrics/field_trial.h#i6ClzEA3SkIB4HClJFSpS5bM3mLlUpnwoUIVw06C0ME%3D

While the high level format of the signature is documented (see [Kythe URI
Spec][]), the URI doesn't include the kind of rich metadata that the old style
Grok signatures had. This broke some of the signature location functionality.
Consequently, the APIs that relied on this functionality was removed.

[Kythe URI Spec]: https://kythe.io/docs/kythe-uri-spec.html

## `xref_search_request` message no longer filters by edge type

This is probably one of the more consequential changes. The
`xref_search_request` message was being used heavily by the `codesearch-py`
library as well as `vim-codesearch` to extract a list of signatures
corresponding to some edge type.

For example, consider the following code snippet provided as an example in the
older `README.md` file:

``` py
# Say we want to look at all the declared members of the File class. This includes
# both member functions and member variables:
# >>> members = file_class.GetEdges(codesearch.EdgeEnumKind.DECLARES)
# 
# There'll be a bunch of these.
# >>> len(members) > 0
# True
# 
# ..  and they are all XrefNode objects.
# >>> isinstance(members[0], codesearch.XrefNode)
# True
# 
# We can find out what kind it is. The kinds that are known to CodeSearch are
# described in the codesearch.NodeEnumKind enumeration.
# >>> print(members[0].GetXrefKind())
# 5200
```

Here, the `file_class` object is an `codesearch.XrefNode` object corresponding
to a `C++` class. The `DECLARES` edge type exists from a C++ class to all fields
and methods that are declared within it.

This kind of filtering is no longer possible since the migration. It is only
possible to extract all the references for a given signature which currently
include the kinds described in the `KytheXrefKind` enumeration in `messages.py`.

Note that there's no `MEMBER_OF` or an equivalent relation. Thus there's no way
currently via this API to enumerate the members of a class other than to infer
such relationships via the document outline.

## `xref_search_response` no longer include called-by information, or modifiers

Prior to the migration, an `xref_search_request` message could've been used to
request not just references, definitions, and declarations, but also call sites.
After the Kythe migration, call sites appear in the `xref_search_response` as
`REFERENCE` type results.

Modifiers are no longer returned as a part of `xref_search_response` messages.

Also, as noted below the `type_id` is now a `KytheXrefKind`.

## Root `call_graph_response` Node no longer contain path information

The server responds to a `call_graph_request` with a `call_graph_response`
message which is described in `messages.py` as the `CallGraphResponse` class. A
non-empty response would include a single root call graph node called `node`.
It's described in `messages.py` as `Node`.

Prior to the migration, this root node could be expected to be properly
populated with file path and snippet information for the root signature. Post
migration these fields are no longer being populated.

## Call graph nodes no longer include a `display_name`

The Grok backend populated the `display_name` field of a `Node` object with a
full `c++` symbol name. The new Kythe backend doesn't populate this field at
all. Instead callers should rely on the `identifier` field. The latter is a
single identifier and does not contain scope or type information.

# Breaking API Changes

*   `NodeEnumKind` is now deprecated. It's still used in some APIs (e.g.
    `CodeSearch.SearchForSymbol()`) where its only interpreted client-side. This
    may change in the future to use something a bit more stable.

*   `InternalLink` and `XrefSignature` acquire a `highlight_signature` field.

*   `signature` and the new `highlight_signature` fields in `InternalLink` and
    `XrefSignature` messages can now contain a SPC delimited list of signatures
    instead of one unique signature. Any code that directly accesses these
    fields must be updated to deal.

    As a conveniece, both `InternalLink` and `XrefSignature` messages have
    `MatchesSignature()`, `GetSignature()`, and `GetSignatures()` methods to
    deal with this new signature formats.

*   `KytheNodeEnumKind` renamed to `KytheNodeKind` for consistency with how
    other enumerations are named.

*   `Annotation` messages no longer populate the `xref_kind` field. Instead they
    populate the `kythe_xref_kind` field.

*   `CodeBlockType` acquired two new values `GROUP` and `SCOPE`.

*   `EdgeEnumKind` enumeration is deprecated and no longer used by any API.

*   New enumeration `KytheXrefKind`. Note the limited functionality
    compared to `EdgeEnumKind`.

*   `XrefTypeCount`'s `type_id` is now strictly a `KytheXrefKind` value.

*   `XrefSingleMatch`'s `type_id` is now a `KytheXrefKind` instead of
    `EdgeEnumKind`.

*   `XrefSingleMatch`'s `node_type` and `grok_modifiers` fields are now no
    longer populated. Consequently, modifiers can no longer be extracted from
    cross reference search result sets.

*   `XrefSearchRequest`'s `edge_filter` field is no longer honored during
    searches.

*   `XrefNode` no longer has a `GetEdges()` or `GetAllEdges()` methods. The
    functionality of these methos had to change considerably. Hence I opted to
    replace both of these with a `Traverse()` method that intends to remain more
    stable.

*   `XrefNode` no longer has a `GetType()` method since that information is no
    longer available from CodeSearch responses.

*   `Node` objects may be sparsely populate and may lack `file_path` fields.

*   `Node` objects no longer populate the `display_name` with the full `c++`
    symbol name. The field is no longer included in responses. Use the
    `identifier` field as a workaround. The full `c++` symbol name is no longer
    accessible from the web-facing interface.

*   `node_kind` of a `Node` object is now a `KytheNodeKind`.

