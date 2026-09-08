"""One name per namespace, across every artifact."""

import shutil

import pytest
from click.testing import CliRunner
from rdflib import Graph
from rdflib.compare import isomorphic

from semforge.cli import cli
from semforge.package import load
from semforge.package.prefixes import (align, canonical_map, check,
                                       context_prefixes, file_prefixes,
                                       names_by_namespace)

BASE = 'https://industryfusion.github.io/contexts/example/v0/'


@pytest.fixture
def package(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], target / name)
    for extra in ('context.jsonld', 'semforge.yaml'):
        shutil.copy(f'{corpus.path}/{extra}', target / extra)
    return load(str(target))


def test_the_context_is_read_as_the_source_of_truth(corpus):
    """context.jsonld declares terms with "@prefix": true."""
    found = context_prefixes(corpus.path)
    assert found['iffBaseEntities'] == BASE + 'base_entities/'
    assert found['material'].endswith('/material/')


def test_the_package_declaration_overrides_the_context(corpus):
    """The context calls base_knowledge `base`; this package says otherwise.

    shacl.ttl says iffBaseKnowledge at the Turtle level AND inside every SPARQL
    body, which declares its own prefixes and is a separate scope. Adopting the
    context's name would align the header and leave the queries saying
    something else.
    """
    assert context_prefixes(corpus.path)['base'] == BASE + 'base_knowledge/'
    assert names_by_namespace(corpus.path)[BASE + 'base_knowledge/'] == \
        'iffBaseKnowledge'


def test_the_corpus_is_aligned(corpus):
    assert check(corpus) == []


def test_no_ambiguous_or_generated_prefix_survives(corpus):
    """The hazard this removes: one prefix, two meanings.

    ':' denoted base_shacl in shacl.ttl and base_entities in knowledge.ttl, and
    'default1:' denoted filter_shacl and base_knowledge. A term copied between
    the files changed meaning silently.
    """
    seen = {}
    for role in ('shapes', 'knowledge'):
        for name, namespace in file_prefixes(corpus.sources[role])[0].items():
            assert name, 'the empty prefix is ambiguous across files'
            assert not name.startswith('default'), \
                f'{name} is an rdfpipe-generated name, not an agreed one'
            seen.setdefault(name, set()).add(namespace)
    assert all(len(namespaces) == 1 for namespaces in seen.values())


def test_every_namespace_has_exactly_one_name(corpus):
    by_name = {}
    for role in ('shapes', 'knowledge'):
        for name, namespace in file_prefixes(corpus.sources[role])[0].items():
            by_name.setdefault(namespace, set()).add(name)
    for namespace, names in by_name.items():
        assert len(names) == 1, f'{namespace} is called {names}'


# --- the alignment itself ----------------------------------------------------

def test_alignment_never_changes_the_graph(package):
    """A rename is a spelling change. If the graph moves, something is wrong."""
    before = Graph()
    before.parse(package.sources['shapes'], format='turtle')

    align(package)

    after = Graph()
    after.parse(package.sources['shapes'], format='turtle')
    assert isomorphic(before, after)


def test_alignment_is_idempotent(package):
    align(package)
    assert align(load(package.path), dry_run=True) == {}


def test_alignment_leaves_sparql_bodies_alone(package):
    """A SPARQL body declares its own prefixes and is a separate scope.

    Rewriting into one would break queries that are currently correct.
    """
    with open(package.sources['shapes']) as handle:
        before = handle.read()
    bodies_before = before.count('PREFIX iffBaseKnowledge:')
    assert bodies_before > 0

    align(package)
    with open(package.sources['shapes']) as handle:
        after = handle.read()
    assert after.count('PREFIX iffBaseKnowledge:') == bodies_before


def test_alignment_reports_a_namespace_nobody_named(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('model',
                                                        'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], target / name)
    shutil.copy(f'{corpus.path}/context.jsonld', target / 'context.jsonld')
    (target / 'shacl.ttl').write_text(
        '@prefix odd: <https://nobody.example/named/> .\n'
        '@prefix sh: <http://www.w3.org/ns/shacl#> .\n')

    findings = check(load(str(target)))
    unnamed = [f for f in findings if f.code == 'SF-PFX-003']
    assert any('nobody.example' in f.namespace for f in unnamed)
    assert 'context.jsonld or semforge.yaml' in unnamed[0].message


def test_an_ambiguous_prefix_is_an_error_not_a_warning(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    shutil.copy(corpus.sources['model'], target / 'model-instance.jsonld')
    shutil.copy(f'{corpus.path}/context.jsonld', target / 'context.jsonld')
    (target / 'knowledge.ttl').write_text(
        '@prefix p: <https://example.org/one/> .\n')
    (target / 'shacl.ttl').write_text(
        '@prefix p: <https://example.org/two/> .\n')

    findings = check(load(str(target)))
    ambiguous = [f for f in findings if f.code == 'SF-PFX-001']
    assert ambiguous and ambiguous[0].severity == 'error'
    assert 'changes meaning' in ambiguous[0].message


def test_canonical_map_merges_both_sources(corpus):
    found = canonical_map(corpus.path)
    assert 'iffBaseShacl' in found          # only in semforge.yaml
    assert 'iffBaseEntities' in found       # only in the context


# --- CLI ---------------------------------------------------------------------

def test_prefixes_command_reports_alignment(corpus_path):
    result = CliRunner().invoke(cli, ['prefixes', corpus_path])
    assert result.exit_code == 0
    assert 'one agreed name' in result.output


def test_prefixes_command_fails_on_an_ambiguous_prefix(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    shutil.copy(corpus.sources['model'], target / 'model-instance.jsonld')
    (target / 'knowledge.ttl').write_text('@prefix p: <https://a/> .\n')
    (target / 'shacl.ttl').write_text('@prefix p: <https://b/> .\n')
    result = CliRunner().invoke(cli, ['prefixes', str(target)])
    assert result.exit_code == 1
    assert 'SF-PFX-001' in result.output


def test_prefixes_fix_rewrites_and_then_reports_clean(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], target / name)
    shutil.copy(f'{corpus.path}/context.jsonld', target / 'context.jsonld')

    source = (target / 'knowledge.ttl').read_text()
    (target / 'knowledge.ttl').write_text(
        source.replace('@prefix iffFilterKnowledge:', '@prefix default9:')
              .replace('iffFilterKnowledge:', 'default9:'))

    result = CliRunner().invoke(cli, ['prefixes', str(target), '--fix'])
    assert 'default9: -> iffFilterKnowledge:' in result.output
    assert result.exit_code == 0
