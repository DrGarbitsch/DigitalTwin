"""Adding an attribute to a shape: the constraint, both layers, at once.

The one way an attribute reached a shape before was a side effect -- "go to
the rule" on an attribute with none wrote a bare `sh:path` stub, which the
capability check then reports as compiling to nothing. That is right for a
jump, which must not decide anything, and wrong for an author who has said
"this type has this attribute": they have decided, and the shape should say so.

What gets written is the NGSI-LD two-layer encoding the scaffold teaches:

    sh:property [ sh:path ex:hasState ;            the attribute is there,
        sh:minCount 1 ; sh:maxCount 1 ;            once,
        sh:nodeKind sh:BlankNode ;                 as an attribute node,
        sh:property [ sh:path ngsild:hasValue ;    and its value is there,
            sh:minCount 1 ; sh:maxCount 1 ;        once,
            sh:nodeKind sh:IRI ;                   and is what was asked for
            sh:class ex:MachineState ] ]

The kind decides the inner path -- a Relationship's payload is `hasObject`, a
Property's `hasValue` -- and is read from the knowledge, never asked: that is
what the knowledge's `rdfs:range` is for. What the value must BE is asked,
because the knowledge deliberately does not say: `sh:class` is the shapes'
business (see choices.nesting).

The refusals are the point as much as the write:

  * an undeclared attribute -- declare it in the knowledge first, or nothing
    else (pickers, references, the Knowledge view) will ever know of it;
  * one the knowledge gives to another type -- the shape would demand it of
    entities that never carry it, and every one of them would fail;
  * a sub-attribute -- it hangs off an attribute node, not off the entity;
  * one already constrained here -- edit it instead;
  * one constrained by a supertype's shape -- SHACL conjoins, so a second
    declaration is an override, and that has its own command, which says
    whether the change tightens or can never take effect.
"""

from rdflib import URIRef
from rdflib.namespace import SH, XSD

from ..errors import PackageError
from ..rdfio import property_blocks
from ..validate.normalise import curie, local
from .choices import (NGSILD, _ancestor_chain, attribute_terms,
                      classify_classes)

# The kind decides where the payload hangs, exactly as ngsild.build's
# PAYLOAD_KEY decides the JSON key.
PAYLOAD_PATH = {
    'Property': NGSILD + 'hasValue',
    'GeoProperty': NGSILD + 'hasValue',
    'Relationship': NGSILD + 'hasObject',
    'JsonProperty': NGSILD + 'hasJSON',
    'ListProperty': NGSILD + 'hasValueList',
}


def _attribute(package, attribute):
    wanted = str(attribute)
    for entry in attribute_terms(package):
        if wanted in (entry.iri, entry.term, entry.label):
            return entry
    raise PackageError(
        f'{attribute} is not declared in the knowledge. Declare it there '
        f'first: an attribute only the shapes know of is one no picker '
        f'offers and no example is checked against.')


def _shape_targets(package, shape):
    return [t for t in package.shapes.objects(URIRef(shape), SH.targetClass)
            if isinstance(t, URIRef)]


def _family(package, classes):
    found = set()
    for cls in classes:
        found.update(str(c) for c in _ancestor_chain(package.knowledge, cls))
    return found


def _constrained_paths(package, shape):
    """The attribute IRIs a shape's own top-level sh:property groups name."""
    return {str(path)
            for group in package.shapes.objects(URIRef(shape), SH.property)
            for path in package.shapes.objects(group, SH.path)
            if isinstance(path, URIRef)}


def _inherited_constraints(package, shape):
    """{attribute IRI: the supertype shape that constrains it}."""
    from ..validate.shapes import node_shapes

    own = set(_shape_targets(package, shape))
    above = _family(package, own) - {str(t) for t in own}
    found = {}
    for other in node_shapes(package.shapes):
        if str(other) == str(shape):
            continue
        targets = {str(t) for t in _shape_targets(package, other)}
        if targets & above:
            for path in _constrained_paths(package, other):
                found.setdefault(path, str(other))
    return found


def own_shape(package, entity_type):
    """The node shape that targets this type itself, or None.

    Its OWN shape, not the nearest one: a new attribute of Filter belongs in
    FilterShape, and writing it into MachineShape because Filter inherits from
    Machine would demand it of every Cutter too. When a type has several shapes
    of its own -- a structural one and SPARQL rule shapes, say -- the one that
    already carries sh:property groups is the one attributes go in.
    """
    from ..validate.shapes import node_shapes
    from .choices import entity_types

    wanted = str(entity_type or '').strip('<>')
    if not wanted:
        return None
    # The type as the knowledge declares it -- term, IRI or local name -- so
    # the comparison is on IRIs and two namespaces' `Filter` stay two.
    iri = next((entry.iri for entry in entity_types(package)[0]
                if wanted in (entry.iri, entry.term, entry.label)), wanted)
    candidates = [shape for shape in node_shapes(package.shapes)
                  if iri in {str(t) for t in _shape_targets(package, shape)}]
    if not candidates:
        return None
    candidates.sort(key=lambda s: (-len(list(package.shapes.objects(s, SH.property))),
                                   str(s)))
    return str(candidates[0])


def attribute_options(package, shape):
    """What the add-attribute picker offers for this shape, and in what state.

    Every attribute the knowledge gives to the shape's target type or one of
    its supertypes, then the ones it gives to nobody (a package may simply not
    have said). Each says whether it can be added:

      * free       -- not constrained here or above
      * here       -- this shape already constrains it; edit it instead
      * inherited  -- a supertype's shape does; override it instead
    """
    targets = _shape_targets(package, shape)
    if not targets:
        raise PackageError(f'{shape} has no sh:targetClass, so no attribute '
                           f'belongs to it')
    family = _family(package, targets)
    here = _constrained_paths(package, shape)
    above = _inherited_constraints(package, shape)

    out = []
    for entry in attribute_terms(package):
        if not entry.ngsild or entry.parents or entry.carrier_kind:
            continue
        if entry.domain_iri and entry.domain_iri not in family:
            continue
        status, by = 'free', ''
        if entry.iri in here:
            status = 'here'
        elif entry.iri in above:
            status, by = 'inherited', curie(package.shapes, above[entry.iri])
        out.append({'iri': entry.iri, 'term': entry.term,
                    'label': entry.label, 'kind': entry.kind or 'Property',
                    'comment': entry.comment, 'domain': entry.domain,
                    'scoped': bool(entry.domain_iri), 'status': status,
                    'by': by})
    out.sort(key=lambda o: (o['status'] != 'free', not o['scoped'],
                            o['label'].lower()))
    return out


def _resolve(package, term):
    """A term from a picker (CURIE or IRI) as an IRI, or None."""
    if not term:
        return None
    text = str(term).strip().strip('<>')
    if '://' in text or text.startswith('urn:'):
        return URIRef(text)
    prefix, _, name = text.partition(':')
    for bound, namespace in package.shapes.namespaces():
        if bound == prefix:
            return URIRef(str(namespace) + name)
    from ..package.prefixes import canonical_map
    namespace = canonical_map(package.path).get(prefix)
    return URIRef(namespace + name) if namespace else None


def _value_layer(package, kind, datatype, value_class, name):
    """The inner layer's parameters, minus its sh:path, as (name, IRI) pairs."""
    pairs = [(SH.minCount, 1), (SH.maxCount, 1)]
    entities, vocabularies, _ = classify_classes(package)
    if kind == 'Relationship':
        if datatype:
            raise PackageError(f'{name} is a Relationship: its value is an '
                               f'entity, which has no datatype')
        pairs.append((SH.nodeKind, SH.IRI))
        if value_class:
            cls = _resolve(package, value_class)
            if cls not in entities:
                raise PackageError(
                    f'{value_class} is not an entity type, so no entity can '
                    f'be one -- a Relationship to it could never be satisfied')
            pairs.append((SH['class'], cls))
        return pairs

    if value_class and datatype:
        raise PackageError('a value is either a vocabulary term (a class) or '
                           'a literal (a datatype), not both')
    if value_class:
        if kind != 'Property':
            raise PackageError(f'a {kind} does not carry a vocabulary term')
        cls = _resolve(package, value_class)
        if cls in entities:
            raise PackageError(
                f'{value_class} is an entity type; pointing at an entity is '
                f'what a Relationship is for. Declare {name} with rdfs:range '
                f'ngsild:Relationship instead.')
        if cls not in vocabularies:
            raise PackageError(f'{value_class} is not a class the knowledge '
                               f'declares')
        # The value IS one of the vocabulary's individuals, so it arrives as an
        # IRI: {"@id": ...}. The nodeKind makes a string that merely spells the
        # name a violation that says so, rather than an sh:class failure that
        # reads as the wrong individual.
        pairs += [(SH.nodeKind, SH.IRI), (SH['class'], cls)]
    elif datatype:
        iri = _resolve(package, datatype)
        if iri is None or not str(iri).startswith(str(XSD)):
            raise PackageError(f'{datatype} is not an XML Schema datatype')
        pairs.append((SH.datatype, iri))
    return pairs


def add_attribute_constraint(package, shape, attribute, required=False,
                             datatype=None, value_class=None):
    """Add `attribute` to `shape` as a complete two-layer property shape.

    Returns {'file', 'line', 'shape', 'attribute', 'kind'}. The write is a text
    insertion into the shape's own statement, verified to parse before the
    file is replaced, so every comment around and inside the shape survives.
    """
    from .knowledge import _turtle_name
    from .tree import _write_verified
    from ..rdfio import add_property_constraint

    shape = str(shape)
    index = package.index('shapes')
    holder = index.file_for(URIRef(shape))
    if holder is None:
        raise PackageError(f'{shape} is not a statement in any shapes file')

    entry = _attribute(package, attribute)
    name = entry.label
    if entry.parents or entry.carrier_kind:
        raise PackageError(
            f'{name} is a sub-attribute: it hangs off an attribute node, not '
            f'off the entity, so it belongs inside the attribute that carries '
            f'it rather than on the shape')
    targets = _shape_targets(package, shape)
    if entry.domain_iri and entry.domain_iri not in _family(package, targets):
        raise PackageError(
            f'the knowledge gives {name} to {local(entry.domain_iri)}, not to '
            f'{", ".join(local(t) for t in targets) or "this shape"}. Required '
            f'here it would be demanded of entities that never carry it.')
    if entry.iri in _constrained_paths(package, shape):
        raise PackageError(f'{curie(package.shapes, shape)} already constrains '
                           f'{name}; edit that constraint instead')
    above = _inherited_constraints(package, shape)
    if entry.iri in above:
        raise PackageError(
            f'{curie(package.shapes, above[entry.iri])} already constrains '
            f'{name} for this type. SHACL conjoins, so declaring it again here '
            f'can only tighten it -- use "Declare on This Type" on the '
            f'inherited constraint, which says whether a change takes effect.')

    kind = entry.kind or 'Property'
    inner = _value_layer(package, kind, datatype, value_class, name)

    with open(holder, encoding='utf-8') as handle:
        text = handle.read()

    def term(node):
        if isinstance(node, int):
            return str(node)
        return _turtle_name(text, node)

    value_pairs = [(term(SH.path), term(URIRef(PAYLOAD_PATH[kind])))] + \
        [(term(p), term(v)) for p, v in inner]
    outer = [(term(SH.minCount), '1' if required else '0'),
             (term(SH.maxCount), '1'),
             (term(SH.nodeKind), term(SH.BlankNode)),
             (term(SH.property), value_pairs)]
    updated = add_property_constraint(
        holder, shape, term(URIRef(entry.iri)), outer, source=text)
    _write_verified(holder, updated)

    from ..rdfio import TurtleIndex
    block = TurtleIndex(updated).block_for(shape)
    line = None
    for group in property_blocks(updated, block):
        if group.path in (term(URIRef(entry.iri)), f'<{entry.iri}>'):
            line = updated.count('\n', 0, group.start) + 1
    return {'file': holder, 'line': line, 'shape': shape,
            'attribute': entry.iri, 'kind': kind}


def shape_targets(package, shape):
    """The target classes of a shape, as terms the model would write."""
    from .choices import model_term

    return [model_term(package, t) for t in _shape_targets(package, shape)]


__all__ = ['attribute_options', 'add_attribute_constraint', 'own_shape',
           'shape_targets', 'PAYLOAD_PATH']
