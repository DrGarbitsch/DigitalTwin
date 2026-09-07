"""Run each view's shapes against that view's data, then merge.

pyshacl evaluates ONE graph, so a shape that reads an attribute's history and a
shape that reads its current state cannot share a run. They are partitioned by
declared view and merged afterwards.
"""

from rdflib import Graph

from ..errors import DiagnosticSet
from ..ngsild import DataView, build_view
from . import shapes as shape_views
from .adapters import pyshacl_adapter
from .results import Report


def validate_graphs(data_graph, shapes_graph, knowledge_graph=None, strict=True):
    """Validate one already-loaded package. Returns a Report."""
    diagnostics = DiagnosticSet()
    for diagnostic in shape_views.check_declarations(shapes_graph):
        diagnostics.add(diagnostic)
    if strict:
        diagnostics.fail_loud(
            'ERROR: the following shapes declare a data view their body '
            'contradicts, and would be evaluated over the wrong instances:')

    report = Report(diagnostics=list(diagnostics))
    for view, view_shapes in sorted(shape_views.partition(shapes_graph).items(),
                                    key=lambda item: item[0].value):
        graph, stats = build_view(data_graph, view)
        report.view_stats.append(stats)
        subset = shape_views.subgraph_for(shapes_graph, view_shapes)
        report.results.extend(pyshacl_adapter.run(
            graph, subset, knowledge_graph, view=view.value))
    return report


def validate_package(package, strict=True):
    """Validate a loaded Package."""
    return validate_graphs(package.model, package.shapes, package.knowledge,
                           strict=strict)


def validate_raw(data_graph, shapes_graph, knowledge_graph=None,
                 view=DataView.CURRENT):
    """Validate every shape against one named view, ignoring declarations.

    Used by tests that need to show what a view does -- notably that the
    cardinality violation is real without the collapse and gone with it.
    """
    graph, stats = build_view(data_graph, view)
    report = Report()
    report.view_stats.append(stats)
    shapes = shapes_graph if isinstance(shapes_graph, Graph) else Graph().parse(shapes_graph)
    report.results.extend(pyshacl_adapter.run(
        graph, shapes, knowledge_graph, view=view.value))
    return report
