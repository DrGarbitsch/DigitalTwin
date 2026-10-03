"""Shapes as SHACL writes them: each one with what it targets, in words.

A shape is not tied to an entity type. It selects focus nodes by class, by
named node, by the subjects or objects of a predicate, by a SPARQL query, or
implicitly when the shape is itself a class -- or it has no target and is
reached from another shape through sh:node. The Types view reads constraints
by type; this is the other half, every shape whatever it targets, so a shape
that belongs to no type still has somewhere to be found.
"""

from rdflib import URIRef
from rdflib.namespace import OWL, RDF, RDFS, SH

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
