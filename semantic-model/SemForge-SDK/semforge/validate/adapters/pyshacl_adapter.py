"""The pyshacl adapter.

Two things here are not obvious and both were learned the expensive way in
shacl2flink/tests/pyshacl-compare/compare.py:

* The knowledge graph belongs in the DATA graph, not in ont_graph. Passed as
  ont_graph it is invisible to sh:class, so every sh:class over a value typed
  only by the knowledge -- `iff:state_OFF a iff:MachineState` -- reports a
  violation that is not one. The validator has to see the same world the
  constraints are written against.

* advanced=True. SHACL-AF is what sh:rule and sh:sparql need, and the kms
  shapes are mostly those.
"""

import pyshacl
from rdflib import Graph
from rdflib.namespace import SH

from .. import normalise
from ..results import Result, Status


def run(data_graph, shapes_graph, knowledge_graph=None, view='current'):
    """Validate and return normalised Results (violations only).

    A SHACL engine reports violations and nothing else, so every Result here is
    VIOLATED. Establishing which constraints were evaluated and CONFORMED is the
    applicable-set enumerator's job (H1, M2) -- deliberately not faked here,
    because a conformant status this function cannot justify would be exactly
    the silence invariant V1 forbids.
    """
    data = Graph()
    for triple in data_graph:
        data.add(triple)
    if knowledge_graph is not None:
        for triple in knowledge_graph:
            data.add(triple)

    _, report, _ = pyshacl.validate(
        data, shacl_graph=shapes_graph,
        advanced=True, inplace=False, do_owl_imports=False)

    results = []
    for node in report.objects(None, SH.result):
        focus = report.value(node, SH.focusNode)
        path = report.value(node, SH.resultPath)
        component = normalise.local(report.value(node, SH.sourceConstraintComponent))
        source = report.value(node, SH.sourceShape)
        shape = normalise.owning_shape(source, shapes_graph, report)
        curie = normalise.curie(shapes_graph, shape)
        severity = normalise.local(report.value(node, SH.resultSeverity) or SH.Violation)
        message = report.value(node, SH.resultMessage)

        resource, attribute = normalise.attribute_name(
            focus, path, data, shapes_graph, report)
        if resource is None:
            # Cannot be attributed to an entity. Never silently dropped: it is
            # reported as NOT_EVALUATED so it still appears in the report.
            results.append(Result(
                resource=str(focus), attribute='', component=component,
                shape=shape or '',

                severity=severity, status=Status.NOT_EVALUATED,
                message=str(message or ''), view=view, shape_curie=curie))
            continue

        results.append(Result(
            resource=resource, attribute=attribute or '',
            component=component,
            shape=shape or '',
            severity=severity, status=Status.VIOLATED,
            message=str(message or ''), view=view, shape_curie=curie))
    return results
