# Copyright 2017 The Chromium Authors.
#
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd.

import json
import sys
import os

from .compat import IsString, ToStringSafe

# For type checking. Not needed at runtime.
try:
  from typing import Any, Optional, List, Dict, Union, Type, Tuple
except ImportError:
  pass


class CodeSearchProtoJsonEncoder(json.JSONEncoder):

  def default(self, o):
    if isinstance(o, Message):
      return o.__dict__
    return o


class CodeSearchProtoJsonSymbolizedEncoder(json.JSONEncoder):

  def default(self, o):
    if isinstance(o, Message):
      rv = {}
      desc = o.__class__.DESCRIPTOR
      for k, v in o.__dict__.items():
        if k in desc:
          if not isinstance(desc[k], list) and \
              issubclass(desc[k], Message) and \
              desc[k].IsEnum():
            rv[k] = desc[k].ToSymbol(v)
          elif desc[k] == str and IsString(v) and not v:
            pass
          elif isinstance(desc[k], list) and \
              isinstance(v, list) and \
              len(v) == 0:
            pass
          elif v is None:
            pass
          else:
            rv[k] = v
        else:
          rv[k] = v
      return rv
    return o


def StringifyObject(o, target_type):

  def stringify_lines(o, level):
    indent = '  ' * level
    lines = [indent + '{']
    for k, v in vars(o).items():
      if isinstance(v, target_type):
        lines.append(indent + '  {}:'.format(k))
        lines.extend(stringify_lines(v, level + 1))
      else:
        lines.append(indent + '  {}: {}'.format(k, repr(v)))
    lines.append(indent + '}')
    return lines

  return '\n'.join(stringify_lines(o, 0))


def AttemptToFixupInvalidUtf8(s):
  """Try to recover invalid UTF-8 by replacing invalid bytes.
   
    The response from the server is not guaranteed to be valid UTF-8.  This
    function attempts to recover incorrect UTF-8. We may still run into issues
    due to a botched recovery, but this response is already doomed."""

  def FixupByteArray(s):
    return s.decode(encoding='utf-8', errors='replace')

  def FixupString(s):
    return str.decode(encoding='utf-8', errors='replace')

  if isinstance(s, bytearray):
    return FixupByteArray(s)

  if isinstance(s, bytes):
    return FixupByteArray(bytearray(s))

  if isinstance(s, str):
    return FixupString(s)

  return None


class Message(object):

  class PARENT_TYPE:
    pass

  def AsQueryString(self):
    # type: () -> List[Tuple[str,str]]
    values = []  # type: List[Tuple[str,str]]
    for k, v in sorted(self.__dict__.items()):
      values.extend(Message.ToQueryString(k, v))
    return values

  def __str__(self):
    return StringifyObject(self, Message)

  @staticmethod
  def ToQueryString(k, o):
    # type: (str, Any) -> List[Tuple[str,str]]
    if o is None:
      return []
    if isinstance(o, Message):
      return [(k, 'b')] + o.AsQueryString() + [(k, 'e')]
    if isinstance(o, bool):
      return [(k, 'true' if o else 'false')]
    if isinstance(o, list):
      values = []
      for v in o:
        values.extend(Message.ToQueryString(k, v))
      return values
    if isinstance(o, str) and not o:
      return []
    return [(k, str(o))]

  @staticmethod
  def Coerce(source, target_type, parent_class=None):
    if isinstance(target_type, list):
      assert isinstance(source, list)
      assert len(target_type) == 1

      return [Message.Coerce(x, target_type[0], parent_class) for x in source]

    if target_type == Message.PARENT_TYPE:
      assert parent_class is not None
      return Message.Coerce(source, parent_class, parent_class)

    if issubclass(target_type, Message):
      if source.__class__ == target_type:
        return source

      descriptor = target_type.DESCRIPTOR

      if isinstance(descriptor, dict):
        assert isinstance(
            source, dict), 'Source is not a dictionary: %s; Mapping to %s' % (
                source, target_type)
        dest = {}
        for k, v in source.items():
          if k in descriptor:
            dest[k] = Message.Coerce(v, descriptor[k], target_type)
          else:
            dest[k] = v
        return target_type(**dest)

      if descriptor is None:
        assert isinstance(source, dict)
        m = Message()
        m.__dict__ = source.copy()
        return m

      if descriptor != str and IsString(source):
        if hasattr(target_type, source):
          return descriptor(getattr(target_type, source))
        raise ValueError(
            "unrecognized symbolic enum value \"{}\" for {}".format(
                source, str(target_type)))
      return descriptor(source)
    if target_type == str and IsString(source):
      return ToStringSafe(source)
    return target_type(source)

  @classmethod
  def IsEnum(cls):
    return not isinstance(cls.DESCRIPTOR, dict)

  @classmethod
  def ToSymbol(cls, v):
    assert cls.IsEnum()
    for prop, value in vars(cls).items():
      if value == v:
        return prop
    return v

  @classmethod
  def FromSymbol(cls, s):
    assert cls.IsEnum()
    return vars(cls)[s]

  @classmethod
  def Make(cls, **kwargs):
    return Message.Coerce(kwargs, cls)

  @classmethod
  def FromShallowDict(cls, d):
    return Message.Coerce(d, cls)

  @classmethod
  def FromJsonString(cls, s):
    try:
      if isinstance(s, bytes) or isinstance(s, bytearray):
        s = s.decode(encoding='utf-8')
      d = json.loads(s)

    except UnicodeError as e:
      # The server sent us something that can't be decoded. It's probably not
      # valid UTF-8.  Rather than giving up, let's try to fix up the string so
      # that we can move on. Usually the problem is that there's an errant byte
      # that needs to be replaced with something else.

      s = AttemptToFixupInvalidUtf8(s)
      if s:
        d = json.loads(s)
      else:
        raise ValueError(
            'Error while decoding {o}. {reason} at offset {start}'.format(
                o=repr(e.object), reason=e.reason, start=e.start))

    except ValueError as e:
      import tempfile
      error_file_name = None
      with tempfile.NamedTemporaryFile(
          delete=False, prefix='codesearch_error_') as f:
        f.write("""Error while decoding JSON response.

Message: {msg}
Content follows this line: ----
{content}
""".format(msg=e.message, content=s))
        error_file_name = f.name
      raise ValueError(
          'Error while decoding JSON response. Report saved to {}'.format(
              error_file_name))

    return cls.FromShallowDict(d)

  DESCRIPTOR = None  # type: Union[None, Type[int], Dict[str, Any]]


class AnnotationTypeValue(Message):
  BLAME = 0x00040
  CODE_FINDINGS = 0x40000
  COMPILER = 0x00080
  COVERAGE = 0x00010
  DEPRECATED = 0x02000
  FINDBUGS = 0x00200
  LANG_COUNT = 0x04000
  LINK_TO_DEFINITION = 0x00001
  LINK_TO_URL = 0x00002
  LINT = 0x00020
  OFFLINE_QUERIES = 0x08000
  OVERRIDE = 0x01000
  TOOLS = 0x20000
  UNKNOWN = 0x00000
  XREF_SIGNATURE = 0x00004

  DESCRIPTOR = int


class AnnotationType(Message):
  DESCRIPTOR = {
      'id': AnnotationTypeValue,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.id = d.get('id', AnnotationTypeValue.UNKNOWN)  # type: int


class TextRange(Message):
  """A range inside a source file. All indices are 1-based and inclusive."""
  DESCRIPTOR = {
      'start_line': int,
      'start_column': int,
      'end_line': int,
      'end_column': int,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.start_line = d.get('start_line', 0)
    self.end_line = d.get('end_line', 0)
    self.start_column = d.get('start_column', 0)
    self.end_column = d.get('end_column', 0)

  def Contains(self, line, column):
    return not (line < self.start_line or line > self.end_line or
                (line == self.start_line and column < self.start_column) or
                (line == self.end_line and column > self.end_column))

  def Overlaps(self, other):
    assert isinstance(other, TextRange)

    def _RangeOverlap(s1, e1, s2, e2):
      """Returns true if the range [s1,e1] and [s2,e2] intersects. The
          ranges are inclusive."""
      return (s1 <= e1 and s2 <= e2) and not (e1 < s2 or e2 < s1)

    if not self.IsValid() or not other.IsValid():
      return False

    if not _RangeOverlap(self.start_line, self.end_line, other.start_line,
                         other.end_line):
      return False

    if _RangeOverlap(self.start_line + 1, self.end_line - 1,
                     other.start_line + 1, other.end_line - 1):
      return True

    if self.end_line == other.start_line and self.end_column < other.start_column:
      return False

    if other.end_line == self.start_line and other.end_column < self.start_column:
      return False

    return True

  def IsValid(self):
    return \
        self.start_line != 0 or \
        self.start_column != 0 or \
        self.end_line != 0 or \
        self.end_column != 0

  def Empty(self):
    return not self.IsValid()

  def __eq__(self, other):
    if not isinstance(other, TextRange):
      return False

    if not self.IsValid() or other.IsValid():
      return False

    return self.start_line == other.start_line and \
            self.start_column == other.start_column and \
            self.end_line == other.end_line and \
            self.end_column == other.end_column


class InternalLink(Message):
  DESCRIPTOR = {
      'package_name': str,
      'highlight_signature': str,  # A ' ' delimited list of tickets.
      'signature': str,  # A ' ' delimited list of tickets.
      'signature_hash': str,  # Always '' for Kythe.
      'path': str,

      # The range in the target path that should be considered the target of the
      # link.
      'range': TextRange,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.package_name = d.get('package_name', str())  # type: str
    self.highlight_signature = d.get('highlight_signature', str())  # type: str
    self.signature = d.get('signature', str())  # type: str
    self.signature_hash = d.get('signature_hash', str())  # type: str
    self.path = d.get('path', str())  # type: str
    self.range = d.get('range', TextRange())  # type: TextRange

  def MatchesSignature(self, signature):
    return signature in getattr(self, 'highlight_signature',
                                '').split(' ') or (signature in getattr(
                                    self, 'signature', '').split(' '))

  def GetSignatures(self):
    # type: () -> List[str]
    sigs = []
    if self.signature:
      sigs.extend(self.signature.split(' '))
    if self.highlight_signature:
      sigs.extend(self.highlight_signature.split(' '))
    return sigs

  def GetSignature(self):
    # type: () -> str
    sigs = self.GetSignatures()
    if len(sigs) == 0:
      return ""
    return sigs[0]


class XrefSignature(Message):
  DESCRIPTOR = {
      'highlight_signature': str,  # A space delimited list of tickets.
      'signature': str,  # A space delimited list of tickets.
      'signature_hash': str,  # Always '' for Kythe.
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.highlight_signature = d.get('highlight_signature', str())  # type: str
    self.signature = d.get('signature', str())  # type: str
    self.signature_hash = d.get('signature_hash', str())  # type: str

  def MatchesSignature(self, signature):
    return signature in getattr(self, 'highlight_signature',
                                '').split(' ') or (signature in getattr(
                                    self, 'signature', '').split(' '))

  def GetSignatures(self):
    # type: () -> List[str]
    sigs = []
    if self.signature:
      sigs.extend(self.signature.split(' '))
    if self.highlight_signature:
      sigs.extend(self.highlight_signature.split(' '))
    return sigs

  def GetSignature(self):
    # type: () -> str
    sigs = self.GetSignatures()
    if len(sigs) == 0:
      return ""
    return sigs[0]


class NodeEnumKind(Message):
  """DEPRECATED: Only used on Grok backend."""

  ALIAS_JOIN = 9100
  ANNOTATION = 900
  ARRAY = 5700
  BIGFLOAT = 3000
  BIGINT = 2900
  BOOLEAN = 2000
  CHANNEL = 6700
  CHAR = 2100
  CLASS = 500
  COMMENT = 9400
  COMMUNICATION = 3850
  COMPLEX = 2800
  CONSTRUCTOR = 1200
  CONST_TYPE = 5400
  DEF_DECL_JOIN = 9000
  DELIMITER = 10000
  DIAGNOSTIC = 4100
  DIRECTORY = 4000
  DOCUMENTATION = 9800
  DOCUMENTATION_TAG = 9900
  DYNAMIC_TYPE = 9300
  ENUM = 700
  ENUM_CONSTANT = 800
  FIELD = 1500
  FILE = 3900
  FIXED_POINT = 2600
  FLOAT = 2500
  FORWARD_DECLARATION = 5300
  FUNCTION = 1000
  FUNCTION_TYPE = 10200
  IMPORT = 8200
  INDEX_INFO = 31337
  INSTANCE = 4600
  INTEGER = 2400
  INTERFACE = 600
  LABEL = 11600
  LIST = 6300
  LOCAL = 1600
  LOST = 9600
  MAP = 6000
  MARKUP_ATTRIBUTE = 11300
  MARKUP_TAG = 11200
  MATRIX = 5800
  METHOD = 1100
  MODULE = 300
  NAME = 3300
  NAMESPACE = 100
  NULL_TYPE = 7300
  NUMBER = 3100
  OBJECT = 4500
  OPAQUE = 6500
  OPTION_TYPE = 5500
  PACKAGE = 200
  PACKAGE_JOIN = 9200
  PARAMETER = 1700
  PARAMETRIC_TYPE = 5600
  POINTER = 5000
  PROPERTY = 1900
  QUEUE = 6400
  RATIONAL = 2700
  REFERENCE_TYPE = 5100
  REGEXP = 2300
  RESTRICTION_TYPE = 10100
  RULE = 8100
  SEARCHABLE_IDENTIFIER = 11500
  SEARCHABLE_NAME = 9500
  SET = 5900
  STRING = 2200
  STRUCT = 400
  SYMBOL = 3200
  TAG_NAME = 11100
  TARGET = 8000
  TEMPLATE = 1400
  TEXT = 9700
  TEXT_MACRO = 1300
  THREAD = 6600
  TUPLE = 6100
  TYPE_ALIAS = 5200
  TYPE_DESCRIPTOR = 11400
  TYPE_SPECIALIZATION = 7000
  TYPE_VARIABLE = 7100
  TYPE_VARIABLE_TYPE = 10400
  UNION = 6200
  UNIT_TYPE = 6900
  UNRESOLVED_TYPE = 404
  USAGE = 3800
  USER_TYPE = 10300
  VALUE = 3400
  VARIABLE = 1800
  VARIADIC_TYPE = 7200
  VOID_TYPE = 6800

  DESCRIPTOR = int


class KytheNodeKind(Message):
  ABS = 100
  ABSVAR = 200
  ANCHOR = 300
  CONSTANT = 500
  DEPRECATED_CALLABLE = 400
  DOC = 550
  FILE = 600
  FUNCTION = 800
  FUNCTION_CONSTRUCTOR = 810
  FUNCTION_DESTRUCTOR = 820
  INTERFACE = 700
  LOOKUP = 900
  MACRO = 1000
  META = 1050
  NAME = 1100
  PACKAGE = 1200
  RECORD = 1300
  RECORD_CLASS = 1310
  RECORD_STRUCT = 1320
  RECORD_UNION = 1330
  SUM = 1400
  SUM_ENUM = 1410
  SUM_ENUM_CLASS = 1420
  TALIAS = 1500
  TAPP = 1600
  TBUILTIN = 1700
  TBUILTIN_ARRAY = 1705
  TBUILTIN_BOOLEAN = 1710
  TBUILTIN_BYTE = 1715
  TBUILTIN_CHAR = 1720
  TBUILTIN_DOUBLE = 1725
  TBUILTIN_FLOAT = 1730
  TBUILTIN_FN = 1735
  TBUILTIN_INT = 1740
  TBUILTIN_LONG = 1745
  TBUILTIN_PTR = 1750
  TBUILTIN_SHORT = 1755
  TBUILTIN_VOID = 1760
  TNOMINAL = 1800
  TSIGMA = 1850
  UNRESOLVED_TYPE = 0
  VARIABLE = 1900
  VARIABLE_FIELD = 1910
  VARIABLE_LOCAL = 1920
  VARIABLE_LOCAL_EXCEPTION = 1940
  VARIABLE_LOCAL_PARAMETER = 1930
  VARIABLE_LOCAL_RESOURCE = 1950
  VCS = 2000

  DESCRIPTOR = int


class Annotation(Message):
  DESCRIPTOR = {
      # Sent for OVERRIDE. Is an informative hover text like "Overrides
      # net::Foo::Callback".
      # Sent for BLAME with a semicolon separated list of Git revision, and
      # author.
      'content': str,
      'file_name': str,
      'internal_link': InternalLink,
      'is_implicit_target': bool,
      'kythe_xref_kind':
          KytheNodeKind,  # Not to be confused with KytheXrefKind.
      'range': TextRange,
      'status': int,
      'type': AnnotationType,
      'url': str,
      'xref_kind': NodeEnumKind,  # DEPRECATED
      'xref_signature': XrefSignature,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.content = d.get('content', "")  # type: str
    self.file_name = d.get('file_name', "")  # type: str
    self.internal_link = d.get('internal_link',
                               InternalLink())  # type: InternalLink
    self.is_implicit_target = d.get('is_implicit_target', False)  # type: bool
    self.kythe_xref_kind = d.get('kythe_xref_kind',
                                 KytheNodeKind.UNRESOLVED_TYPE)  # type: int
    self.range = d.get('range', TextRange())  # type: TextRange
    self.status = d.get('status', 0)  # type: int
    self.type = d.get('type', AnnotationType())  # type: AnnotationType
    self.url = d.get('url', "")  # type: str
    self.xref_signature = d.get('xref_signature',
                                XrefSignature())  # type: XrefSignature

  def MatchesSignature(self, signature):
    # type: (str) -> bool
    if self.type.id == AnnotationTypeValue.LINK_TO_DEFINITION:
      return self.internal_link.MatchesSignature(signature)
    if self.type.id == AnnotationTypeValue.XREF_SIGNATURE:
      return self.xref_signature.MatchesSignature(signature)
    return False

  def HasSignature(self):
    # type: () -> bool
    return self.type.id == AnnotationTypeValue.LINK_TO_DEFINITION or self.type.id == AnnotationTypeValue.XREF_SIGNATURE

  def GetSignature(self):
    # type: () -> Optional[str]
    if self.type.id == AnnotationTypeValue.LINK_TO_DEFINITION:
      return self.internal_link.GetSignature()
    if self.type.id == AnnotationTypeValue.XREF_SIGNATURE:
      return self.xref_signature.GetSignature()
    return None

  def GetSignatures(self):
    # type: () -> List[str]
    if self.type.id == AnnotationTypeValue.LINK_TO_DEFINITION:
      return self.internal_link.GetSignatures()
    if self.type.id == AnnotationTypeValue.XREF_SIGNATURE:
      return self.xref_signature.GetSignatures()
    return []


class FileSpec(Message):
  DESCRIPTOR = {
      'name': str,
      'package_name': str,
      'changelist': str,  # Last known Git commit.
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.name = d.get('name', '')  # type: str
    self.package_name = d.get('package_name', '')  # type: str
    self.changelist = d.get('changelist', '')  # type: str


class FormatType(Message):
  CARRIAGE_RETURN = 22
  CL_LINK = 33
  CODESEARCH_LINK = 36
  EXTERNAL_LINK = 31
  INCLUDE_QUERY = 35
  LINE = 1
  QUERY_MATCH = 40
  SNIPPET_QUERY_MATCH = 41
  SYNTAX_CLASS = 8
  SYNTAX_COMMENT = 5
  SYNTAX_CONST = 9
  SYNTAX_DEPRECATED = 11
  SYNTAX_DOC_NAME = 13
  SYNTAX_DOC_TAG = 12
  SYNTAX_ESCAPE_SEQUENCE = 10
  SYNTAX_KEYWORD = 3
  SYNTAX_KEYWORD_STRONG = 15
  SYNTAX_MACRO = 7
  SYNTAX_MARKUP_BOLD = 51
  SYNTAX_MARKUP_CODE = 54
  SYNTAX_MARKUP_ENTITY = 50
  SYNTAX_MARKUP_ITALIC = 52
  SYNTAX_MARKUP_LINK = 53
  SYNTAX_NUMBER = 6
  SYNTAX_PLAIN = 2
  SYNTAX_STRING = 4
  SYNTAX_TASK_TAG = 14
  TABS = 21
  TRAILING_SPACE = 20
  UNKNOWN_TYPE = 0
  USER_NAME_LINK = 32

  DESCRIPTOR = int


class FormatRange(Message):
  DESCRIPTOR = {
      'type': FormatType,
      'range': TextRange,
      'target': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.type = d.get('type', FormatType())  # type: FormatType
    self.range = d.get('range', TextRange())  # type: TextRange
    self.target = d.get('target', str())  # type: str


class FileType(Message):
  BINARY = 5
  CODE = 1
  DATA = 3
  DIR = 4
  DOC = 2
  SYMLINK = 6
  UNKNOWN = 0

  DESCRIPTOR = int


class AnnotatedText(Message):
  DESCRIPTOR = {'text': str, 'range': [FormatRange]}

  def __init__(self, **kwargs):
    d = kwargs
    self.text = d.get('text', str())  # type: str
    self.range = d.get('range', [])  # type: [FormatRange]

  def Empty(self):
    # type: () -> bool
    return self.text == ""


class CodeBlockType(Message):
  DESCRIPTOR = int

  ALLOCATION = 49
  ANONYMOUS_FUNCTION = 15
  BUILD_ARGUMENT = 25
  BUILD_BINARY = 21
  BUILD_GENERATOR = 24
  BUILD_LIBRARY = 23
  BUILD_RULE = 20
  BUILD_TEST = 22
  BUILD_VARIABLE = 26
  CLASS = 1
  COMMENT = 13
  DEFINE_CONST = 40
  DEFINE_MACRO = 41
  ENUM = 4
  ENUM_CONSTANT = 14
  ERROR = 0
  FIELD = 7
  FUNCTION = 8
  GROUP = 51
  INTERFACE = 2
  JOB = 47
  JS_ASSIGNMENT = 38
  JS_CONST = 31
  JS_FUNCTION_ASSIGNMENT = 39
  JS_FUNCTION_LITERAL = 37
  JS_GETTER = 35
  JS_GOOG_PROVIDE = 32
  JS_GOOG_REQUIRE = 33
  JS_LITERAL = 36
  JS_SETTER = 34
  JS_VAR = 30
  METHOD = 6
  NAMESPACE = 11
  PACKAGE = 17
  PROPERTY = 12
  RESERVED_27 = 27
  RESERVED_28 = 28
  RESERVED_29 = 29
  ROOT = -1
  SCOPE = 50
  SERVICE = 48
  STRUCT = 3
  TEMPLATE = 46
  TEST = 16
  TYPEDEF = 10
  UNION = 5
  VARIABLE = 9
  XML_TAG = 45


class Modifiers(Message):
  DESCRIPTOR = {
      '_global': bool,
      '_thread_local': bool,
      'abstract': bool,
      'anonymous': bool,
      'autogenerated': bool,
      'close_delimiter': bool,
      'constexpr_': bool,
      'declaration': bool,
      'definition': bool,
      'deprecated': bool,
      'discrete': bool,
      'dynamically_scoped': bool,
      'exported': bool,
      'file_scoped': bool,
      'foreign': bool,
      'getter': bool,
      'has_figment': bool,
      'immutable': bool,
      'implicit': bool,
      'inferred': bool,
      'is_figment': bool,
      'join_node': bool,
      'library_scoped': bool,
      'namespace_scoped': bool,
      'nonescaped': bool,
      'open_delimiter': bool,
      'operator': bool,
      'optional': bool,
      'package_scoped': bool,
      'parametric': bool,
      'predeclared': bool,
      'private': bool,
      'protected': bool,
      'public': bool,
      'receiver': bool,
      'register': bool,
      'renamed': bool,
      'repeated': bool,
      'setter': bool,
      'shadowing': bool,
      'signed': bool,
      'static': bool,
      'strict_math': bool,
      'synchronized': bool,
      'terminal': bool,
      'transient': bool,
      'unsigned': bool,
      'virtual': bool,
      'volatile': bool,
      'whitelisted': bool,
  }

  def __init__(self, **kwargs):
    self.__dict__ = kwargs


class CodeBlock(Message):
  DESCRIPTOR = {
      'child': [Message.PARENT_TYPE],
      'modifiers': Modifiers,
      'name': str,  # Unadorned name.
      'name_prefix': str,  # Class qualifiers. I.e. For a function named
      # net::Foo::Bar, where net is a namespace, name="Bar",
      # name_prefix="Foo::".
      'signature': str,  # Valid if .type == FUNCTION. The signature
      # includes the function parameters excluding the
      # function name. This is not a CodeSearch ticket.
      'text_range': TextRange,
      'type': CodeBlockType,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.child = d.get('child', [])  # type: [CodeBlock]
    self.modifiers = d.get('modifiers', Modifiers())  # type: Modifiers
    self.name = d.get('name', str())  # type: str
    self.name_prefix = d.get('name_prefix', str())  # type: str
    self.signature = d.get('signature', str())  # type: str
    self.text_range = d.get('text_range', TextRange())  # type: TextRange
    self.type = d.get('type', 0)  # type: int

  def Find(self, name="", type=CodeBlockType.ROOT):
    """Find the self or child CodeBlock that matches the name and type.

      The special *name* value of "*" matches all names.
      """

    if (self.name == name or name == "*") and self.type == type:
      return self
    for c in self.child:
      n = c.Find(name, type)
      if n is not None:
        return n
    return None


class GobInfo(Message):
  DESCRIPTOR = {
      'commit': str,  # Git commit
      'path': str,  # Path relative to repository
      'repo': str,  # Repository path. Chromium's is "chromium/chromium/src"
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.commit = d.get('commit', str())  # type: str
    self.path = d.get('path', str())  # type: str
    self.repo = d.get('repo', str())  # type: str


class FileInfo(Message):
  DESCRIPTOR = {
      'actual_name': str,
      'changelist_num': str,  # Git commit hash for indexed ToT.
      'codeblock': [CodeBlock],
      'content': AnnotatedText,
      'converted_content': AnnotatedText,
      'converted_lines': int,
      'fold_ranges': [TextRange],
      'generated': bool,  # Generated file?
      'generated_from': [str],
      'gob_info': GobInfo,
      'html_text': str,
      'language': str,  # "c++" etc.
      'license_path': str,
      'license_type': str,
      'lines': int,
      'md5': str,
      'mime_type': str,
      'name': str,
      'package_name': str,
      'revision_num': str,  # DEPRECATED
      'size': int,
      'type': FileType,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.actual_name = d.get('actual_name', str())  # type: str
    self.changelist_num = d.get('changelist_num', str())  # type: str
    self.codeblock = d.get('codeblock', [])  # type: List[CodeBlock]
    self.content = d.get('content', AnnotatedText())  # type: AnnotatedText
    self.converted_content = d.get('converted_content',
                                   AnnotatedText())  # type: AnnotatedText
    self.converted_lines = d.get('converted_lines', int())  # type: int
    self.fold_ranges = d.get('fold_ranges', [])  # type: List[TextRange]
    self.generated = d.get('generated', bool())  # type: bool
    self.generated_from = d.get('generated_from', [])  # type: List[str]
    self.gob_info = d.get('gob_info', GobInfo())  # type: GobInfo
    self.html_text = d.get('html_text', str())  # type: str
    self.language = d.get('language', str())  # type: str
    self.license_path = d.get('license_path', str())  # type: str
    self.license_type = d.get('license_type', str())  # type: str
    self.lines = d.get('lines', int())  # type: int
    self.md5 = d.get('md5', str())  # type: str
    self.mime_type = d.get('mime_type', str())  # type: str
    self.name = d.get('name', str())  # type: str
    self.package_name = d.get('package_name', str())  # type: str
    self.size = d.get('size', int())  # type: int
    self.type = d.get('type', FileType())  # type: FileType


class FileInfoResponse(Message):
  DESCRIPTOR = {
      'announcement': str,
      'error_message': str,
      'file_info': FileInfo,
      'return_code': int,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.announcement = d.get('announcement', str())  # type: str
    self.error_message = d.get('error_message', str())  # type: str
    self.file_info = d.get('file_info', FileInfo())  # type: FileInfo
    self.return_code = d.get('return_code', int())  # type: int


class FileInfoRequest(Message):
  DESCRIPTOR = {
      'file_spec': FileSpec.__class__,
      'fetch_html_content': bool,
      'fetch_outline': bool,
      'fetch_folding': bool,
      'fetch_generated_from': bool,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.file_spec = d.get('file_spec', FileSpec())  # type: FileSpec
    self.fetch_html_content = d.get('fetch_html_content', bool())  # type: bool
    self.fetch_outline = d.get('fetch_outline', bool())  # type: bool
    self.fetch_folding = d.get('fetch_folding', bool())  # type: bool
    self.fetch_generated_from = d.get('fetch_generated_from',
                                      bool())  # type: bool


class AnnotationResponse(Message):
  DESCRIPTOR = {
      'annotation': [Annotation],
      'file': str,  # Not populated
      'max_findings_reached': bool,
      'return_code': int,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.annotation = d.get('annotation', [])  # type: List[Annotation]
    self.file = d.get('file', str())  # type: str
    self.max_findings_reached = d.get('max_findings_reached',
                                      bool())  # type: bool
    self.return_code = d.get('return_code', int())  # type: int


class AnnotationRequest(Message):
  DESCRIPTOR = {
      'file_spec': FileSpec,
      'type': [AnnotationType],
      'md5': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.file_spec = d.get('file_spec', FileSpec())  # type: FileSpec
    self.type = d.get('type', [])  # type: List[AnnotationType]
    self.md5 = d.get('md5', str())  # type: str

  def AsQueryString(self):
    # type: () -> List[Tuple[str,str]]
    qs = Message.AsQueryString(self)
    if not self.md5:
      idx = qs.index(('file_spec', 'e'))
      qs.insert(idx + 1, ('md5', ''))
    return qs


class MatchReason(Message):
  DESCRIPTOR = {
      'blame': bool,
      'content': bool,
      'filename': bool,
      'filename_lineno': bool,
      'scoped_symbol': bool,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.blame = d.get('blame', bool())  # type: bool
    self.content = d.get('content', bool())  # type: bool
    self.filename = d.get('filename', bool())  # type: bool
    self.filename_lineno = d.get('filename_lineno', bool())  # type: bool
    self.scoped_symbol = d.get('scoped_symbol', bool())  # type: bool


class Snippet(Message):
  DESCRIPTOR = {
      'first_line_number': int,
      'match_reason': MatchReason,
      'scope': str,
      'text': AnnotatedText,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.first_line_number = d.get('first_line_number', int())  # type: int
    self.match_reason = d.get('match_reason',
                              MatchReason())  # type: MatchReason
    self.scope = d.get('scope', str())  # type: str
    self.text = d.get('text', AnnotatedText())  # type: AnnotatedText

  def Empty(self):
    # type: () -> bool
    return self.first_line_number == 0 or self.text.Empty()


class Node(Message):
  DESCRIPTOR = {
      # Take this example snippet:
      #
      # 03  void Foo(int a, int b) {
      # 04    Bar();
      # 05  }
      #
      # If this is a call graph node for Bar(), then call_scope_range would
      # cover "Foo" on line 3 (i.e. call_scope_range { start_line: 3,
      # start_column: 6, end_line: 3, end_column: 8 })
      #
      # call_site_range would cover the function call on line 4. I.e
      # call_site_range { start_line: 4, start_column: 3, end_line: 4,
      # end_column: 7 }
      'call_scope_range': TextRange,  # Range defining calling function name.
      'call_site_range': TextRange,  # Range defining call site.
      'children': [Message.PARENT_TYPE],  # Nodes corresponding to callsites of 
      'display_name': str,  # Deprecated.
      'edge_kind': str,  # Deprecated.
      'file_path': str,
      'identifier': str,
      'node_kind': KytheNodeKind,
      'override': bool,
      'package_name': str,
      'params': [str],  # For FUNCTION nodes, list of parameter names.
      # No type information present.
      'signature':
          str,  # Signature for call scope. I.e. thing at call_scope_range.
      'snippet': Snippet,
      'snippet_file_path': str,
      'snippet_package_name': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.call_scope_range = d.get('call_scope_range',
                                  TextRange())  # type: TextRange
    self.call_site_range = d.get('call_site_range',
                                 TextRange())  # type: TextRange
    self.children = d.get('children', [])  # type: [Node]
    self.display_name = d.get('display_name', str())  # type: str
    self.edge_kind = d.get('edge_kind', str())  # type: str
    self.file_path = d.get('file_path', str())  # type: str
    self.identifier = d.get('identifier', str())  # type: str
    self.node_kind = d.get('node_kind', int)  # type: int
    self.override = d.get('override', bool())  # type: bool
    self.package_name = d.get('package_name', str())  # type: str
    self.params = d.get('params', [])  # type: [str]
    self.signature = d.get('signature', str())  # type: str
    self.snippet = d.get('snippet', Snippet())  # type: Snippet
    self.snippet_file_path = d.get('snippet_file_path', str())  # type: str
    self.snippet_package_name = d.get('snippet_package_name',
                                      str())  # type: str


class CallGraphResponse(Message):
  DESCRIPTOR = {
      'debug_message': str,
      'estimated_total_number_results': int,
      'is_call_graph': bool,
      'is_from_kythe': bool,
      'kythe_next_page_token': str,
      'node': Node,
      'results_offset': int,
      'return_code': int,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.debug_message = d.get('debug_message', str())  # type: str
    self.estimated_total_number_results = d.get(
        'estimated_total_number_results', int())  # type: int
    self.is_call_graph = d.get('is_call_graph', bool())  # type: bool
    self.is_from_kythe = d.get('is_from_kythe', bool())  # type: bool
    self.kythe_next_page_token = d.get('kythe_next_page_token',
                                       str())  # type: str
    self.node = d.get('node', Node())  # type: Node
    self.results_offset = d.get('results_offset', int())  # type: int
    self.return_code = d.get('return_code', int())  # type: int


class CallGraphRequest(Message):
  DESCRIPTOR = {
      'file_spec': FileSpec,
      'max_num_results': int,
      'signature': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.file_spec = d.get('file_spec', FileSpec())  # type: FileSpec
    self.max_num_results = d.get('max_num_results', 100))  # type: int
    self.signature = d.get('signature', str())  # type: str


class EdgeEnumKind(Message):
  """Types of edge.

  DEPRECATED: Only used by Grok backend.
  """

  DESCRIPTOR = int

  ALLOWED_ACCESS_TO = 4500
  ANNOTATED_WITH = 5000
  ANNOTATION_OF = 5100
  BASE_TYPE = 1300
  BELONGS_TO_NAMESPACE = 7200
  BELONGS_TO_PACKAGE = 6900
  CALL = 2200
  CALLED_AT = 2300
  CALLGRAPH_FROM = 4700
  CALLGRAPH_TO = 4600
  CAPTURED_BY = 1200
  CAPTURES = 1100
  CATCHES = 6400
  CAUGHT_BY = 6500
  CHANNEL_USED_BY = 2351
  CHILD = 5300
  COMMENT_IN_FILE = 7400
  COMPOSING_TYPE = 1400
  CONSUMED_BY = 4100
  CONTAINS_COMMENT = 7500
  CONTAINS_DECLARATION = 5800
  CONTAINS_USAGE = 6000
  DECLARATION_IN_FILE = 5900
  DECLARATION_OF = 3200
  DECLARED_BY = 400
  DECLARES = 300
  DEFINITION_OF = 3400
  DIAGNOSTIC_OF = 5400
  DIRECTLY_INHERITED_BY = 1060
  DIRECTLY_INHERITS = 1050
  DIRECTLY_OVERRIDDEN_BY = 860
  DIRECTLY_OVERRIDES = 850
  DOCUMENTED_WITH = 7700
  DOCUMENTS = 7600
  ENCLOSED_USAGE = 4900
  EXTENDED_BY = 200
  EXTENDS = 100
  GENERATED_BY = 3100
  GENERATES = 3000
  GENERATES_NAME = 3150
  HAS_DECLARATION = 3300
  HAS_DEFINITION = 3500
  HAS_DIAGNOSTIC = 5500
  HAS_FIGMENT = 9200
  HAS_IDENTIFIER = 9400
  HAS_INPUT = 4000
  HAS_OUTPUT = 4200
  HAS_PROPERTY = 2800
  HAS_SELECTION = 10900
  HAS_TYPE = 1800
  IMPLEMENTED_BY = 600
  IMPLEMENTS = 500
  INHERITED_BY = 1000
  INHERITS = 900
  INITIALIZED_WITH = 9100
  INITIALIZES = 9000
  INJECTED_AT = 10500
  INJECTS = 10400
  INSTANTIATED_AT = 2500
  INSTANTIATION = 2400
  IS_FIGMENT_OF = 9300
  IS_IDENTIFIER_OF = 9500
  IS_TYPE_OF = 1900
  KEY_METHOD = 3600
  KEY_METHOD_OF = 3700
  MEMBER_SELECTED_AT = 10700
  NAMESPACE_CONTAINS = 7300
  NAME_GENERATED_BY = 3160
  OUTLINE_CHILD = 5700
  OUTLINE_PARENT = 5600
  OVERRIDDEN_BY = 800
  OVERRIDES = 700
  PACKAGE_CONTAINS = 6800
  PARAMETER_TYPE = 8800
  PARAMETER_TYPE_OF = 8900
  PARENT = 5200
  PRODUCED_BY = 4300
  PROPERTY_OF = 2900
  RECEIVES_FROM = 2353
  REFERENCE = 2600
  REFERENCED_AT = 2700
  REQUIRED_BY = 3900
  REQUIRES = 3800
  RESTRICTED_TO = 4400
  RETURNED_BY = 2100
  RETURN_TYPE = 2000
  SELECTED_FROM = 10800
  SELECTS_MEMBER_OF = 10600
  SENDS_TO = 2352
  SPECIALIZATION_OF = 1600
  SPECIALIZED_BY = 1700
  THROWGRAPH_FROM = 6700
  THROWGRAPH_TO = 6600
  THROWN_BY = 6300
  THROWS = 6200
  TREE_CHILD = 7900
  TREE_PARENT = 7800
  TYPE_PARAMETER = 1500
  TYPE_PARAMETER_OF = 1550
  USAGE_CONTEXT = 4800
  USAGE_IN_FILE = 6100
  USES_CHANNEL = 2350
  USES_VARIABLE = 7000
  VARIABLE_USED_IN = 7100
  XLANG_PROVIDES = 8600
  XLANG_PROVIDES_NAME = 8400
  XLANG_USES = 8700
  XLANG_USES_NAME = 8500


class KytheXrefKind(Message):
  DESCRIPTOR = int

  DEFINITION = 1
  DECLARATION = 2
  REFERENCE = 3

  OVERRIDES = 4
  OVERRIDDEN_BY = 5
  EXTENDS = 6
  EXTENDED_BY = 7

  INSTANTIATION = 8

  GENERATES = 10
  GENERATED_BY = 11

  ANNOTATES = 12
  ANNOTATED_BY = 13

  # These are manual additions for extending the xref lookup features.
  CALLS = -100  # Provided for symmetry. Not implemented.
  CALLED_BY = -101


class XrefTypeCount(Message):
  DESCRIPTOR = {
      'count': int,
      'type': str,
      'type_id': KytheXrefKind,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.count = d.get('count', int())  # type: int
    self.type = d.get('type', str())  # type: str
    self.type_id = d.get('type_id', KytheXrefKind())  # type: KytheXrefKind


class XrefSingleMatch(Message):
  DESCRIPTOR = {
      'line_number': int,
      'line_text': str,
      'type': str,
      'type_id': KytheXrefKind,
      'node_type': NodeEnumKind,  # DEPRECATED
      'grok_modifiers': Modifiers,  # DEPRECATED
      'signature': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.line_number = d.get('line_number', int())  # type: int
    self.line_text = d.get('line_text', str())  # type: str
    self.type = d.get('type', str())  # type: str
    self.type_id = d.get('type_id', KytheXrefKind())  # type: KytheXrefKind
    self.signature = d.get('signature', str())  # type: str


class XrefSearchResult(Message):
  DESCRIPTOR = {
      'file': FileSpec,
      'match': [XrefSingleMatch],
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.file = d.get('file', FileSpec())  # type: FileSpec
    self.match = d.get('match', [])  # type: List[XrefSingleMatch]


class XrefSearchResponse(Message):
  DESCRIPTOR = {
      'eliminated_type_count': [XrefTypeCount],
      'estimated_total_type_count': [XrefTypeCount],
      'from_kythe': bool,
      'kythe_next_page_token': str,
      'grok_total_number_of_results': int,  # DEPRECATED
      'search_result': [XrefSearchResult],
      'status': int,
      'status_message': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.eliminated_type_count = d.get('eliminated_type_count',
                                       [])  # type: List[XrefTypeCount]
    self.estimated_total_type_count = d.get('estimated_total_type_count',
                                            [])  # type: List[XrefTypeCount]
    self.from_kythe = d.get('from_kythe', bool())  # type: bool
    self.kythe_next_page_token = d.get('kythe_next_page_token',
                                       str())  # type: str
    self.search_result = d.get('search_result',
                               [])  # type: List[XrefSearchResult]
    self.status = d.get('status', int())  # type: int
    self.status_message = d.get('status_message', str())  # type: str


class XrefSearchRequest(Message):
  DESCRIPTOR = {
      'edge_filter': [EdgeEnumKind],  # DEPRECATED
      'file_spec': FileSpec,
      'max_num_results': int,
      'query': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.file_spec = d.get('file_spec', FileSpec())  # type: FileSpec
    self.max_num_results = d.get('max_num_results', 100)  # type: int
    self.query = d.get('query', str())  # type: str


class VanityGitOnBorgHostname(Message):
  DESCRIPTOR = {
      'name': str,
      'hostname': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.name = d.get('name', str())  # type: str
    self.hostname = d.get('hostname', str())  # type: str


class InternalPackage(Message):
  DESCRIPTOR = {
      'browse_path_prefix': str,
      'cs_changelist_num': str,
      'grok_languages': [str],
      'grok_name': str,
      'grok_path_prefix': [str],
      'id': str,
      'kythe_languages': [str],
      'name': str,
      'repo': str,
      'vanity_git_on_borg_hostnames': [VanityGitOnBorgHostname],
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.browse_path_prefix = d.get('browse_path_prefix', str())  # type: str
    self.cs_changelist_num = d.get('cs_changelist_num', str())  # type: str
    self.grok_languages = d.get('grok_languages', [])  # type: List[str]
    self.grok_name = d.get('grok_name', str())  # type: str
    self.grok_path_prefix = d.get('grok_path_prefix', [])  # type: List[str]
    self.id = d.get('id', str())  # type: str
    self.kythe_languages = d.get('kythe_languages', [])  # type: List[str]
    self.name = d.get('name', str())  # type: str
    self.repo = d.get('repo', str())  # type: str
    self.vanity_git_on_borg_hostnames = d.get(
        'vanity_git_on_borg_hostnames',
        [])  # type: List[VanityGitOnBorgHostname]


class StatusResponse(Message):
  DESCRIPTOR = {
      'announcement': str,
      'build_label': str,
      'internal_package': [InternalPackage],
      'success': bool,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.announcement = d.get('announcement', str())  # type: str
    self.build_label = d.get('build_label', str())  # type: str
    self.internal_package = d.get('internal_package',
                                  [])  # type: List[InternalPackage]
    self.success = d.get('success', bool())  # type: bool


class DirInfoResponseChild(Message):
  DESCRIPTOR = {
      'is_deleted': bool,
      'is_directory': bool,
      'name': str,
      'package_id': str,
      'path': str,
      'revision_num': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.is_deleted = d.get('is_deleted', bool())  # type: bool
    self.is_directory = d.get('is_directory', bool())  # type: bool
    self.name = d.get('name', str())  # type: str
    self.package_id = d.get('package_id', str())  # type: str
    self.path = d.get('path', str())  # type: str
    self.revision_num = d.get('revision_num', str())  # type: str


class DirInfoResponseParent(Message):
  DESCRIPTOR = {
      'name': str,
      'path': str,
      'package_id': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.name = d.get('name', str())  # type: str
    self.path = d.get('path', str())  # type: str
    self.package_id = d.get('package_id', str())  # type: str


class DirInfoResponse(Message):
  DESCRIPTOR = {
      'child': [DirInfoResponseChild],
      'generated': bool,
      'gob_info': GobInfo,
      'name': str,
      'package_id': str,
      'parent': [DirInfoResponseParent],
      'path': str,
      'success': bool,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.child = d.get('child', [])  # type: List[DirInfoResponseChild]
    self.generated = d.get('generated', bool())  # type: bool
    self.gob_info = d.get('gob_info', GobInfo())  # type: GobInfo
    self.name = d.get('name', str())  # type: str
    self.package_id = d.get('package_id', str())  # type: str
    self.parent = d.get('parent', [])  # type: List[DirInfoResponseParent]
    self.path = d.get('path', str())  # type: str
    self.success = d.get('success', bool())  # type: bool


class DirInfoRequest(Message):
  DESCRIPTOR = {
      'file_spec': FileSpec,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.file_spec = d.get('file_spec', FileSpec())  # type: FileSpec


class FileResult(Message):
  DESCRIPTOR = {
      'display_name': AnnotatedText,
      'file': FileSpec,
      'license': FileSpec,
      'license_type': str,
      'size': int,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.display_name = d.get('display_name',
                              AnnotatedText())  # type: AnnotatedText
    self.file = d.get('file', FileSpec())  # type: FileSpec
    self.license = d.get('license', FileSpec())  # type: FileSpec
    self.license_type = d.get('license_type', str())  # type: str
    self.size = d.get('size', int())  # type: int


class SingleMatch(Message):
  DESCRIPTOR = {
      'line_number': int,
      'line_text': str,
      'match_length': int,
      'match_offset': int,
      'post_context_num_lines': int,
      'post_context_text': str,
      'pre_context_num_lines': int,
      'pre_context_text': str,
      'score': int,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.line_number = d.get('line_number', int())  # type: int
    self.line_text = d.get('line_text', str())  # type: str
    self.match_length = d.get('match_length', int())  # type: int
    self.match_offset = d.get('match_offset', int())  # type: int
    self.post_context_num_lines = d.get('post_context_num_lines',
                                        int())  # type: int
    self.post_context_text = d.get('post_context_text', str())  # type: str
    self.pre_context_num_lines = d.get('pre_context_num_lines',
                                       int())  # type: int
    self.pre_context_text = d.get('pre_context_text', str())  # type: str
    self.score = d.get('score', int())  # type: int


class SearchResult(Message):
  DESCRIPTOR = {
      'best_matching_line_number': int,
      'children': [str],
      'docid': str,
      'duplicate': [FileResult],
      'full_history_search': bool,
      'has_unshown_matches': bool,
      'hit_max_matches': bool,
      'is_augmented': bool,
      'language': str,
      'match': [SingleMatch],
      'match_reason': MatchReason,
      'num_duplicates': int,
      'num_matches': int,
      'snippet': [Snippet],
      'top_file': FileResult,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.best_matching_line_number = d.get('best_matching_line_number',
                                           int())  # type: int
    self.children = d.get('children', [])  # type: List[str]
    self.docid = d.get('docid', str())  # type: str
    self.duplicate = d.get('duplicate', [])  # type: List[FileResult]
    self.has_unshown_matches = d.get('has_unshown_matches',
                                     bool())  # type: bool
    self.hit_max_matches = d.get('hit_max_matches', bool())  # type: bool
    self.is_augmented = d.get('is_augmented', bool())  # type: bool
    self.language = d.get('language', str())  # type: str
    self.match = d.get('match', [])  # type: List[SingleMatch]
    self.match_reason = d.get('match_reason',
                              MatchReason())  # type: MatchReason
    self.num_duplicates = d.get('num_duplicates', int())  # type: int
    self.num_matches = d.get('num_matches', int())  # type: int
    self.snippet = d.get('snippet', [])  # type: List[Snippet]
    self.top_file = d.get('top_file', FileResult())  # type: FileResult


class SearchResponse(Message):
  DESCRIPTOR = {
      'estimated_total_number_of_results': int,
      'hit_max_matches_per_file': bool,
      'hit_max_results': bool,
      'hit_max_to_score': bool,
      'maybe_skipped_documents': bool,
      'next_page_token': str,
      'results_offset': int,
      'search_result': [SearchResult],
      'status': int,
      'status_message': str,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.estimated_total_number_of_results = d.get(
        'estimated_total_number_of_results', int())  # type: int
    self.hit_max_matches_per_file = d.get('hit_max_matches_per_file',
                                          bool())  # type: bool
    self.hit_max_results = d.get('hit_max_results', bool())  # type: bool
    self.hit_max_to_score = d.get('hit_max_to_score', bool())  # type: bool
    self.maybe_skipped_documents = d.get('maybe_skipped_documents',
                                         bool())  # type: bool
    self.results_offset = d.get('results_offset', int())  # type: int
    self.search_result = d.get('search_result', [])  # type: List[SearchResult]
    self.status = d.get('status', int())  # type: int
    self.status_message = d.get('status_message', str())  # type: str


class SearchRequest(Message):
  DESCRIPTOR = {
      'exhaustive': bool,
      'file_sizes': bool,
      'full_history_search': bool,
      'lines_context': int,
      'max_num_results': int,
      'page_token': str,
      'query': str,
      'results_offset': int,
      'return_all_duplicates': bool,
      'return_all_snippets': bool,
      'return_local_augmented_results': bool,
      'return_decorated_snippets': bool,
      'return_directories': bool,
      'return_line_matches': bool,
      'return_snippets': bool,
      'sort_results': bool,
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.exhaustive = d.get('exhaustive', bool())  # type: bool
    self.lines_context = d.get('lines_context', int())  # type: int
    self.max_num_results = d.get('max_num_results', 100)  # type: int
    self.query = d.get('query', str())  # type: str
    self.return_all_duplicates = d.get('return_all_duplicates',
                                       bool())  # type: bool
    self.return_all_snippets = d.get('return_all_snippets',
                                     bool())  # type: bool
    self.return_decorated_snippets = d.get('return_decorated_snippets',
                                           bool())  # type: bool
    self.return_directories = d.get('return_directories', bool())  # type: bool
    self.return_line_matches = d.get('return_line_matches',
                                     bool())  # type: bool
    self.return_snippets = d.get('return_snippets', bool())  # type: bool


class StatusRequest(Message):
  DESCRIPTOR = {}  # type: Dict[str,Any]


class CompoundResponse(Message):
  DESCRIPTOR = {
      'annotation_response': [AnnotationResponse],
      'call_graph_response': [CallGraphResponse],
      'dir_info_response': [DirInfoResponse],
      'file_info_response': [FileInfoResponse],
      'search_response': [SearchResponse],
      'status_response': [StatusResponse],
      'xref_search_response': [XrefSearchResponse],
      'elapsed_ms': int,  # Time taken to process request.
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.annotation_response = d.get(
        'annotation_response', None)  # type: Optional[List[AnnotationResponse]]
    self.call_graph_response = d.get(
        'call_graph_response', None)  # type: Optional[List[CallGraphResponse]]
    self.dir_info_response = d.get(
        'dir_info_response', None)  # type: Optional[List[DirInfoResponse]]
    self.file_info_response = d.get(
        'file_info_response', None)  # type: Optional[List[FileInfoResponse]]
    self.search_response = d.get('search_response',
                                 None)  # type: Optional[List[SearchResponse]]
    self.status_response = d.get('status_response',
                                 None)  # type: Optional[List[StatusResponse]]
    self.xref_search_response = d.get(
        'xref_search_response',
        None)  # type: Optional[List[XrefSearchResponse]]
    self.elapsed_ms = d.get('elapsed_ms', 0)


class CompoundRequest(Message):
  DESCRIPTOR = {
      'annotation_request': [AnnotationRequest],
      'call_graph_request': [CallGraphRequest],
      'dir_info_request': [DirInfoRequest],
      'file_info_request': [FileInfoRequest],
      'search_request': [SearchRequest],
      'status_request': [StatusRequest],
      'xref_search_request': [XrefSearchRequest],
  }

  def __init__(self, **kwargs):
    d = kwargs
    self.annotation_request = d.get(
        'annotation_request', None)  # type: Optional[List[AnnotationRequest]]
    self.call_graph_request = d.get(
        'call_graph_request', None)  # type: Optional[List[CallGraphRequest]]
    self.dir_info_request = d.get('dir_info_request',
                                  None)  # type: Optional[List[DirInfoRequest]]
    self.file_info_request = d.get(
        'file_info_request', None)  # type: Optional[List[FileInfoRequest]]
    self.search_request = d.get('search_request',
                                None)  # type: Optional[List[SearchRequest]]
    self.status_request = d.get('status_request',
                                None)  # type: Optional[List[StatusRequest]]
    self.xref_search_request = d.get(
        'xref_search_request', None)  # type: Optional[List[XrefSearchRequest]]
