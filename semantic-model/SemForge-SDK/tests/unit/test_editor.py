"""M6: the editor service.

Everything here runs without starting a server. That is the point of keeping
analysis.py protocol-free -- if these needed an LSP session, the editor layer
would have become the semantic engine.
"""

import json
import os

import pytest

from semforge.editor import analyse, definition_at, hover_at
from semforge.editor.analysis import package_root


@pytest.fixture(scope='module')
def analysis(request):
    root = os.path.join(os.path.dirname(__file__), '..', 'corpus', 'kms')
    findings, package = analyse(os.path.abspath(root))
    return list(findings.values())[0], package


def test_package_root_is_found_from_any_artifact(corpus_path):
    for name in ('shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld'):
        assert package_root(os.path.join(corpus_path, name)) == \
            os.path.abspath(corpus_path)


def test_package_root_is_none_outside_a_package(tmp_path):
    assert package_root(str(tmp_path)) is None


def test_findings_land_on_the_shapes_file(corpus_path):
    findings, _ = analyse(corpus_path)
    assert len(findings) == 1
    assert list(findings)[0].endswith('shacl.ttl')


def test_every_finding_has_a_real_line(analysis):
    items, _ = analysis
    assert items
    for finding in items:
        assert finding.line >= 1


def test_a_firing_constraint_is_reported_against_its_shape(analysis):
    items, _ = analysis
    fires = [f for f in items if f.kind == 'fires']
    assert fires
    assert 'MachineShape' in fires[0].subject
    assert 'hasXXXWorkpiece' in fires[0].message


def test_unexercised_constraints_are_aggregated_per_shape(analysis):
    """One finding per shape, not one per constraint.

    Per-constraint, a package with a single example puts a finding on nearly
    every line, and a warning nobody can read is a warning nobody acts on.
    """
    items, _ = analysis
    unexercised = [f for f in items if f.kind == 'unexercised']
    assert unexercised
    assert len(unexercised) == len({f.subject for f in unexercised})
    assert len(unexercised) < 15
    assert 'no example that makes them fire' in unexercised[0].message


def test_the_dead_shape_warning_reaches_the_editor(analysis):
    """The H6 signal, where an author will actually notice it."""
    items, _ = analysis
    message = ' '.join(f.message for f in items if f.kind == 'unexercised')
    assert 'looks exactly like one that is satisfied' in message


def test_a_view_declaration_error_is_an_editor_error(tmp_path, corpus):
    import shutil

    package = tmp_path / 'pkg'
    package.mkdir()
    shutil.copy(corpus.sources['knowledge'], package / 'knowledge.ttl')
    shutil.copy(corpus.sources['model'], package / 'model-instance.jsonld')
    (package / 'shacl.ttl').write_text('''
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix ex: <https://example.org/> .
ex:S a sh:NodeShape ; sh:targetClass ex:C ;
    sh:sparql [ a sh:SPARQLConstraints ; sh:select """
SELECT $this (COUNT(?v) AS ?n) WHERE { $this ex:a [ ex:v ?v ] } GROUP BY $this
""" ] .
''')
    findings, _ = analyse(str(package))
    items = list(findings.values())[0]
    views = [f for f in items if f.kind == 'view']
    assert views and views[0].severity == 'error'
    assert views[0].line == 4


def test_hover_describes_a_shape(analysis):
    _, package = analysis
    markdown = hover_at(package, 'CartridgeShape')
    assert 'imported-shacl' in markdown
    assert 'declared' in markdown


def test_hover_on_nothing_is_empty(analysis):
    _, package = analysis
    assert hover_at(package, '') == ''
    assert hover_at(package, 'NotAThing') == ''


def test_definition_crosses_from_shapes_to_the_ontology(analysis):
    """The navigation nothing else in the toolchain can do.

    shacl.ttl and knowledge.ttl are related only through the graph, so an
    editor cannot follow `sh:path iffBaseEntities:hasStrength` to the
    owl:ObjectProperty that declares it without the semantic model.
    """
    _, package = analysis
    found = definition_at(package, 'hasStrength')
    assert found is not None
    path, line = found
    assert path.endswith('knowledge.ttl') and line > 1


def test_definition_finds_a_shape_in_the_shapes_file(analysis):
    _, package = analysis
    path, line = definition_at(package, 'CartridgeShape')
    assert path.endswith('shacl.ttl') and line >= 1


def test_definition_of_nothing_is_none(analysis):
    _, package = analysis
    assert definition_at(package, 'NoSuchThing') is None
    assert definition_at(package, '') is None


# --- the protocol layer, exercised without a session -------------------------

def test_the_server_module_imports_and_maps_severities():
    from semforge.editor import server

    assert set(server.SEVERITY) == {'error', 'warning', 'information', 'hint'}
    assert server.server is not None


def test_word_extraction_at_a_cursor():
    from lsprotocol import types

    from semforge.editor.server import _word_at

    class Document:
        lines = ['    sh:path iffBaseEntities:hasStrength ;\n']

    assert _word_at(Document(), types.Position(0, 30)) == 'hasStrength'
    assert _word_at(Document(), types.Position(9, 0)) == ''


def test_uri_round_trip():
    from semforge.editor.server import _path_to_uri, _uri_to_path

    path = '/tmp/a package/shacl.ttl'
    assert _uri_to_path(_path_to_uri(path)) == path


def test_the_extension_manifest_is_valid_and_points_at_the_server():
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    manifest = os.path.join(here, 'SemForge-SDK', 'vscode', 'package.json') \
        if os.path.basename(here) != 'SemForge-SDK' \
        else os.path.join(here, 'vscode', 'package.json')
    with open(manifest) as handle:
        data = json.load(handle)
    assert data['main'] == './src/extension.js'
    assert 'vscode-languageclient' in data['dependencies']
    assert any('shacl.ttl' in event for event in data['activationEvents'])

    source = os.path.join(os.path.dirname(manifest), 'src', 'extension.js')
    with open(source) as handle:
        text = handle.read()
    assert 'semforge.editor.server' in text, \
        'the extension must launch the SDK server, not reimplement it'
