"""A byte-span index over a Turtle file, keyed by subject (H3).

Invariant P2 says an edit through the cooked API changes only the triples
backing the edited element. rdflib cannot do that: it parses to a graph and
serialises the whole file fresh, which reorders statements, reassigns prefixes
and drops every comment. The kms shapes carry load-bearing comments -- the
explanation of why CartridgeShape needs a two-hop inverse path exists nowhere
else -- so a writer built on rdflib alone would delete the reasoning behind the
model on its first edit.

The plan timeboxed a spike (tree-sitter, or a purpose-built tokenizer) with
shape-block rewriting as the fallback. The tokenizer won: Turtle's statement
grammar is small, and what is needed is spans rather than semantics. It also
pays for itself twice, because the same index gives every shape a file:line
locator -- which is what provenance reports and what an editor will need.

What it understands, because each of these can hide a statement terminator:

  * comments      # to end of line, but NOT inside a string or an IRI
  * strings       "..." '...' \"\"\"...\"\"\" '''...''', with backslash escapes
  * nesting       [ ] blank node property lists, ( ) collections
  * directives    @prefix / @base / PREFIX / BASE, which are not subjects

It is not a Turtle parser and does not try to be. It locates statements; rdflib
remains the authority on what they mean.
"""

import re
from dataclasses import dataclass

DIRECTIVE = re.compile(r'^\s*(?:@?(?:prefix|base)\b)', re.IGNORECASE)
# The subject at the head of a statement: <iri>, prefix:name, or :name.
SUBJECT = re.compile(r'\s*(?:<(?P<iri>[^>]*)>|(?P<curie>[A-Za-z_][\w.-]*:[\w.-]*|:[\w.-]+))')


@dataclass(frozen=True)
class Block:
    """One Turtle statement: its subject, its text span and its line span."""
    subject: str          # IRI when resolvable, else the prefixed form as written
    raw_subject: str      # exactly as written in the file
    start: int            # byte offset of the first character
    end: int              # byte offset just past the terminating '.'
    start_line: int       # 1-based
    end_line: int

    def text(self, source):
        return source[self.start:self.end]


def _skip_string(text, i):
    """Return the index just past the string literal starting at i."""
    quote = text[i]
    triple = text[i:i + 3] in ('"""', "'''")
    delimiter = text[i:i + 3] if triple else quote
    i += len(delimiter)
    while i < len(text):
        if text[i] == '\\':
            i += 2
            continue
        if text.startswith(delimiter, i):
            return i + len(delimiter)
        i += 1
    return i  # unterminated; caller stops at EOF


def _statement_spans(text):
    """(start, end) for every top-level statement, terminator included."""
    spans = []
    i = 0
    start = None
    depth = 0
    while i < len(text):
        char = text[i]
        if char == '<':
            # An IRI. It must be skipped as one token, because a '#' inside it
            # is a fragment, not a comment -- reading <...shacl#> as a comment
            # swallowed the statement terminator and merged three statements
            # with the shape that followed them.
            closing = text.find('>', i)
            newline = text.find('\n', i)
            if closing != -1 and (newline == -1 or closing < newline):
                if start is None:
                    start = i
                i = closing + 1
                continue
        if char == '#':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        if char in '"\'':
            if start is None:
                start = i
            i = _skip_string(text, i)
            continue
        if char in '[(':
            if start is None:
                start = i
            depth += 1
        elif char in '])':
            depth -= 1
        elif char == '.' and depth == 0 and start is not None:
            # A '.' inside a number or a prefixed name is not a terminator.
            following = text[i + 1:i + 2]
            if following == '' or following.isspace():
                spans.append((start, i + 1))
                start = None
                i += 1
                continue
        elif not char.isspace() and start is None:
            start = i
        i += 1
    return spans


def _resolve(raw, prefixes, base):
    if raw.startswith('<'):
        iri = raw[1:-1]
        return base + iri if base and not re.match(r'^[a-z][a-z0-9+.-]*:', iri, re.I) else iri
    prefix, _, name = raw.partition(':')
    namespace = prefixes.get(prefix)
    return namespace + name if namespace else raw


def _prefixes(text):
    found = {}
    base = ''
    for match in re.finditer(
            r'^\s*@?(prefix|base)\s+(?:([\w.-]*):)?\s*<([^>]*)>\s*\.?',
            text, re.IGNORECASE | re.MULTILINE):
        kind, prefix, iri = match.group(1).lower(), match.group(2), match.group(3)
        if kind == 'base':
            base = iri
        else:
            found[prefix or ''] = iri
    return found, base


class TurtleIndex:
    """Statement spans of one Turtle file, addressable by subject IRI."""

    def __init__(self, source, path=''):
        self.source = source
        self.path = path
        prefixes, base = _prefixes(source)
        self.blocks = []
        for start, end in _statement_spans(source):
            chunk = source[start:end]
            if DIRECTIVE.match(chunk):
                continue
            match = SUBJECT.match(chunk)
            if not match:
                continue
            raw = match.group(0).strip()
            self.blocks.append(Block(
                subject=_resolve(raw, prefixes, base),
                raw_subject=raw,
                start=start, end=end,
                start_line=source.count('\n', 0, start) + 1,
                end_line=source.count('\n', 0, end) + 1))
        self._by_subject = {block.subject: block for block in self.blocks}

    def block_for(self, subject):
        return self._by_subject.get(str(subject))

    def locator(self, subject):
        """'file:line' for a subject, or '' when it is not in this file."""
        block = self.block_for(subject)
        if block is None:
            return ''
        return f'{self.path}:{block.start_line}' if self.path else str(block.start_line)

    def __len__(self):
        return len(self.blocks)


def index_file(path):
    with open(path, encoding='utf-8') as handle:
        return TurtleIndex(handle.read(), path=path)
