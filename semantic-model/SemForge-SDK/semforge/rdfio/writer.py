"""Editing a Turtle artifact in place, touching only what changed (P2).

The edit is a text insertion located by the block index, not a reserialisation.
Everything outside the edited statement is byte-identical afterwards, and so is
everything inside it that the edit did not add -- including comments, which
rdflib would have dropped and which in the kms shapes are the only record of why
several constraints are written the way they are.
"""

import re

from ..errors import PackageError
from .turtle_index import TurtleIndex

INDENT = '    '


def _insertion_point(source, block):
    """Offset just before the statement's terminating '.', and its indent.

    Inserting there appends a new predicate-object to the subject rather than
    starting a new statement, which is what keeps the diff to the shape.
    """
    i = block.end - 1                      # the '.' itself
    while i > block.start and source[i - 1].isspace():
        i -= 1
    line_start = source.rfind('\n', block.start, i) + 1
    indent = re.match(r'[ \t]*', source[line_start:]).group(0) or INDENT
    return i, indent


def property_constraint_text(path, parameters, indent=INDENT):
    """A sh:property block for one attribute.

    Values are emitted as written by the caller: they are Turtle terms, and
    quoting them here would turn every IRI into a string.
    """
    lines = [f'{indent}sh:property [ sh:path {path} ;']
    for name, value in parameters:
        lines.append(f'{indent}{INDENT}{name} {value} ;')
    lines[-1] = lines[-1].removesuffix(' ;') + ' ]'
    # The leading ' ;' joins this to the predicate-object list already there;
    # no trailing one, because the statement's own '.' follows.
    return ' ;\n' + '\n'.join(lines)


def add_property_constraint(path_or_source, shape, attribute_path, parameters,
                            source=None):
    """Add a sh:property constraint to an existing shape.

    Returns the new file content. Raises PackageError when the shape is not in
    this file -- silently appending a second statement for the same subject
    would be valid Turtle and a confusing diff.
    """
    if source is None:
        with open(path_or_source, encoding='utf-8') as handle:
            source = handle.read()
        path = path_or_source
    else:
        path = ''

    index = TurtleIndex(source, path=path)
    block = index.block_for(shape)
    if block is None:
        raise PackageError(
            f'{shape} is not a statement in {path or "this file"}; '
            f'nothing to add a constraint to')

    at, indent = _insertion_point(source, block)
    text = property_constraint_text(attribute_path, parameters, indent)
    return source[:at] + text + '\n' + source[at:]
