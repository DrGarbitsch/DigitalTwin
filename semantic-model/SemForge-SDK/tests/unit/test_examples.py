"""The example instances as a tree, and editing them."""

import json
import shutil

import pytest

from semforge.cooked.examples import build_examples, flatten, set_value
from semforge.errors import PackageError
from semforge.package import load
from semforge.validate import validate_package


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


def _find(nodes, label, kind=None):
    return next(n for _, n in flatten(nodes)
                if n.label == label and (kind is None or n.kind == kind))


# --- the tree ----------------------------------------------------------------

def test_every_entity_appears(corpus):
    tree = build_examples(corpus)
    entities = {n.label for _, n in flatten(tree) if n.kind == 'entity'}
    assert {'urn:filter:1', 'urn:plasmacutter:1', 'urn:cartridge:1'} <= entities


def test_an_entity_shows_its_type(corpus):
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    assert 'Filter' in node.detail


def test_attributes_hang_under_their_entity(corpus):
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    assert {c.label for c in node.children} >= {'hasStrength', 'hasCartridge'}


def test_a_single_instance_is_folded_into_its_attribute(corpus):
    """Showing one instance as a child of itself doubles the depth for nothing."""
    node = _find(build_examples(corpus), 'urn:filter:2', 'entity')
    state = next(c for c in node.children if c.label == 'hasState')
    assert state.children == []
    assert state.editable and state.value


def test_an_instance_with_sub_attributes_is_not_folded(corpus):
    """plasmacutter:1's hasState carries hasXXXWorkpiece, which must stay reachable."""
    node = _find(build_examples(corpus), 'urn:plasmacutter:1', 'entity')
    state = next(c for c in node.children if c.label == 'hasState')
    assert state.children
    nested = [c for c in state.children[0].children if c.kind == 'attribute']
    assert any(c.label == 'hasXXXWorkpiece' for c in nested)


def test_a_repeated_attribute_keeps_its_instances(corpus):
    """urn:filter:1 carries four hasStrength observations."""
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert len(strength.children) == 4
    assert '4 instances' in strength.detail


def test_observed_at_is_shown_as_metadata(corpus):
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    meta = [m for instance in strength.children for m in instance.children
            if m.kind == 'meta']
    assert any(m.label == 'observedAt' for m in meta)


def test_a_violating_entity_is_marked_and_carries_the_message(corpus):
    """A minCount violation is about an attribute that is NOT there, so there
    is no attribute node to hang it on -- the entity carries it or it is lost."""
    tree = build_examples(corpus, validate_package(corpus))
    node = _find(tree, 'urn:cutter:1', 'entity')
    assert node.severity == 'violation'
    assert 'violation(s)' in node.detail
    assert node.messages and any('Count' in m for m in node.messages)


def test_a_clean_entity_is_not_marked(corpus):
    tree = build_examples(corpus, validate_package(corpus))
    node = _find(tree, 'urn:plasmacutter:1', 'entity')
    assert node.severity == ''


def test_without_a_report_nothing_is_marked(corpus):
    assert all(n.severity == '' for _, n in flatten(build_examples(corpus)))


def test_a_relationship_target_is_readable(corpus):
    node = _find(build_examples(corpus), 'urn:filter:2', 'entity')
    rel = next(c for c in node.children if c.label == 'hasCartridge')
    assert 'urn:cartridge:2' in rel.value


def test_an_iri_value_is_shown_as_the_iri_not_the_wrapper(corpus):
    """`{"@id": "base:state_ON"}` reads as base:state_ON."""
    node = _find(build_examples(corpus), 'urn:filter:2', 'entity')
    state = next(c for c in node.children if c.label == 'hasState')
    assert state.value == 'base:state_ON'


def test_the_instance_validation_reads_is_marked(corpus):
    """Attributes resolve to the latest observedAt before validation.

    Editing a superseded observation changes the file and nothing else, which
    without a marker reads as the editor being broken.
    """
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    marks = [c.detail.split(' · ')[-1] for c in strength.children]
    assert marks.count('current') == 1
    assert marks.count('superseded') == 3
    assert marks[-1] == 'current', 'the latest observedAt is the current one'


# --- editing -----------------------------------------------------------------

def test_editing_a_value_produces_a_minimal_diff(package):
    with open(package.sources['model']) as handle:
        before = handle.read()

    path, old, new = set_value(
        package, 'urn:filter:1',
        ['iffBaseEntities:hasStrength', 0, 'value'], '0.95')

    with open(path) as handle:
        after = handle.read()
    assert (old, new) == ('0.9', '0.95')

    changed = [line for line in after.splitlines()
               if line not in before.splitlines()]
    assert len(changed) == 1, f'expected one changed line, got {changed}'


def test_a_value_is_parsed_as_json_when_it_can_be(package):
    """Typing 42 should give a number, not the string "42".

    A Property whose value arrives as a string where a number was meant is the
    difference between a range constraint passing and failing.
    """
    set_value(package, 'urn:filter:1',
              ['iffBaseEntities:hasStrength', 0, 'value'], '42')
    with open(package.sources['model']) as handle:
        document = json.load(handle)
    entity = next(e for e in document if e['id'] == 'urn:filter:1')
    assert entity['iffBaseEntities:hasStrength'][0]['value'] == 42


def test_an_iri_value_can_be_written_as_a_node_reference(package):
    set_value(package, 'urn:filter:1',
              ['iffBaseEntities:hasState', 0, 'value'],
              '{"@id": "base:state_OFF"}')
    with open(package.sources['model']) as handle:
        document = json.load(handle)
    entity = next(e for e in document if e['id'] == 'urn:filter:1')
    assert entity['iffBaseEntities:hasState'][0]['value'] == \
        {'@id': 'base:state_OFF'}


def test_a_plain_string_stays_a_string(package):
    set_value(package, 'urn:cartridge:1',
              ['iffBaseEntities:isUsedFrom', 0, 'value'], 'not-json')
    with open(package.sources['model']) as handle:
        document = json.load(handle)
    entity = next(e for e in document if e['id'] == 'urn:cartridge:1')
    assert entity['iffBaseEntities:isUsedFrom'][0]['value'] == 'not-json'


def test_the_edit_moves_the_verdict(package):
    """The reason to edit data here rather than in the JSON."""
    before = validate_package(load(package.path))
    assert not [r for r in before.violations if r.attribute == 'hasStrength']

    # Index 3 is the CURRENT observation; editing an older one would change
    # the file and leave the verdict alone, which is the point of the marker.
    set_value(package, 'urn:filter:1',
              ['iffBaseEntities:hasStrength', 3, 'value'], '999')

    after = validate_package(load(package.path))
    fired = [r for r in after.violations if r.attribute == 'hasStrength']
    assert fired, 'a strength above the maximum should now violate'


def test_editing_a_superseded_observation_leaves_the_verdict_alone(package):
    """Not a bug: the current view resolves to the latest observedAt."""
    set_value(package, 'urn:filter:1',
              ['iffBaseEntities:hasStrength', 0, 'value'], '999')
    after = validate_package(load(package.path))
    assert not [r for r in after.violations if r.attribute == 'hasStrength']


def test_an_unknown_entity_is_named_in_the_error(package):
    with pytest.raises(PackageError) as exc:
        set_value(package, 'urn:nope:1', ['x', 0, 'value'], '1')
    assert 'urn:nope:1' in str(exc.value)


def test_an_unknown_path_is_refused(package):
    with pytest.raises((PackageError, KeyError, IndexError)):
        set_value(package, 'urn:filter:1',
                  ['iffBaseEntities:nothingHere', 0, 'value'], '1')


def test_the_file_still_parses_after_an_edit(package):
    set_value(package, 'urn:filter:1',
              ['iffBaseEntities:hasStrength', 0, 'value'], '0.5')
    with open(package.sources['model']) as handle:
        json.load(handle)
    assert load(package.path).model
