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


def test_a_repeated_attribute_keeps_its_observations(corpus):
    """urn:filter:1 carries four hasStrength observations."""
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert len(strength.children) == 4
    assert '4 observations' in strength.detail


def test_the_timestamp_is_on_the_row_not_a_child(corpus):
    """Inside a series the observedAt IS the row's identity.

    Repeating it as a child is one more level to expand for something already
    on the line.
    """
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert all('2024-02-28T13:52' in c.detail for c in strength.children)
    assert not [m for c in strength.children for m in c.children
                if m.kind == 'meta' and m.label == 'observedAt']


def test_metadata_outside_a_series_is_still_a_child(corpus):
    """A lone instance's observedAt has no row of its own to sit on."""
    node = _find(build_examples(corpus), 'urn:cartridge:1', 'entity')
    used = next(c for c in node.children if c.label == 'isUsedFrom')
    assert used.value


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


# --- per datasetId -----------------------------------------------------------

def test_one_dataset_shows_the_series_under_the_attribute(corpus):
    """No dataset row when there is only one: it would be depth for nothing."""
    node = _find(build_examples(corpus), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert strength.dataset_id == '@none'
    assert strength.observations == 4 and strength.is_series
    assert all(c.kind == 'instance' for c in strength.children)
    assert strength.value == '0.6', 'the row shows what validation reads'


def test_several_datasets_get_a_row_each(package):
    """Different datasetIds are different attributes sharing a name.

    The dedup resolves within a datasetId and never across, so listing them
    flat would conflate two things that behave differently.
    """
    from semforge.cooked.examples import add_observation

    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    'urn:sensor:B', '1.0', '2024-02-28T14:00:00.000Z')
    add_observation(load(package.path), 'urn:filter:1',
                    ['iffBaseEntities:hasStrength'], 'urn:sensor:B', '1.5',
                    '2024-02-28T14:01:00.000Z')

    node = _find(build_examples(load(package.path)), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert '2 datasets' in strength.detail
    datasets = {c.dataset_id: c for c in strength.children}
    assert set(datasets) == {'@none', 'urn:sensor:B'}
    assert datasets['@none'].value == '0.6'
    assert datasets['urn:sensor:B'].value == '1.5'
    assert datasets['urn:sensor:B'].observations == 2


def test_each_dataset_resolves_its_own_current(package):
    """The latest observedAt WITHIN a datasetId, not across all of them."""
    from semforge.cooked.examples import add_observation

    # Newer than everything in @none, but a different dataset.
    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    'urn:sensor:B', '1.0', '2025-01-01T00:00:00.000Z')

    node = _find(build_examples(load(package.path)), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    datasets = {c.dataset_id: c for c in strength.children}
    assert datasets['@none'].value == '0.6', \
        'a newer observation in another dataset must not supersede this one'


def test_the_current_index_addresses_the_whole_attribute(package):
    """It is an edit path into the JSON array, not a position within a group.

    The two coincide only when there is a single datasetId, which is what made
    the first version crash on the second dataset.
    """
    from semforge.cooked.examples import add_observation

    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    'urn:sensor:B', '1.0', '2024-02-28T14:00:00.000Z')
    node = _find(build_examples(load(package.path)), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    sensor = next(c for c in strength.children
                  if c.dataset_id == 'urn:sensor:B')
    assert sensor.path[-2] == 4, 'index 4 is where it sits in the array'


# --- adding observations -----------------------------------------------------

def test_an_observation_joins_its_own_series(package):
    from semforge.cooked.examples import add_observation

    _, count = add_observation(
        package, 'urn:filter:1', ['iffBaseEntities:hasStrength'], '@none',
        '0.55', '2024-02-28T13:52:36.000Z')
    assert count == 5

    node = _find(build_examples(load(package.path)), 'urn:filter:1', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert strength.value == '0.55', 'the newest observation becomes current'


def test_a_new_dataset_id_starts_its_own_series(package):
    from semforge.cooked.examples import add_observation

    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    'urn:sensor:B', '1.0', '2024-02-28T14:00:00.000Z')
    with open(package.sources['model']) as handle:
        document = json.load(handle)
    entity = next(e for e in document if e['id'] == 'urn:filter:1')
    added = entity['iffBaseEntities:hasStrength'][-1]
    assert added['datasetId'] == 'urn:sensor:B'
    assert added['value'] == 1.0


def test_the_default_dataset_is_not_written_out(package):
    """`@none` IS the default instance; writing it would be a different thing."""
    from semforge.cooked.examples import add_observation

    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    '@none', '0.55', '2024-02-28T13:52:36.000Z')
    with open(package.sources['model']) as handle:
        document = json.load(handle)
    entity = next(e for e in document if e['id'] == 'urn:filter:1')
    assert 'datasetId' not in entity['iffBaseEntities:hasStrength'][-1]


def test_the_type_is_carried_over(package):
    """A Property whose new instance is a Relationship is a different attribute."""
    from semforge.cooked.examples import add_observation

    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    '@none', '0.55', '2024-02-28T13:52:36.000Z')
    with open(package.sources['model']) as handle:
        document = json.load(handle)
    entity = next(e for e in document if e['id'] == 'urn:filter:1')
    assert entity['iffBaseEntities:hasStrength'][-1]['type'] == 'Property'


def test_adding_to_a_single_valued_attribute_makes_it_a_series(package):
    from semforge.cooked.examples import add_observation

    _, count = add_observation(
        package, 'urn:filter:2', ['iffBaseEntities:hasStrength'], '@none',
        '0.7', '2024-03-01T00:00:00.000Z')
    assert count == 2
    node = _find(build_examples(load(package.path)), 'urn:filter:2', 'entity')
    strength = next(c for c in node.children if c.label == 'hasStrength')
    assert strength.is_series and strength.value == '0.7'


def test_adding_to_an_unknown_attribute_is_refused(package):
    from semforge.cooked.examples import add_observation

    with pytest.raises(PackageError) as exc:
        add_observation(package, 'urn:filter:1', ['iffBaseEntities:nope'],
                        '@none', '1', None)
    assert 'nope' in str(exc.value)


def test_a_new_observation_can_move_the_verdict(package):
    from semforge.cooked.examples import add_observation

    add_observation(package, 'urn:filter:1', ['iffBaseEntities:hasStrength'],
                    '@none', '999', '2030-01-01T00:00:00.000Z')
    after = validate_package(load(package.path))
    assert [r for r in after.violations if r.attribute == 'hasStrength']
