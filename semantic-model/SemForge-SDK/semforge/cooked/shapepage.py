"""The shape page: what one shape checks, and what it reaches.

The type page reads constraints by type ("what must a Filter carry"). A shape
is the other unit: what SHACL actually evaluates, and the only home a shape
has when it targets something other than one entity type -- a named node, the
subjects of a predicate, a SPARQL query -- or nothing, being reached through
sh:node. Built from the same rows the type page uses, so an attribute reads
the same on both.
"""

import os

from rdflib import URIRef
from rdflib.namespace import RDF, SH

from ..errors import PackageError
from ..validate.normalise import curie
from .shapes import is_rule_only, target_short, targets, used_by
from .typepage import (_attribute_rows, _cases, _coverage, _examples_root,
                       _rules, _short)

# The nodes a page lists by name; past this it says how many more.
LISTED = 50


def _resolve(package, shape):
    from ..validate.shapes import every_node_shape

    wanted = str(shape or '').strip('<>')
    for candidate in every_node_shape(package.shapes):
        if wanted in (str(candidate), curie(package.shapes, candidate)) or \
                wanted == str(candidate).rsplit('/', 1)[-1]:
            return candidate
    raise PackageError(f'{shape} is not a shape in this package')


def _reach(package, shape, graph):
    """The focus nodes this shape selects in one data graph. A shape with no
    target of its own reaches whatever the shapes using it at the top level
    reach."""
    from ..validate.applicable import focus_nodes

    nodes = set(focus_nodes(shape, package.shapes, graph, package.knowledge))
    if not targets(package, shape):
        for user in used_by(package, shape):
            if (URIRef(user), SH.node, shape) in package.shapes:
                nodes |= set(focus_nodes(URIRef(user), package.shapes, graph,
                                         package.knowledge))
    return {str(node) for node in nodes}


def _types_of(graph, nodes):
    return {str(o) for node in nodes for o in graph.objects(URIRef(node), RDF.type)}


def build_shape_page(package, shape):
    """The payload the shape page renders. Reads only."""
    from ..expect.runner import run_tests
    from ..sanity import known_constraints
    from ..validate import validate_package
    from .choices import attribute_terms, entity_types
    from .tree import shape_node

    shape = _resolve(package, shape)
    name = curie(package.shapes, shape)
    node = shape_node(package, shape)
    declared = targets(package, shape)
    users = used_by(package, shape)

    cases = _cases(package)
    coverage = _coverage(cases)
    kind_of = {a.iri: a.kind for a in attribute_terms(package) if a.kind}

    report = validate_package(package, strict=False)
    mine = [v for v in report.violations if str(v.shape) == str(shape)]
    violated = {}
    for violation in mine:
        violated.setdefault((name, violation.attribute or ''), []).append(
            str(violation.resource))

    attributes = []
    for child in (node.children if node else []):
        if child.kind == 'attribute':
            attributes += _attribute_rows(package, child, kind_of, 0, coverage,
                                          violated)
    rules = _rules(package, [node], coverage) if node else []

    # What it reaches: in the model, and in every case.
    reached = sorted(_reach(package, shape, package.model))
    known = {entry.iri: entry.label for entry in entity_types(package)[0]}
    types = _types_of(package.model, reached)
    outcomes = {o.example: o for o in run_tests(
        [(example, case_report) for example, _, case_report in cases],
        known_constraints(package))}
    exercised = []
    for example, graph, case_report in cases:
        nodes = _reach(package, shape, graph)
        if not nodes:
            continue
        types |= _types_of(graph, nodes)
        fired = sum(1 for v in case_report.violations if str(v.shape) == str(shape))
        outcome = outcomes.get(example.path)
        exercised.append({
            'case': example.path, 'description': example.description,
            'expect': example.expect, 'entities': sorted(nodes)[:LISTED],
            'fired': fired, 'passed': bool(outcome and outcome.passed),
            'file': os.path.join(_examples_root(package), example.path)})

    problems = {}
    for violation in mine:
        problems.setdefault(str(violation.resource), []).append(
            f'{violation.attribute or name} · '
            f'{str(violation.component).replace("ConstraintComponent", "")}')

    fired_anywhere = any(case['fired'] for case in exercised)
    return {
        'iri': str(shape), 'name': name, 'label': _short(name),
        'definedAt': node.defined_at if node else '',
        'targets': declared,
        'target': target_short(package, shape, declared, users),
        'usedBy': [{'iri': u, 'name': curie(package.shapes, URIRef(u))} for u in users],
        'rule': is_rule_only(node),
        'attributes': attributes, 'rules': rules,
        # Entity types are links to their pages; anything else is a name.
        'types': sorted(({'iri': t, 'label': known[t], 'page': True} if t in known
                         else {'iri': t, 'label': _short(t), 'page': False})
                        for t in types),
        'reach': {'model': len(reached),
                  'nodes': [{'id': n, 'violations': problems.get(n, [])}
                            for n in reached[:LISTED]],
                  'more': max(0, len(reached) - LISTED)},
        'exercisedBy': exercised,
        'summary': {
            'reached': len(reached), 'violations': len(mine),
            'cases': len(exercised),
            'casesFailing': sum(1 for e in exercised if not e['passed']),
            'neverFired': not fired_anywhere and bool(attributes or rules),
        },
    }
