"""One id, one entity -- and the three different ways a suite bends that."""

import json
import os
import shutil

import pytest

from semforge.expect.identity import duplicate_ids
from semforge.expect.store import Example, compose, load_expectations
from semforge.package import load
from semforge.validate.normalise import local


@pytest.fixture
def package(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], target / name)
    for extra in ('context.jsonld', 'semforge.yaml'):
        shutil.copy(f'{corpus.path}/{extra}', target / extra)
    (target / 'examples').mkdir()
    return target


def _write(path, entities):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(entities, handle, indent=2)


# Every entity in the suite carries the published context URL, which the loader
# swaps for the local file. Without it `id` and `type` are ordinary keys, the
# entity becomes a blank node and the case tests nothing -- which a fixture of
# mine did, silently, until this was measured.
PUBLISHED = ('https://industryfusion.github.io/contexts/staging/example/v0.2/'
             'context.jsonld')


def _entity(identifier, state='base:state_ON'):
    return {
        'id': identifier, 'type': 'iffBaseEntities:Filter',
        'iffBaseEntities:hasState': {
            'type': 'Property', 'value': {'@id': state},
            'observedAt': '2024-02-28T13:52:32.000Z'},
        '@context': PUBLISHED,
    }


def _expectations(path, text):
    with open(path / 'examples' / 'expectations.yaml', 'w',
              encoding='utf-8') as handle:
        handle.write(text)


# --- the corpus as shipped ----------------------------------------------------

def test_the_shipped_examples_reuse_ids_across_cases(corpus):
    """Which is legitimate -- and still worth saying, because the id has stopped
    identifying one entity."""
    found = duplicate_ids(corpus)
    assert {d.entity for d in found} == {'urn:filter:1', 'urn:workpiece:1',
                                         'urn:cartridge:1', 'urn:plasmacutter:1'}
    assert {d.kind for d in found} == {'across-files'}
    assert {d.severity for d in found} == {'warning'}


def test_a_reused_id_says_where_the_others_are(corpus):
    filters = next(d for d in duplicate_ids(corpus) if d.entity == 'urn:filter:1')
    files = [os.path.basename(path) for path, _ in filters.places]
    assert 'filter-on.jsonld' in files and 'filter-off.jsonld' in files
    assert 'model-instance.jsonld' in files
    for path, line in filters.places:
        text = open(path, encoding='utf-8').read().splitlines()
        # The line is the entity, so a diagnostic lands where it is defined.
        assert any('urn:filter:1' in text[number]
                   for number in range(line - 1, min(line + 2, len(text))))


# --- the same id twice in one file ---------------------------------------------

def test_the_same_id_twice_in_one_file_is_an_error(package):
    _write(package / 'examples' / 'twice.jsonld',
           [_entity('urn:filter:77'), _entity('urn:filter:77', 'base:state_OFF')])
    _expectations(package, 'examples:\n  - path: twice.jsonld\n    expect: valid\n')

    found = duplicate_ids(load(str(package)))
    mine = [d for d in found if d.entity == 'urn:filter:77']
    assert [d.severity for d in mine] == ['error']
    assert mine[0].kind == 'in-file'
    assert 'defined 2 times' in mine[0].message
    assert len(mine[0].places) == 2


# --- the same id inside one composed case --------------------------------------

def test_redefining_an_included_entity_merges_rather_than_overrides(package):
    """Measured, because the severity depends on it.

    `compose` parses the case and its includes into one graph, so two
    definitions of an id do not override -- the entity ends up with the
    attributes of both, and the case stops describing what it says.
    """
    _write(package / 'examples' / 'inc.jsonld', [_entity('urn:filter:78')])
    _write(package / 'examples' / 'case.jsonld',
           [_entity('urn:filter:78', 'base:state_OFF')])

    graph = compose(load(str(package)),
                    Example(path='case.jsonld', include=['inc.jsonld']))
    states = {local(value) for _, _, value in graph
              if 'state_' in str(value)}
    assert states == {'state_ON', 'state_OFF'}, \
        'if this ever overrides, in-case stops being an error'


def test_an_id_in_both_a_case_and_its_include_is_an_error(package):
    _write(package / 'examples' / 'inc.jsonld', [_entity('urn:filter:78')])
    _write(package / 'examples' / 'case.jsonld',
           [_entity('urn:filter:78', 'base:state_OFF')])
    _expectations(package, 'examples:\n  - path: case.jsonld\n'
                           '    include: [inc.jsonld]\n    expect: valid\n')

    mine = [d for d in duplicate_ids(load(str(package)))
            if d.entity == 'urn:filter:78']
    assert [d.kind for d in mine] == ['in-case']
    assert mine[0].severity == 'error'
    assert 'MERGE' in mine[0].message
    assert mine[0].case == 'case.jsonld'


def test_a_merged_id_is_not_also_reported_as_reused(package):
    """One finding per problem: the merge is the problem, not the reuse."""
    _write(package / 'examples' / 'inc.jsonld', [_entity('urn:filter:78')])
    _write(package / 'examples' / 'case.jsonld',
           [_entity('urn:filter:78', 'base:state_OFF')])
    _expectations(package, 'examples:\n  - path: case.jsonld\n'
                           '    include: [inc.jsonld]\n    expect: valid\n')

    mine = [d for d in duplicate_ids(load(str(package)))
            if d.entity == 'urn:filter:78']
    assert len(mine) == 1


def test_alternative_subobjects_are_not_an_error(package):
    """Two variants of one entity, each included by a different case.

    This is how the kms writes "the filter, but off", so flagging it as an error
    would reject the design rather than a mistake.
    """
    _write(package / 'examples' / 'on.jsonld', [_entity('urn:filter:79')])
    _write(package / 'examples' / 'off.jsonld',
           [_entity('urn:filter:79', 'base:state_OFF')])
    _write(package / 'examples' / 'good.jsonld', [_entity('urn:cutter:79')])
    _write(package / 'examples' / 'bad.jsonld', [_entity('urn:cutter:80')])
    _expectations(package,
                  'examples:\n'
                  '  - path: good.jsonld\n    include: [on.jsonld]\n'
                  '    expect: valid\n'
                  '  - path: bad.jsonld\n    include: [off.jsonld]\n'
                  '    expect: valid\n')

    mine = [d for d in duplicate_ids(load(str(package)))
            if d.entity == 'urn:filter:79']
    assert [d.severity for d in mine] == ['warning']
    assert mine[0].kind == 'across-files'


def test_a_unique_id_is_not_reported(package):
    _write(package / 'examples' / 'only.jsonld', [_entity('urn:filter:81')])
    _expectations(package, 'examples:\n  - path: only.jsonld\n    expect: valid\n')
    assert [d for d in duplicate_ids(load(str(package)))
            if d.entity == 'urn:filter:81'] == []


def test_expectations_are_optional(package):
    """A package with no declared cases still gets the file-level check."""
    _write(package / 'examples' / 'twice.jsonld',
           [_entity('urn:filter:82'), _entity('urn:filter:82')])
    found = duplicate_ids(load(str(package)), load_expectations(str(package)))
    assert [d.kind for d in found if d.entity == 'urn:filter:82'] == ['in-file']


# --- an entity that will not expand at all -------------------------------------

def test_an_entity_without_a_context_is_an_error(package):
    """It passes validation by describing nothing.

    `id` and `type` are ordinary keys until a context maps them, so the entity
    becomes a blank node, no sh:targetClass matches, and the case reports ok.
    """
    from semforge.expect.identity import missing_context

    naked = _entity('urn:filter:90')
    del naked['@context']
    _write(package / 'examples' / 'naked.jsonld', [naked])
    _expectations(package, 'examples:\n  - path: naked.jsonld\n    expect: valid\n')

    found = missing_context(load(str(package)))
    assert [f.entity for f in found] == ['urn:filter:90']
    assert found[0].severity == 'error'
    assert 'validates nothing' in found[0].message


def test_the_contextless_entity_really_does_validate_nothing(package):
    """The measurement behind the severity."""
    naked = _entity('urn:filter:91')
    del naked['@context']
    _write(package / 'examples' / 'naked.jsonld', [naked])

    graph = compose(load(str(package)), Example(path='naked.jsonld'))
    assert not [s for s in graph.subjects() if str(s).startswith('urn:')], \
        'if this ever expands, no-context stops being an error'


def test_the_shipped_examples_all_have_a_context(corpus):
    from semforge.expect.identity import missing_context

    assert missing_context(corpus) == []


def test_a_shared_context_on_the_document_counts(package):
    """A single object with @context covers what is inside it."""
    from semforge.expect.identity import missing_context

    naked = _entity('urn:filter:92')
    del naked['@context']
    _write(package / 'examples' / 'wrapped.jsonld',
           {'@context': PUBLISHED, '@graph': [naked]})
    assert [f.entity for f in missing_context(load(str(package)))
            if f.entity.startswith('urn:filter:92')] == []


# --- where it is surfaced ------------------------------------------------------

def test_the_diagnostics_land_on_the_json_file_and_line(corpus_path):
    from semforge.editor.analysis import analyse

    findings, _ = analyse(corpus_path)
    identity = {path: [f for f in items if f.kind == 'identity']
                for path, items in findings.items()}
    identity = {path: items for path, items in identity.items() if items}
    assert identity, 'nothing was reported about entity identity'
    for path, items in identity.items():
        assert path.endswith('.jsonld'), 'reported against the wrong artifact'
        text = open(path, encoding='utf-8').read().splitlines()
        for finding in items:
            assert 1 <= finding.line <= len(text)
            assert finding.subject in '\n'.join(
                text[finding.line - 1:finding.line + 2])


def test_the_entity_rows_are_marked(corpus):
    from semforge.cooked.examples import build_suite, flatten

    rows = [n for _, n in flatten(build_suite(corpus)) if n.kind == 'entity']
    reused = [n for n in rows if n.label == 'urn:filter:1']
    assert reused and all('id reused' in n.detail for n in reused)
    assert all(any('no longer identifies one entity' in m for m in n.messages)
               for n in reused)
    # A violation outranks it: that says the entity is wrong, this says we
    # cannot be sure which entity it is.
    assert {n.severity for n in reused} <= {'violation', 'warning'}
    clean = [n for n in rows if n.label == 'urn:filter:8']
    assert clean and all('id reused' not in n.detail for n in clean)
