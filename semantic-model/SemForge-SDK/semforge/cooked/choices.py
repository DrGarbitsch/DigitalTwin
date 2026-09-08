"""Candidate values for a constraint parameter.

`sh:class` means something different either side of the NGSI-LD encoding, and
offering one list for both is what makes a picker useless:

    …/hasObject   a Relationship points at an ENTITY -- Filter, Workpiece
    …/hasValue    a Property with an IRI value points into the VOCABULARY --
                  MachineState, Wasteclass, Material

The shipped kms says exactly that: `hasFilter → hasObject → sh:class Filter`
against `hasState → hasValue → sh:class MachineState`. So the slot the
constraint sits in decides which half of the ontology is offered.

Telling the halves apart needs a root for the entity hierarchy. The kms already
has one -- `base_entities:Entity`, with Machine, Cutter, Filter, Consumable,
Workpiece and FilterCartridge all beneath it -- so this is read from the
ontology rather than guessed. Where a package has no such root it is DECLARED,
in semforge.yaml, and where it is neither present nor declared the choices are
reported as unavailable rather than filled with everything.
"""

import os

from rdflib import OWL, RDF, RDFS, URIRef

from ..validate.normalise import local

NGSILD = 'https://uri.etsi.org/ngsi-ld/'
VALUE_PATH = NGSILD + 'hasValue'
OBJECT_PATH = NGSILD + 'hasObject'

# Scaffolding, not domain vocabulary. Offering these as a value class would be
# offering the encoding itself.
EXCLUDED = {NGSILD + 'Property', NGSILD + 'Relationship',
            str(RDFS.Datatype), str(RDFS.Class), str(OWL.Class)}

NODE_KINDS = ['sh:IRI', 'sh:BlankNode', 'sh:Literal', 'sh:BlankNodeOrIRI',
              'sh:IRIOrLiteral', 'sh:BlankNodeOrLiteral']

COMMON_DATATYPES = ['xsd:string', 'xsd:integer', 'xsd:double', 'xsd:decimal',
                    'xsd:boolean', 'xsd:dateTime', 'xsd:date', 'xsd:anyURI']


def declared_entity_root(package_path):
    """`entityRoot:` from semforge.yaml, if the package declares one."""
    config = os.path.join(package_path, 'semforge.yaml')
    if not os.path.exists(config):
        return None
    from ruamel.yaml import YAML

    with open(config) as handle:
        data = YAML().load(handle) or {}
    root = data.get('entityRoot')
    return URIRef(root) if root else None


def entity_root(package):
    """The class every entity type descends from, or None.

    Declared wins. Otherwise it is derived as the common ancestor of the
    shapes' target classes -- which is a real signal rather than a guess: a
    shape's target IS an entity type, so whatever sits above all of them is the
    root of the entity hierarchy.
    """
    declared = declared_entity_root(package.path)
    if declared is not None:
        return declared

    from ..validate.shapes import node_shapes
    from rdflib.namespace import SH

    targets = {t for shape in node_shapes(package.shapes)
               for t in package.shapes.objects(shape, SH.targetClass)}
    if not targets:
        return None

    ancestors = None
    for target in targets:
        chain = _ancestors(package.knowledge, target)
        ancestors = chain if ancestors is None else (ancestors & chain)
    if not ancestors:
        return None
    # The most specific class that is still above every target.
    return max(ancestors, key=lambda c: len(_descendants(package.knowledge, c)))


def _ancestors(graph, cls):
    found = {cls}
    pending = [cls]
    while pending:
        current = pending.pop()
        for parent in graph.objects(current, RDFS.subClassOf):
            if parent not in found:
                found.add(parent)
                pending.append(parent)
    return found


def _descendants(graph, cls):
    found = {cls}
    pending = [cls]
    while pending:
        current = pending.pop()
        for child in graph.subjects(RDFS.subClassOf, current):
            if child not in found:
                found.add(child)
                pending.append(child)
    return found


def classify_classes(package):
    """(entity classes, knowledge classes, root). Both sorted by IRI."""
    declared = {c for c in package.knowledge.subjects(RDF.type, OWL.Class)
                if isinstance(c, URIRef) and str(c) not in EXCLUDED}
    # A class used only as a superclass may never be declared owl:Class.
    for subject, obj in package.knowledge.subject_objects(RDFS.subClassOf):
        for node in (subject, obj):
            if isinstance(node, URIRef) and str(node) not in EXCLUDED:
                declared.add(node)

    root = entity_root(package)
    if root is None:
        return [], sorted(declared, key=str), None

    entities = _descendants(package.knowledge, root) & declared
    entities.add(root)
    knowledge = declared - entities
    return sorted(entities, key=str), sorted(knowledge, key=str), root


def term_for(shapes_graph, iri):
    """A term that is valid IN THE SHAPES FILE.

    The value is written into shacl.ttl, and knowledge.ttl binds different
    prefixes for the same namespaces -- `default1:` there against
    `iffBaseKnowledge:` here. Offering the knowledge file's spelling would write
    an undefined prefix into the shapes file and break it on the next parse.
    Where the shapes file binds no prefix at all, a full IRI is always valid.
    """
    try:
        prefix, _, name = shapes_graph.namespace_manager.compute_qname(
            str(iri), generate=False)
        return f'{prefix}:{name}'
    except Exception:
        return f'<{iri}>'


def _as_choice(package, cls, note=''):
    return {'value': term_for(package.shapes, cls),
            'label': local(cls),
            'detail': note or str(cls)}


def choices_for(package, path_chain, parameter):
    """Candidate values for one parameter, or [] when a free value is right.

    Returns (choices, note). The note explains an EMPTY list, because "no
    suggestions" and "suggestions unavailable" are different situations and a
    picker that silently offers nothing cannot tell you which you are in.
    """
    if parameter == 'sh:nodeKind':
        return [{'value': kind, 'label': kind, 'detail': ''}
                for kind in NODE_KINDS], ''

    if parameter == 'sh:datatype':
        return [{'value': name, 'label': name, 'detail': ''}
                for name in COMMON_DATATYPES], ''

    if parameter != 'sh:class':
        return [], ''

    entities, knowledge, root = classify_classes(package)
    if root is None:
        return [], ('no entity root: the ontology has no class every '
                    'sh:targetClass descends from, and semforge.yaml declares '
                    'no entityRoot. Add one to get class suggestions.')

    slot = path_chain[-1] if path_chain else ''
    slot_iri = slot.strip('<>')
    is_object = slot_iri.endswith('hasObject') or slot_iri == OBJECT_PATH
    is_value = slot_iri.endswith('hasValue') or slot_iri == VALUE_PATH

    if is_object:
        return ([_as_choice(package, c, f'entity type (under {local(root)})')
                 for c in entities],
                '' if entities else 'no entity classes below ' + local(root))
    if is_value:
        return ([_as_choice(package, c, 'vocabulary class') for c in knowledge],
                '' if knowledge else 'no non-entity classes in the ontology')

    # Not in a value slot: the constraint is on the attribute node itself, where
    # sh:class is unusual. Offer everything and say so.
    return ([_as_choice(package, c) for c in entities + knowledge],
            'not a value slot -- both entity and vocabulary classes offered')
