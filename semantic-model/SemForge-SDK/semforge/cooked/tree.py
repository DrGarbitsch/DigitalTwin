"""The cooked view over a package's constraints (manifest section 2.2).

Raw and cooked are two views of ONE state, so this is a projection of the shapes
file rather than a model beside it. Every node addresses a real span of text,
and every edit rewrites that span -- which is what makes invariant S1 hold by
construction: there is nothing the cooked view can express that raw cannot,
because a cooked edit IS a raw edit.

The tree it builds:

    Filter                      entity type (sh:targetClass)
    └── hasStrength             attribute
        ├── count 1..1          constraints on the ATTRIBUTE: how many instances
        ├── nodeKind BlankNode
        └── value               the value slot
            ├── 0.0 <= x        constraints on the VALUE: what it may be
            └── <= 100.0

Two things are deliberately visible but not editable here. Connectives
(sh:or, sh:node) are structure rather than a parameter, and SPARQL bodies are
not plausibly a form. Both are shown with their raw text so the tree does not
lie about what a shape contains -- invariant S2: content the cooked view cannot
project is preserved and marked, never hidden and never dropped.
"""

from dataclasses import dataclass, field

from rdflib.namespace import SH

from ..errors import PackageError
from ..rdfio import (find_block, index_file, property_blocks, remove_parameter,
                     set_parameter)
from ..validate.normalise import curie, local
from ..validate.shapes import node_shapes

# Parameters a form can honestly offer: one name, one scalar value.
EDITABLE = {
    'sh:minCount': ('count', 'integer'),
    'sh:maxCount': ('count', 'integer'),
    'sh:datatype': ('datatype', 'iri'),
    'sh:class': ('class', 'iri'),
    'sh:nodeKind': ('nodeKind', 'iri'),
    'sh:minInclusive': ('range', 'number'),
    'sh:maxInclusive': ('range', 'number'),
    'sh:minExclusive': ('range', 'number'),
    'sh:maxExclusive': ('range', 'number'),
    'sh:minLength': ('length', 'integer'),
    'sh:maxLength': ('length', 'integer'),
    'sh:pattern': ('pattern', 'string'),
}

# Structure, not parameters. Shown so the tree is honest; edited in raw.
RAW_ONLY = {'sh:or', 'sh:and', 'sh:xone', 'sh:not', 'sh:node', 'sh:in'}

VALUE_PATHS = {'ngsild:hasValue', 'ngsild:hasObject', 'ngsild:hasValueList',
               'ngsild:hasJSON'}


@dataclass
class CookedNode:
    kind: str                  # type | attribute | slot | constraint | raw
    label: str
    detail: str = ''
    shape: str = ''            # owning shape IRI
    path_chain: list = field(default_factory=list)
    parameter: str = ''
    value: str = ''
    editable: bool = False
    children: list = field(default_factory=list)

    @property
    def address(self):
        """What an edit needs: which shape, which nesting, which parameter."""
        return {'shape': self.shape, 'path': list(self.path_chain),
                'parameter': self.parameter}


def _constraint_nodes(block, shape, chain):
    nodes = []
    for name in sorted(block.parameters):
        if name == 'sh:order':
            continue
        _, _, value = block.parameters[name]
        if name in RAW_ONLY:
            nodes.append(CookedNode(
                kind='raw', label=f'{local(name)} (raw only)',
                detail='structure, not a parameter — edit in the .ttl',
                shape=shape, path_chain=list(chain), parameter=name,
                value=value.strip()[:60]))
        elif name in EDITABLE:
            nodes.append(CookedNode(
                kind='constraint', label=local(name), detail=value,
                shape=shape, path_chain=list(chain), parameter=name,
                value=value, editable=True))
        else:
            nodes.append(CookedNode(
                kind='raw', label=local(name), detail=value,
                shape=shape, path_chain=list(chain), parameter=name,
                value=value))
    return nodes


def _short(path):
    """`iffBaseEntities:hasFilter` and `<http://…/hasFilter>` both read hasFilter."""
    return local(path.strip('<>')).split(':')[-1]


def _attribute_node(block, shape, chain):
    chain = chain + [block.path]
    node = CookedNode(kind='attribute', label=_short(block.path),
                      detail=block.path, shape=shape, path_chain=list(chain))
    node.children.extend(_constraint_nodes(block, shape, chain))

    for child in block.children:
        if child.path in VALUE_PATHS:
            slot = CookedNode(
                kind='slot', label='value',
                detail=_short(child.path), shape=shape,
                path_chain=chain + [child.path])
            slot.children.extend(
                _constraint_nodes(child, shape, chain + [child.path]))
            node.children.append(slot)
        else:
            node.children.append(_attribute_node(child, shape, chain))
    return node


def build_tree(package):
    """Entity types -> attributes -> constraints, for the whole package."""
    source_path = package.sources['shapes']
    with open(source_path, encoding='utf-8') as handle:
        text = handle.read()
    index = index_file(source_path)

    by_type = {}
    for shape in node_shapes(package.shapes):
        block = index.block_for(shape)
        if block is None:
            continue
        groups = property_blocks(text, block)
        targets = [local(t) for t in package.shapes.objects(shape, SH.targetClass)]
        label = targets[0] if targets else local(shape)

        shape_node = CookedNode(
            kind='shape', label=curie(package.shapes, shape),
            detail=f'{len(groups)} attribute(s)', shape=str(shape))
        for group in groups:
            shape_node.children.append(_attribute_node(group, str(shape), []))
        if (shape, SH.sparql, None) in package.shapes:
            shape_node.children.append(CookedNode(
                kind='raw', label='SPARQL constraint',
                detail='a query body is not a form — edit in the .ttl',
                shape=str(shape)))
        if (shape, SH.rule, None) in package.shapes:
            shape_node.children.append(CookedNode(
                kind='raw', label='SPARQL rule',
                detail='a rule body is not a form — edit in the .ttl',
                shape=str(shape)))
        by_type.setdefault(label, []).append(shape_node)

    roots = []
    for label in sorted(by_type):
        node = CookedNode(kind='type', label=label,
                          detail=f'{len(by_type[label])} shape(s)')
        node.children = by_type[label]
        roots.append(node)
    return roots


def _locate(package, shape, path_chain):
    source_path = package.sources['shapes']
    with open(source_path, encoding='utf-8') as handle:
        text = handle.read()
    block = index_file(source_path).block_for(shape)
    if block is None:
        raise PackageError(f'{shape} is not a statement in {source_path}')
    target = find_block(property_blocks(text, block), path_chain)
    if target is None:
        raise PackageError(
            f'no property shape at {" / ".join(path_chain)} in {local(shape)}')
    return source_path, text, target


def _write_verified(source_path, text):
    """Write only after the result parses.

    A cooked edit that produces invalid Turtle would take the file with it, and
    the whole point of editing spans rather than reserialising is that the file
    survives.
    """
    from rdflib import Graph

    Graph().parse(data=text, format='turtle')
    with open(source_path, 'w', encoding='utf-8') as handle:
        handle.write(text)


def apply_edit(package, shape, path_chain, parameter, value):
    """Set one constraint parameter. Returns (path, bytes changed)."""
    if parameter not in EDITABLE:
        raise PackageError(
            f'{parameter} is not editable in the cooked view: it is structure '
            f'rather than a parameter. Edit it in the .ttl.')
    source_path, text, target = _locate(package, shape, path_chain)
    updated = set_parameter(text, target, parameter, value)
    _write_verified(source_path, updated)
    return source_path, sum(1 for a, b in zip(text, updated) if a != b) or \
        abs(len(updated) - len(text))


def remove_constraint(package, shape, path_chain, parameter):
    source_path, text, target = _locate(package, shape, path_chain)
    updated = remove_parameter(text, target, parameter)
    _write_verified(source_path, updated)
    return source_path, len(text) - len(updated)


def flatten(nodes, depth=0):
    """Depth-first, for tests and for a text rendering of the tree."""
    for node in nodes:
        yield depth, node
        yield from flatten(node.children, depth + 1)


def render(nodes):
    lines = []
    for depth, node in flatten(nodes):
        mark = '*' if node.editable else ' '
        detail = f'  {node.detail}' if node.detail else ''
        lines.append(f'{"  " * depth}{mark} {node.label}{detail}')
    return lines
