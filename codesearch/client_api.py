# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.
"""This file defines the entry point for most external consumers of the Python
Codesearch library.
"""

from __future__ import absolute_import

import logging
import os

from .file_cache import FileCache
from .messages import CompoundRequest, AnnotationType, AnnotationTypeValue, \
        CompoundResponse, FileInfoRequest, FileSpec, AnnotationRequest, \
        EdgeEnumKind, XrefSearchRequest, XrefSingleMatch, XrefSearchResult, \
        FileInfo, TextRange, Annotation
from .paths import GetSourceRoot

try:
  from urllib.request import urlopen, Request
  from urllib.parse import urlencode, urlparse
except ImportError:
  from urllib2 import urlopen, Request
  from urllib import urlencode
  from urlparse import urlparse


class CsFile(object):
  """Represents a file known to CodeSearch and allows looking up annotations."""

  def __init__(self, cs, file_info):
    self.cs = cs
    self.file_info = file_info

    assert isinstance(self.cs, CodeSearch)
    assert isinstance(self.file_info, FileInfo)

    if hasattr(self.file_info, 'content'):
      self.lines = self.file_info.content.text.splitlines()
      self.file_info.content.text = None
    else:
      self.lines = []
    self.annotations = None

  def Path(self):
    """Return the path to the file relative to the root of the source directory."""
    return self.file_info.name

  def Text(self, text_range):
    """Given a TextRange, returns the text corresponding to said range in this file.

    Any intervening newlines will be represented with a single '\n'."""

    assert isinstance(text_range, TextRange)

    if text_range.start_line <= 0 or text_range.start_line > len(self.lines) or \
            text_range.end_line <= 0 or text_range.end_line > len(self.lines) or \
            text_range.start_line > text_range.end_line:
      raise IndexError('invalid range specified')
    if text_range.start_line == text_range.end_line:
      return self.lines[text_range.start_line
                        - 1][text_range.start_column - 1:text_range.end_column]

    first = [
        self.lines[text_range.start_line - 1][text_range.start_column - 1:]
    ]
    middle = self.lines[text_range.start_line:text_range.end_line - 1]
    end = [self.lines[text_range.end_line - 1][:text_range.end_column]]

    return '\n'.join(first + middle + end)

  def GetFileSpec(self):
    return FileSpec(
        name=self.file_info.name, package_name=self.file_info.package_name)

  def GetAnnotations(self):
    if self.annotations == None:
      response = self.cs.GetAnnotationsForFile(self.GetFileSpec())
      if not hasattr(response.annotation_response[0], 'annotation'):
        raise Exception(
            'can\'t fetch annotations for {}'.format(str(self.GetFileSpec())))
      self.annotations = response.annotation_response[0].annotation
      assert isinstance(self.annotations, list)
      assert isinstance(self.annotations[0], Annotation)

    return self.annotations

  def GetAnchorText(self, signature):
    # Fetch annotations if we haven't already.
    self.GetAnnotations()

    for annotation in self.annotations:
      sig = getattr(annotation, 'xref_signature', None)
      if sig and sig.signature == signature:
        return self.Text(annotation.range)

    raise Exception('can\'t determine display name for {}'.format(signature))


class XrefNode(object):
  """A cross-reference node.

  The codesearch data is represented as a graph of nodes where locations in
  source or symbols are are connected to other symbols or locations in source
  via edges.

  In the abstract, a location or symbol in the source is represented using
  what's called a "signature". In practice the signature is a string whose
  exact contents is determined by the indexer. It's purpose is to act as an
  identifier for the "thing" its referring to.

  For example, the declaration of HttpNetworkTransaction in
  net/http_network_transaction.cc (currently) has the signature
  "cpp:net::class-HttpNetworkTransaction@chromium/../../net/http/http_network_transaction.h|def".

  HttpNetworkTransaction declares a number of symols (more than 200 at the time
  of writing). So you can figure out its declared symbols as follows:

  >>> import codesearch

  # Replace the path with where you have the Chromium sources checked out:
  >>> cs = codesearch.CodeSearch(a_path_inside_source_dir='~/src/chrome/src')

  # Ditto for the path to source:
  >>> sig = cs.GetSignatureForSymbol('~/src/chrome/src/net/http/http_network_transaction.cc', \
          'HttpNetworkTransaction')

  >>> node = codesearch.XrefNode.FromSignature(cs, sig)
  >>> node.GetEdges(codesearch.EdgeEnumKind.DECLARES)

  This should dump out a list of XrefNode objects corresponding to the declared
  symbols. You can inspect the .filespec and .single_match members to figure
  out what the symols are.

  Note that the members of the |node| object that was created by
  XrefNode.FromSignature() doesn't have anything interesting in the |filespec|
  and |single_match| members other than the signature.
  """

  def __init__(self, cs, single_match, filespec=None, parent=None):
    """Constructs an XrefNode.

    This is probably not what you are looking for. Instead figure out the
    signature of the node you want to start with using one of the
    GetSignatureFor* methods in CodeSearch, and then use the
    XrefNode.FromSignature() static method to construct a starter node.

    From there, you can use the GetEdge() and/or GetAllEdges() methods to
    explore the cross references."""

    self.cs = cs
    self.filespec = filespec
    self.single_match = single_match
    self.parent = parent

    assert isinstance(self.cs, CodeSearch)
    assert isinstance(self.single_match, XrefSingleMatch)
    assert self.parent is None or isinstance(self.parent, XrefNode)

  def GetEdges(self, edge_enum_kind, max_num_results=500):
    """Gets outgoing edges for this node matching |edge_enum_kind|.

    |edge_enum_kind| can be either a single EdgeEnumKind value or it could be a
    list of EdgeEnumKind values. In either case, all outgoing edges that match
    any element in |edge_enum_kind| will be returned in the form of a list of
    XrefNode objects.

    If there are no matching edges, the funtion will return an empty list.
    """
    if isinstance(edge_enum_kind, list):
      edge_filter = edge_enum_kind
    else:
      edge_filter = [edge_enum_kind]
    results = self.cs.GetXrefsFor(self.single_match.signature, edge_filter,
                                  max_num_results)
    if not results:
      return []

    return XrefNode.FromSearchResults(self.cs, results, self)

  def GetAllEdges(self, max_num_results=500):
    """Return all known outgoing edges from this node.

    Note that there can be literally hundreds of outgoing edges, if not
    thousands. The |max_num_results| determines the number of results that will
    be returned if there are too many.
    """
    return self.GetEdges([
        getattr(EdgeEnumKind, x) for x in vars(EdgeEnumKind)
        if isinstance(getattr(EdgeEnumKind, x), int)
    ], max_num_results)

  def GetFile(self):
    """Return the file containing this XrefNode as a CsFile."""
    if not self.filespec:
      raise Exception('no filespec found for XrefNode')
    return self.cs.GetFileInfo(self.filespec)

  def GetDisplayName(self):
    """Return the display name for this XrefNode.

    It is possible for there to be no associated displayname. E.g. if the
    XrefNode corresponds to a template specialization. In that case, this
    method will throw.
    """
    if not self.filespec:
      raise Exception('no filespec found for XrefNode')
    return self.cs.GetFileInfo(self.filespec).GetAnchorText(
        self.single_match.signature)

  def GetXrefKind(self):
    """Return the kind of node.

    See definition of NodeEnumKind for a list of possible node kinds."""

    if not self.filespec:
      raise Exception('no filespec found for XrefNode')
    annotations = self.cs.GetFileInfo(self.filespec).GetAnnotations()
    for annotation in annotations:
      sig = getattr(annotation, 'xref_signature', None)
      if sig and sig.signature == self.single_match.signature:
        return getattr(annotation, 'xref_kind', None)
    raise Exception('unable to determine xref kind')

  def GetRelatedAnnotations(self):
    """Get related annotations. Currently this is defined to be annotations
    that surround the current xref location."""

    if not self.filespec:
      raise Exception('no filespec found for XrefNode')
    annotations = self.cs.GetFileInfo(self.filespec).GetAnnotations()
    target_range = None
    for annotation in annotations:
      sig = getattr(annotation, 'xref_signature', None)
      if sig and sig.signature == self.single_match.signature:
        target_range = annotation.range
        break

    if not target_range:
      raise Exception('no related annotations')

    related = []
    for annotation in annotations:
      if annotation.range.end_line < target_range.start_line or \
              annotation.range.start_line > target_range.end_line:
        continue
      if annotation.range == target_range:
        continue
      related.append(annotation)
    return related

  def GetRelatedDefinitions(self):
    """Get related definitions. Currently this is defined to be linked
    definitions that surround the current xref location.

    This is a hack that can be used to get at the type of a class member. E.g.:

        class Foo {
          public:
            BarType bar_;
        };

    The signature of |bar_|'s definition should have a cross reference of type
    HAS_TYPE which should link to the type. However, in practice, this
    reference type may not be available. Instead, we use a heuristic where we
    look for definitions that are on the same lines as the target. In this
    case, we look for a LINK_TO_DEFINITION type annotation on the same line as
    |bar_|. Such a link is likely to point to the type of |bar_| if it's a
    compound type with cross reference information.

    If any such definitions are found, a further HAS_DEFINITION edge lookup is
    performed so that the resulting XrefNode corresponds to the definition of
    the type.
    """

    if not self.filespec:
      raise Exception('no filespec found for XrefNode')
    annotations = self.cs.GetFileInfo(self.filespec).GetAnnotations()
    target_range = None
    for annotation in annotations:
      sig = getattr(annotation, 'xref_signature', None)
      if sig and sig.signature == self.single_match.signature:
        target_range = annotation.range
        break

    if not target_range:
      raise Exception('no related annotations')

    related = []
    for annotation in annotations:
      if annotation.type.id != AnnotationTypeValue.LINK_TO_DEFINITION:
        continue
      if annotation.range.end_line < target_range.start_line or \
              annotation.range.start_line > target_range.end_line:
        continue
      abstract_node = XrefNode.FromAnnotation(self.cs, annotation)
      def_list = abstract_node.GetEdges(EdgeEnumKind.HAS_DEFINITION)
      if not def_list:
          related.append(abstract_node)
      else:
          related.append(def_list[0])
    return related

  def GetSignature(self):
    """Return the signature for this node"""
    return self.single_match.signature

  def __str__(self):
    s = "{"
    if self.filespec:
      s += "filespec: {}, ".format(str(self.filespec))
    s += "single_match: {}".format(str(self.single_match))
    s += "}"
    return s

  @staticmethod
  def FromSignature(cs, signature, filename=None):
    """Construct a XrefNode object for |signature|.

    Other than the |signature| the constructured node will have no other
    interesting fields. It can, however, be used to query outgoing edges.
    """

    filespec = cs.GetFileSpec(filename) if filename else None
    return XrefNode(
        cs,
        filespec=filespec,
        single_match=XrefSingleMatch(signature=signature))

  @staticmethod
  def FromAnnotation(cs, annotation):
    """Construct a XrefNode based on an Annotation.

      This is currently limited to annotations that have a LINK_TO_DEFINITION."""
    assert isinstance(annotation, Annotation)
    assert annotation.type.id == AnnotationTypeValue.LINK_TO_DEFINITION

    return XrefNode.FromSignature(
        cs,
        annotation.internal_link.signature,
        filename=FileSpec(
            name=annotation.internal_link.path,
            package_name=annotation.internal_link.package_name))

  @staticmethod
  def FromSearchResults(cs, results, parent=None):
    """Construct a *list* of XrefNode objects from a list of XrefSearchResult
    objects.
    """
    nodes = []

    assert isinstance(cs, CodeSearch)
    assert isinstance(results, list)

    for result in results:
      assert isinstance(result, XrefSearchResult)

      for match in result.match:
        assert isinstance(match, XrefSingleMatch)

        nodes.append(XrefNode(cs, match, result.file, parent))

    return nodes


class CodeSearch(object):

  class Stats(object):

    def __init__(self):
      self.cache_hits = 0
      self.cache_misses = 0  # == number of network requests made

  def __init__(self,
               should_cache=False,
               cache_dir=None,
               source_root=None,
               a_path_inside_source_dir=None,
               package_name='chromium',
               codesearch_host='https://cs.chromium.org',
               request_timeout_in_seconds=3,
               user_agent_string='Python-CodeSearch-Client'):

    # An instance of FileCache or None if no caching is to be performed.
    self.file_cache = None

    # A cache mapping path -> CsFile objects.
    self.file_info_cache = {}

    self.logger = logging.getLogger('codesearch')

    self.source_root = ''

    self.package_name = package_name

    self.codesearch_host = codesearch_host

    self.request_timeout_in_seconds = request_timeout_in_seconds

    self.source_root = source_root if source_root else GetSourceRoot(
        a_path_inside_source_dir)

    self.extra_headers = {'User-Agent': user_agent_string}

    self.stats = CodeSearch.Stats()

    if not should_cache:
      self.file_cache = None
      return
    self.file_cache = FileCache(cache_dir=cache_dir)

  def GetSourceRoot(self):
    return self.source_root

  def GetLogger(self):
    return self.logger

  def GetFileSpec(self, path=None):
    if not path:
      return FileSpec(name='.', package_name=self.package_name)

    if isinstance(path, FileSpec):
      return path

    return FileSpec(
        name=os.path.relpath(os.path.abspath(path), self.source_root),
        package_name=self.package_name)

  def TeardownCache(self):
    if self.file_cache:
      self.file_cache.close()

    self.file_cache = None

  def _Retrieve(self, url):
    """Retrieve the URL by first checking the cache and then falling back to
        using the network."""
    self.logger.debug('Fetching %s', url)

    if self.file_cache:
      cached_response = self.file_cache.get(url)
      self.logger.debug('Found cached response')
      if (cached_response):
        self.stats.cache_hits += 1
        return cached_response.decode('utf8')
    self.stats.cache_misses += 1

    # Long URLs cause the request to fail.
    if len(url) > 1500:
      parsed = urlparse(url)
      short_url = '{}://{}{}'.format(parsed.scheme, parsed.netloc, parsed.path)
      data = parsed.query.encode('utf-8')
      request = Request(url=short_url, headers=self.extra_headers, data=data)
    else:
      request = Request(url=url, headers=self.extra_headers)

    response = urlopen(request, timeout=self.request_timeout_in_seconds)
    result = response.read()
    if self.file_cache:
      self.file_cache.put(url, result)
    return result.decode('utf8')

  def SendRequestToServer(self, compound_request):
    if not isinstance(compound_request, CompoundRequest):
      raise ValueError(
          '|compound_request| should be an instance of CompoundRequest')

    qs = urlencode(compound_request.AsQueryString(), doseq=True)
    url = '{host}/codesearch/json?{qs}'.format(host=self.codesearch_host, qs=qs)
    result = self._Retrieve(url)
    return CompoundResponse.FromJsonString(result)

  def GetAnnotationsForFile(
      self,
      filename,
      annotation_types=[AnnotationType(id=AnnotationTypeValue.XREF_SIGNATURE)]):
    return self.SendRequestToServer(
        CompoundRequest(annotation_request=[
            AnnotationRequest(
                file_spec=self.GetFileSpec(filename), type=annotation_types)
        ]))

  def GetSignatureForLocation(self, filename, line, column):
    annotations = self.GetFileInfo(filename).GetAnnotations()
    for annotation in annotations:
      if not annotation.range.Contains(line, column):
        continue

      if hasattr(annotation, 'xref_signature'):
        return annotation.xref_signature.signature

      if hasattr(annotation, 'internal_link'):
        return annotation.internal_link.signature

    raise Exception("Can't determine signature for %s at %d:%d" %
                    (filename, line, column))

  def GetFileInfo(self,
                  filename,
                  fetch_html_content=False,
                  fetch_outline=False,
                  fetch_folding=False,
                  fetch_generated_from=False):
    """Return a CsFile object corresponding to the file named by |filename|.

    If |filename| is a FileSpec object, then that FileSpec object is used as-is
    to locate the file. Otherwise |filename| is resolved as a local path which
    should then map to a file known to CodeSearch."""

    file_spec = self.GetFileSpec(filename)
    cacheable = (not fetch_html_content) and (not fetch_outline) and (
        not fetch_folding) and (not fetch_generated_from)
    if cacheable and (file_spec.name in self.file_info_cache):
      return self.file_info_cache[file_spec.name]

    result = self.SendRequestToServer(
        CompoundRequest(file_info_request=[
            FileInfoRequest(
                file_spec=self.GetFileSpec(filename),
                fetch_html_content=fetch_html_content,
                fetch_outline=fetch_outline,
                fetch_folding=fetch_folding,
                fetch_generated_from=fetch_generated_from)
        ]))

    if hasattr(result.file_info_response[0], 'file_info'):
      file_info = CsFile(self, file_info=result.file_info_response[0].file_info)
      if cacheable:
        self.file_info_cache[file_spec.name] = file_info

      return file_info

    raise Exception('can\'t fetch file info for %f' % (filename))

  def GetSignatureForSymbol(self, filename, symbol):
    annotations = self.GetFileInfo(filename).GetAnnotations()
    for snippet in annotations:
      if hasattr(snippet, 'xref_signature'):
        signature = snippet.xref_signature.signature
        if '%s(' % symbol in signature:
          return signature

      elif hasattr(snippet, 'internal_link'):
        signature = snippet.internal_link.signature
        if '::%s' % symbol in signature or 'class-%s' % symbol in signature:
          return signature

    raise Exception("Can't determine signature for %s:%s" % (filename, symbol))

  def GetXrefsFor(self, signature, edge_filter, max_num_results=500):
    refs = self.SendRequestToServer(
        CompoundRequest(xref_search_request=[
            XrefSearchRequest(
                file_spec=self.GetFileSpec(),
                query=signature,
                edge_filter=edge_filter,
                max_num_results=max_num_results)
        ]))
    if not refs or not hasattr(refs.xref_search_response[0], 'search_result'):
      return []
    return refs.xref_search_response[0].search_result

  def GetOverridingDefinitions(self, signature):
    candidates = []
    refs = self.GetXrefsFor(signature, [EdgeEnumKind.OVERRIDDEN_BY])
    for result in refs:
      matches = []
      for match in result.match:
        if hasattr(match, 'grok_modifiers') and hasattr(
            match.grok_modifiers,
            'definition') and match.grok_modifiers.definition:
          matches.append(match)
      if matches:
        result.match = matches
        candidates.append(result)
    return candidates

  def GetCallTargets(self, signature):
    # First look up the declaration for the callsite.
    refs = self.GetXrefsFor(signature, [EdgeEnumKind.HAS_DECLARATION])

    candidates = []
    for result in refs:
      for match in result.match:
        if hasattr(match, 'grok_modifiers') and hasattr(
            match.grok_modifiers, 'virtual') and match.grok_modifiers.virtual:
          candidates.extend(self.GetOverridingDefinitions(match.signature))
    if not candidates:
      return self.GetXrefsFor(signature, [EdgeEnumKind.HAS_DEFINITION])
    return candidates

  def IsContentStale(self, filename, buffer_lines, check_prefix=False):
    response = self.SendRequestToServer(
        CompoundRequest(file_info_request=[
            FileInfoRequest(
                file_spec=self.GetFileSpec(filename),
                fetch_html_content=False,
                fetch_outline=False,
                fetch_folding=False,
                fetch_generated_from=False)
        ]))

    response = response.file_info_response[0]
    content_lines = response.file_info.content.text.split('\n')

    if check_prefix:
      content_lines = content_lines[:len(buffer_lines)]
      if len(content_lines) != len(buffer_lines):
        return True

    for left, right in zip(content_lines, buffer_lines):
      if left != right:
        return True

    return False
