"""The applicable-set enumerator (implementation-plan.md H1).

A SHACL engine reports violations and nothing else. Conformance is the ABSENCE
of a result -- which is exactly the silence invariant V1 forbids us to read as
success, because it is also what a constraint that never ran produces.

So the set of constraints that SHOULD have been evaluated is computed
independently of the validator, and the engine's results are subtracted from it:

    in the report            -> VIOLATED
    enumerated, not reported -> CONFORMANT
    shape with no target     -> NOT_APPLICABLE
    enumerated badly, or engine error -> NOT_EVALUATED

The enumerator is a second, partial implementation of SHACL targeting, and it
can drift from pyshacl's. That is caught rather than assumed: every reported
result must map onto an enumerated pair, and one that does not is an enumerator
bug reported as such. Drift in the other direction -- enumerating something
pyshacl does not check -- shows up as a constraint that is CONFORMANT on every
example forever, which is what the coverage report exists to surface.
"""

from rdflib import URIRef
from rdflib.namespace import RDF, RDFS, SH

from .normalise import local

NGSILD_VALUE_PATHS = {
    'https://uri.etsi.org/ngsi-ld/hasValue',
    'https://uri.etsi.org/ngsi-ld/hasObject',
    'https://uri.etsi.org/ngsi-ld/hasValueList',
    'https://uri.etsi.org/ngsi-ld/hasJSON',
}

# SHACL parameter -> the constraint component pyshacl names in its report.
# Only parameters that actually produce a result belong here: sh:path and
# sh:order describe a shape, they do not constrain anything.
PARAMETERS = {
    SH.minCount: 'MinCountConstraintComponent',
    SH.maxCount: 'MaxCountConstraintComponent',
    SH.datatype: 'DatatypeConstraintComponent',
    SH.nodeKind: 'NodeKindConstraintComponent',
    SH['class']: 'ClassConstraintComponent',
    SH.minInclusive: 'MinInclusiveConstraintComponent',
    SH.maxInclusive: 'MaxInclusiveConstraintComponent',
    SH.minExclusive: 'MinExclusiveConstraintComponent',
    SH.maxExclusive: 'MaxExclusiveConstraintComponent',
    SH.minLength: 'MinLengthConstraintComponent',
    SH.maxLength: 'MaxLengthConstraintComponent',
    SH.pattern: 'PatternConstraintComponent',
    SH.hasValue: 'HasValueConstraintComponent',
    SH['in']: 'InConstraintComponent',
    SH.node: 'NodeConstraintComponent',
    SH['or']: 'OrConstraintComponent',
    SH['and']: 'AndConstraintComponent',
    SH.xone: 'XoneConstraintComponent',
    SH['not']: 'NotConstraintComponent',
}


def subclasses_of(graph, cls):
    """cls and everything below it through rdfs:subClassOf*.

    sh:targetClass goes through the subclass closure -- that is SHACL, and it is
    why a Plasmacutter is a target of a shape written for Cutter.
    """
    found = {cls}
    pending = [cls]
    while pending:
        current = pending.pop()
        for sub in graph.subjects(RDFS.subClassOf, current):
            if sub not in found:
                found.add(sub)
                pending.append(sub)
    return found


def focus_nodes(shape, shapes_graph, data_graph, knowledge_graph=None):
    """Every node a shape targets, by any of SHACL's target mechanisms."""
    typing = data_graph
    closure = knowledge_graph if knowledge_graph is not None else shapes_graph

    nodes = set()
    for cls in shapes_graph.objects(shape, SH.targetClass):
        for member in subclasses_of(closure, cls):
            nodes.update(typing.subjects(RDF.type, member))
    for node in shapes_graph.objects(shape, SH.targetNode):
        nodes.add(node)
    for predicate in shapes_graph.objects(shape, SH.targetSubjectsOf):
        nodes.update(typing.subjects(predicate, None))
    for predicate in shapes_graph.objects(shape, SH.targetObjectsOf):
        nodes.update(typing.objects(None, predicate))
    # Implicit class target: a shape that is itself a class targets its instances.
    if (shape, RDF.type, RDFS.Class) in shapes_graph:
        nodes.update(typing.subjects(RDF.type, shape))
    return nodes


def _constraints_of(node, shapes_graph):
    """The constraint components a single shape node declares."""
    return sorted({name for parameter, name in PARAMETERS.items()
                   if (node, parameter, None) in shapes_graph})


def _walk(node, shapes_graph, attribute, seen):
    """(attribute, component) pairs under a shape node, recursively.

    `attribute` is the NGSI-LD attribute a constraint is attributed to. A nested
    shape on ngsild:hasValue constrains the value of the attribute above it, so
    it keeps that attribute's name -- matching how a result is named on the way
    back out (normalise.attribute_name).
    """
    if node in seen:
        return []
    seen.add(node)

    pairs = [(attribute, component) for component in _constraints_of(node, shapes_graph)]

    for child in shapes_graph.objects(node, SH.property):
        path = shapes_graph.value(child, SH.path)
        if isinstance(path, URIRef) and str(path) not in NGSILD_VALUE_PATHS:
            child_attribute = local(path)
        else:
            # A value path, or a path expression with no name of its own: the
            # constraint stays attributed to the attribute that carries it.
            child_attribute = attribute
        pairs.extend(_walk(child, shapes_graph, child_attribute, seen))
    return pairs


def constraints_of_shape(shape, shapes_graph):
    """Every (attribute, component) a node shape declares.

    SPARQL constraints and rules are node-level: they are attributed to the
    shape, not to an attribute, because their bodies may touch many.
    """
    pairs = _walk(shape, shapes_graph, '', set())
    if (shape, SH.sparql, None) in shapes_graph:
        pairs.append(('', 'SPARQLConstraintComponent'))
    return sorted(set(pairs))


def enumerate_pairs(shapes_graph, data_graph, knowledge_graph=None, shapes=None):
    """{(resource, attribute, component, shape)} that should be evaluated.

    Returns (pairs, inapplicable) where inapplicable holds the shapes whose
    target matched nothing -- reported NOT_APPLICABLE rather than omitted, so a
    shape that silently stopped matching anything is visible.
    """
    from .shapes import node_shapes

    pairs = set()
    inapplicable = []
    for shape in (shapes if shapes is not None else node_shapes(shapes_graph)):
        declared = constraints_of_shape(shape, shapes_graph)
        if not declared:
            continue
        targets = focus_nodes(shape, shapes_graph, data_graph, knowledge_graph)
        if not targets:
            inapplicable.append((str(shape), declared))
            continue
        for node in targets:
            for attribute, component in declared:
                pairs.add((str(node), attribute, component, str(shape)))
    return pairs, inapplicable
