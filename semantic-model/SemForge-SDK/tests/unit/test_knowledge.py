"""The knowledge tree: the hierarchy, the vocabularies, and the joins."""

import os
import shutil

import pytest

from semforge.cooked.knowledge import build_knowledge, flatten
from semforge.package import load


@pytest.fixture(scope='module')
def tree(corpus):
    return build_knowledge(corpus)


def _find(tree, label, kind=None):
    return next(n for _, n in flatten(tree)
                if n.label == label and (kind is None or n.kind == kind))


def _all(tree, kind):
    return [n for _, n in flatten(tree) if n.kind == kind]


# --- the hierarchy ------------------------------------------------------------

def test_the_two_groups_are_the_hierarchy_and_the_vocabularies(tree):
    assert [n.label for n in tree] == ['Entity types', 'Vocabulary classes']


def test_entity_types_nest_by_subclass(tree):
    machine = _find(tree, 'iffBaseEntities:Machine', 'class')
    below = {n.label for n in machine.children if n.kind == 'class'}
    assert below == {'iffBaseEntities:Cutter', 'iffBaseEntities:Filter'}

    cutter = _find(tree, 'iffBaseEntities:Cutter', 'class')
    assert {n.label for n in cutter.children if n.kind == 'class'} == \
        {'iffBaseEntities:Lasercutter', 'iffBaseEntities:Plasmacutter'}


def test_a_vocabulary_class_lists_its_members(tree):
    states = _find(tree, 'base:MachineState', 'class')
    members = [n.label for n in states.children if n.kind == 'individual']
    assert 'state_ON' in members and 'state_OFF' in members
    assert '7 member(s)' in states.detail


def test_an_entity_type_is_not_listed_among_the_vocabularies(tree):
    vocabulary = tree[1]
    labels = {n.label for _, n in flatten(vocabulary.children)}
    assert 'iffBaseEntities:Filter' not in labels


# --- the join to the shapes ---------------------------------------------------

def test_a_class_carries_the_shape_that_judges_it(tree):
    node = _find(tree, 'iffBaseEntities:Filter', 'class')
    assert 'iffBaseShacl:FilterShape' in node.detail
    assert node.shape_at and os.path.basename(
        node.shape_at.rsplit(':', 1)[0]) == 'shacl.ttl'


def test_a_subclass_with_no_shape_of_its_own_is_not_called_unchecked(tree):
    """sh:targetClass traverses rdfs:subClassOf*.

    CutterShape judges a Plasmacutter, so flagging it as unchecked would be a
    false alarm -- and the least obvious rule in SHACL is exactly the one an
    author should not have to remember here.
    """
    node = _find(tree, 'iffBaseEntities:Plasmacutter', 'class')
    assert node.severity == ''
    assert 'inherited shape' in node.detail


def test_an_abstract_root_is_not_flagged(tree):
    """Entity and Consumable have subclasses and no instances: nothing is
    missing."""
    for label in ('iffBaseEntities:Entity', 'iffBaseEntities:Consumable'):
        assert _find(tree, label, 'class').severity == ''


def test_a_truly_unchecked_type_is_flagged(tmp_path, corpus):
    target = tmp_path / 'pkg'
    target.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], target / name)
    for extra in ('context.jsonld', 'semforge.yaml'):
        shutil.copy(f'{corpus.path}/{extra}', target / extra)
    with open(target / 'knowledge.ttl', 'a', encoding='utf-8') as handle:
        handle.write('\niffBaseEntities:Conveyor a owl:Class ;\n'
                     '    rdfs:subClassOf iffBaseEntities:Entity .\n')

    node = _find(build_knowledge(load(str(target))),
                 'iffBaseEntities:Conveyor', 'class')
    assert node.severity == 'warning'
    assert 'no shape' in node.detail


# --- the join to the examples -------------------------------------------------

def test_instances_are_counted_across_every_example_file(tree):
    """Counting only model-instance.jsonld would call types uninstantiated
    that the suites instantiate several times over."""
    node = _find(tree, 'iffBaseEntities:Filter', 'class')
    assert 'instance(s)' in node.detail
    instances = [n for n in node.children if n.kind == 'instance']
    assert len(instances) > 1
    assert all(n.defined_at for n in instances)
    assert {os.path.basename(n.file) for n in instances} != \
        {'model-instance.jsonld'}, 'the example suites were not read'


def test_a_term_an_example_uses_is_marked_used_and_says_where(tree):
    used = _find(tree, 'state_ON', 'individual')
    assert 'used in' in used.detail
    assert used.severity == ''
    assert [n.kind for n in used.children] == ['usage'] * len(used.children)
    assert any(n.entity.startswith('urn:') for n in used.children)


def test_a_term_used_only_by_a_bad_example_still_counts_as_used(tree):
    """state_OFF appears in a case under bad/, not in the shipped model.

    Calling it unused would send somebody deleting a term the suite depends on.
    """
    node = _find(tree, 'state_OFF', 'individual')
    assert 'used in' in node.detail and node.severity == ''


def test_an_unexercised_value_of_a_constrained_vocabulary_is_flagged(tree):
    node = _find(tree, 'state_CLEANING', 'individual')
    assert node.severity == 'warning'
    assert 'no case exercises it' in node.messages[0]


def test_terms_of_a_vocabulary_no_shape_draws_from_are_not_flagged(tree):
    """A Binding is not something an NGSI-LD example mentions.

    Flagging those would colour most of the tree and bury the real gap.
    """
    for label in ('carbon', 'heightBinding', '_map1'):
        node = _find(tree, label, 'individual')
        assert node.severity == '', f'{label} should not be flagged'


def test_an_entity_range_is_not_reported_as_having_no_members(tree):
    """sh:class on a relationship means the value is an ENTITY.

    Its instances live in the data, so "no individuals in knowledge.ttl" says
    nothing about whether the constraint can be satisfied.
    """
    for label in ('iffBaseEntities:FilterCartridge', 'iffBaseEntities:Workpiece'):
        node = _find(tree, label, 'class')
        assert 'no members' not in node.detail
        assert node.severity == ''


# --- the locations every row needs --------------------------------------------

def test_every_class_and_member_can_be_opened(tree, corpus):
    rows = _all(tree, 'class') + _all(tree, 'individual')
    # Every one of them, including the base:-prefixed vocabulary whose
    # statements the index used to discard as @base directives.
    assert [n.label for n in rows if not n.defined_at] == []
    for node in rows:
        if node.defined_at:
            path, line = node.defined_at.rsplit(':', 1)
            assert path == corpus.sources['knowledge']
            text = open(path, encoding='utf-8').read().splitlines()
            assert node.label.split(':')[-1] in text[int(line) - 1]
