"""Candidate values for a constraint parameter, and how entities are told apart."""

import pytest
from rdflib import Graph

from semforge.cooked.choices import (choices_for, classify_classes,
                                     declared_entity_root, entity_root,
                                     term_for)
from semforge.package import load

ENTITIES = 'https://industryfusion.github.io/contexts/example/v0/base_entities/'
STATE = ['iffBaseEntities:hasState', 'ngsild:hasValue']
FILTER_REL = ['iffBaseEntities:hasFilter', 'ngsild:hasObject']


# --- finding the entity hierarchy -------------------------------------------

def test_the_kms_already_has_an_entity_root(corpus):
    """base_entities:Entity exists; no change to the shipped model is needed."""
    assert str(entity_root(corpus)) == ENTITIES + 'Entity'


def test_every_entity_class_descends_from_it(corpus):
    entities, _, root = classify_classes(corpus)
    names = {str(c).rsplit('/', 1)[-1] for c in entities}
    assert names == {'Entity', 'Machine', 'Cutter', 'Filter', 'Consumable',
                     'Workpiece', 'FilterCartridge', 'Lasercutter',
                     'Plasmacutter'}
    assert str(root).endswith('Entity')


def test_vocabulary_classes_are_kept_out_of_the_entity_half(corpus):
    _, knowledge, _ = classify_classes(corpus)
    names = {str(c).rsplit('/', 1)[-1] for c in knowledge}
    assert {'MachineState', 'Wasteclass', 'Material', 'SeverityClass'} <= names
    assert 'Filter' not in names and 'Workpiece' not in names


def test_the_ngsild_encoding_is_not_offered_as_a_class(corpus):
    """Property and Relationship are the encoding, not domain vocabulary."""
    entities, knowledge, _ = classify_classes(corpus)
    everything = {str(c) for c in entities + knowledge}
    assert 'https://uri.etsi.org/ngsi-ld/Property' not in everything
    assert 'https://uri.etsi.org/ngsi-ld/Relationship' not in everything


def test_a_declared_root_wins_over_detection(tmp_path, corpus):
    import shutil

    package = tmp_path / 'pkg'
    package.mkdir()
    for role, name in (('knowledge', 'knowledge.ttl'), ('shapes', 'shacl.ttl'),
                       ('model', 'model-instance.jsonld')):
        shutil.copy(corpus.sources[role], package / name)
    (package / 'semforge.yaml').write_text(
        f'entityRoot: {ENTITIES}Machine\n')

    loaded = load(str(package))
    assert str(declared_entity_root(str(package))) == ENTITIES + 'Machine'
    assert str(entity_root(loaded)) == ENTITIES + 'Machine'
    entities, _, _ = classify_classes(loaded)
    names = {str(c).rsplit('/', 1)[-1] for c in entities}
    assert 'Workpiece' not in names        # not under Machine
    assert 'Cutter' in names


def test_no_root_means_no_suggestions_not_all_of_them(tmp_path, corpus):
    """"no suggestions" and "suggestions unavailable" are different situations."""
    import shutil

    package = tmp_path / 'pkg'
    package.mkdir()
    shutil.copy(corpus.sources['model'], package / 'model-instance.jsonld')
    (package / 'knowledge.ttl').write_text('@prefix ex: <https://example.org/> .\n')
    (package / 'shapes-empty.ttl').write_text('')
    (package / 'shacl.ttl').write_text(
        '@prefix sh: <http://www.w3.org/ns/shacl#> .\n')

    loaded = load(str(package))
    choices, note = choices_for(loaded, STATE, 'sh:class')
    assert choices == []
    assert 'entityRoot' in note


# --- which half is offered ---------------------------------------------------

def test_a_relationship_target_offers_entity_types(corpus):
    choices, _ = choices_for(corpus, FILTER_REL, 'sh:class')
    labels = {c['label'] for c in choices}
    assert 'Filter' in labels and 'Workpiece' in labels
    assert 'MachineState' not in labels


def test_a_property_value_offers_vocabulary_classes(corpus):
    """hasState -> hasValue -> sh:class MachineState is what the kms declares."""
    choices, _ = choices_for(corpus, STATE, 'sh:class')
    labels = {c['label'] for c in choices}
    assert 'MachineState' in labels and 'Wasteclass' in labels
    assert 'Filter' not in labels


def test_the_offered_term_is_spelled_for_the_shapes_file(corpus):
    """It is written into shacl.ttl, which binds different prefixes.

    knowledge.ttl calls that namespace `default1:`; shacl.ttl calls it
    `iffBaseKnowledge:`. Offering the knowledge file's spelling would write an
    undefined prefix into the shapes file and break it on the next parse.
    """
    choices, _ = choices_for(corpus, STATE, 'sh:class')
    values = {c['value'] for c in choices}
    assert 'base:MachineState' in values
    assert not any(v.startswith('default') for v in values)


def test_every_offered_term_parses_in_the_shapes_file(corpus):
    with open(corpus.sources['shapes']) as handle:
        source = handle.read()
    for chain in (STATE, FILTER_REL):
        for choice in choices_for(corpus, chain, 'sh:class')[0]:
            probe = f'{source}\n<urn:probe> <urn:p> {choice["value"]} .\n'
            Graph().parse(data=probe, format='turtle')


def test_an_unbound_namespace_falls_back_to_a_full_iri():
    graph = Graph()
    assert term_for(graph, 'https://unbound.example/Thing') == \
        '<https://unbound.example/Thing>'


# --- other parameters --------------------------------------------------------

def test_nodekind_offers_the_shacl_node_kinds(corpus):
    choices, _ = choices_for(corpus, STATE, 'sh:nodeKind')
    values = {c['value'] for c in choices}
    assert 'sh:IRI' in values and 'sh:BlankNode' in values and 'sh:Literal' in values


def test_datatype_offers_the_common_xsd_types(corpus):
    choices, _ = choices_for(corpus, STATE, 'sh:datatype')
    values = {c['value'] for c in choices}
    assert 'xsd:double' in values and 'xsd:string' in values


def test_a_numeric_bound_has_no_candidate_list(corpus):
    """A range is a number, not a choice; the picker should stay out of the way."""
    choices, note = choices_for(corpus, STATE, 'sh:maxInclusive')
    assert choices == [] and note == ''


@pytest.mark.parametrize('parameter', ['sh:minCount', 'sh:maxCount', 'sh:pattern'])
def test_free_value_parameters_offer_nothing(corpus, parameter):
    assert choices_for(corpus, STATE, parameter) == ([], '')
