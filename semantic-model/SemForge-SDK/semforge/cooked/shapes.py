"""Shapes as SHACL writes them: each one with what it targets, in words.

A shape is not tied to an entity type. It selects focus nodes by class, by
named node, by the subjects or objects of a predicate, by a SPARQL query, or
implicitly when the shape is itself a class -- or it has no target and is
reached from another shape through sh:node. The Types view reads constraints
by type; this is the other half, every shape whatever it targets, so a shape
that belongs to no type still has somewhere to be found.
"""

import re

from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH

from ..errors import PackageError
from ..validate.normalise import curie
from ..validate.shapes import every_node_shape

NGSILD_OBJECT = 'https://uri.etsi.org/ngsi-ld/hasObject'


def _name(package, iri):
    """A short name for a term in a target: the local part, unless the
    shapes graph has nothing better than the full IRI."""
    text = curie(package.shapes, URIRef(iri))
    return text.split(':', 1)[1] if ':' in text and not text.startswith('http') \
        else text


def targets(package, shape):
    """[{kind, value, short, text}] -- one per target the shape declares."""
    graph = package.shapes
    shape = URIRef(shape)
    out = []
    for cls in graph.objects(shape, SH.targetClass):
        name = _name(package, cls)
        out.append({'kind': 'class', 'value': str(cls), 'short': f'targets {name}',
                    'text': f'every {name}, and every subclass of it'})
    for node in graph.objects(shape, SH.targetNode):
        out.append({'kind': 'node', 'value': str(node), 'short': f'targets {node}',
                    'text': f'the node {node}'})
    for predicate in graph.objects(shape, SH.targetSubjectsOf):
        name = _name(package, predicate)
        out.append({'kind': 'subjectsOf', 'value': str(predicate),
                    'short': f'targets subjects of {name}',
                    'text': f'everything that has {name}'})
    for predicate in graph.objects(shape, SH.targetObjectsOf):
        name = _name(package, predicate)
        said = ('every entity a Relationship points at'
                if str(predicate) == NGSILD_OBJECT
                else f'everything {name} points at')
        out.append({'kind': 'objectsOf', 'value': str(predicate),
                    'short': f'targets objects of {name}', 'text': said})
    for target in graph.objects(shape, SH.target):
        query = graph.value(target, SH.select)
        out.append({'kind': 'sparql', 'value': str(query or ''),
                    'short': 'SPARQL target',
                    'text': 'the nodes a SPARQL query selects (SHACL-AF)'})
    if (shape, RDF.type, RDFS.Class) in graph or (shape, RDF.type, OWL.Class) in graph:
        name = _name(package, shape)
        out.append({'kind': 'implicit', 'value': str(shape),
                    'short': f'targets {name} (implicitly)',
                    'text': f'every {name}: the shape is itself the class'})
    return out


def used_by(package, shape):
    """The named shapes that reach this one through sh:node, anywhere in
    their body."""
    graph = package.shapes
    shape = URIRef(shape)
    users = []
    for other in every_node_shape(graph):
        if other == shape:
            continue
        if any(o == shape for s, p, o in graph.cbd(other) if p == SH.node):
            users.append(str(other))
    return users


def target_short(package, shape, declared=None, users=None):
    declared = targets(package, shape) if declared is None else declared
    if declared:
        return ' · '.join(t['short'] for t in declared)
    users = used_by(package, shape) if users is None else users
    if users:
        return 'no target · used by ' + ', '.join(_name(package, u) for u in users)
    return 'no target · never used'


def is_rule_only(node):
    """A shape that is only a query or a rule: no attribute rows."""
    return bool(node and node.children) and \
        all(child.kind == 'raw' for child in node.children)


# --- a new shape --------------------------------------------------------------------

TARGET_PREDICATES = {'class': SH.targetClass, 'node': SH.targetNode,
                     'subjectsOf': SH.targetSubjectsOf,
                     'objectsOf': SH.targetObjectsOf}
NAME = r'^[A-Za-z_][A-Za-z0-9_.-]*$'


def _shapes_namespace(package):
    """Where this package keeps its shapes: the namespace most of them use."""
    from ..validate.shapes import every_node_shape

    spaces = []
    for shape in every_node_shape(package.shapes):
        text = str(shape)
        cut = max(text.rfind('#'), text.rfind('/'))
        spaces.append(text[:cut + 1])
    if not spaces:
        return None
    return max(set(spaces), key=spaces.count)


def _target_iri(package, kind, target):
    """The target as an IRI: an entity type or an attribute by term, IRI or
    local name; a node as written."""
    from .choices import attribute_terms, entity_types

    text = str(target or '').strip().strip('<>')
    if not text:
        raise PackageError('a shape needs a target')
    if kind == 'class':
        entry = next((e for e in entity_types(package)[0]
                      if text in (e.iri, e.term, e.label)), None)
        if entry is None:
            raise PackageError(f'{text} is not an entity type this package declares; '
                               f'declare it in the knowledge first')
        return URIRef(entry.iri)
    if kind in ('subjectsOf', 'objectsOf'):
        if text in ('ngsild:hasObject', 'https://uri.etsi.org/ngsi-ld/hasObject'):
            return URIRef('https://uri.etsi.org/ngsi-ld/hasObject')
        entry = next((e for e in attribute_terms(package)
                      if text in (e.iri, e.term, e.label)), None)
        if entry is None:
            raise PackageError(f'{text} is not an attribute this package declares')
        return URIRef(entry.iri)
    if kind == 'node':
        if not re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:\S+$', text):
            raise PackageError(f'"{text}" is not an IRI (e.g. urn:my-model:machine:1)')
        return URIRef(text)
    raise PackageError(f'{kind} is not a target the editor writes')


def add_shape(package, name, kind, target, namespace=None):
    """Write a new node shape: `ns:Name a sh:NodeShape ; sh:target… X .`

    Appended to the shapes file that holds the package's other shapes, in
    their namespace (or the one named), written with the file's own
    prefixes and verified to parse before it is kept. Constraints are then
    added from its page. Returns {'iri', 'name', 'file', 'line'}.
    """
    from rdflib import Graph

    from .knowledge import _resolve_namespace, _turtle_name

    name = str(name or '').strip()
    if not re.match(NAME, name):
        raise PackageError(f'"{name}" is not a usable name: letters, digits, "_", '
                           f'"-" and ".", starting with a letter')
    if kind not in TARGET_PREDICATES:
        raise PackageError(f'{kind} is not a target the editor writes')
    space = _resolve_namespace(package, namespace) if namespace \
        else _shapes_namespace(package)
    if not space:
        raise PackageError('this package has no shape yet to take a namespace from; '
                           'name one (a prefix from semforge.yaml)')
    iri = URIRef(space + name)
    if (iri, None, None) in package.shapes:
        raise PackageError(f'{curie(package.shapes, iri)} already exists')
    target_iri = _target_iri(package, kind, target)

    index = package.index('shapes')
    from ..validate.shapes import every_node_shape

    neighbour = next((s for s in every_node_shape(package.shapes)
                      if str(s).startswith(space)), None)
    path = (index.file_for(neighbour) if neighbour is not None else None) or \
        package.sources['shapes']
    with open(path, encoding='utf-8') as handle:
        text = handle.read()
    statement = (f'{_turtle_name(text, iri)} a {_turtle_name(text, SH.NodeShape)} ;\n'
                 f'    {_turtle_name(text, TARGET_PREDICATES[kind])} '
                 f'{_turtle_name(text, target_iri)} .\n')
    updated = text + ('' if text.endswith('\n') else '\n') + '\n' + statement
    graph = Graph().parse(data=updated, format='turtle')
    if (iri, TARGET_PREDICATES[kind], target_iri) not in graph:
        raise PackageError(f'{name} did not come out as written; nothing changed')
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(updated)
    return {'iri': str(iri), 'name': curie(graph, iri), 'file': path,
            'line': len(updated.splitlines()) - 1}


def build_shapes(package, report=None):
    """One row per named shape, for the Shapes view."""
    from ..validate import validate_package
    from .tree import shape_node

    if report is None:
        report = validate_package(package, strict=False)
    violations = {}
    for violation in report.violations:
        violations[str(violation.shape)] = violations.get(str(violation.shape), 0) + 1

    rows = []
    for shape in every_node_shape(package.shapes):
        node = shape_node(package, shape)
        attributes = sum(1 for c in (node.children if node else [])
                         if c.kind == 'attribute')
        rule = is_rule_only(node)
        parts = [target_short(package, shape)]
        if attributes:
            parts.append(f'{attributes} attribute(s)')
        if rule:
            parts.append('rule' if (shape, SH.rule, None) in package.shapes
                         else 'SPARQL constraint')
        failing = violations.get(str(shape), 0)
        if failing:
            parts.append(f'{failing} violation(s)')
        rows.append({
            'kind': 'shape', 'label': curie(package.shapes, shape),
            'shape': str(shape), 'iri': str(shape),
            'detail': ' · '.join(parts), 'rule': rule,
            'severity': 'violation' if failing else '',
            'definedAt': node.defined_at if node else '',
            'children': []})
    rows.sort(key=lambda row: row['label'].split(':')[-1].lower())
    return rows
