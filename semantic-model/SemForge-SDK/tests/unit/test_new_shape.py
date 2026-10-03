"""New shape…: a node shape with one target, from the editor.

No command wrote a shape, so a new entity type had no way to get one --
and its type page's + Attribute had nowhere to write. `add_shape` writes
`ns:Name a sh:NodeShape ; sh:target… X .` for an entity type, one entity,
whatever has an attribute, or whatever a relationship points at.
"""

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SH

from semforge.cooked.constrain import add_attribute_constraint, own_shape
from semforge.cooked.knowledge import add_attribute_term
from semforge.cooked.shapes import add_shape, build_shapes
from semforge.cooked.typepage import build_type_page
from semforge.errors import PackageError
from semforge.package import load
from semforge.package.scaffold import create_package
from semforge.validate import validate_package


@pytest.fixture
def fresh(tmp_path):
    """A scaffolded package with a new entity type that has no shape."""
    root = str(tmp_path / 'my-model')
    create_package(root)
    package = load(root)
    entity = next(str(c) for c in package.knowledge.subjects() if str(c).endswith('/Entity'))
    space = entity[:-len('Entity')]
    with open(f'{root}/knowledge.ttl', 'a') as handle:
        handle.write(f'\n<{space}Pump> a <http://www.w3.org/2002/07/owl#Class> ;\n'
                     f'    <http://www.w3.org/2000/01/rdf-schema#subClassOf> <{entity}> .\n')
    return root, space


def _graph(root):
    return Graph().parse(f'{root}/shacl.ttl', format='turtle')


@pytest.mark.parametrize('kind, target, predicate', [
    ('class', 'Pump', SH.targetClass),
    ('node', 'urn:my-model:machine:1', SH.targetNode),
    ('subjectsOf', 'hasTemperature', SH.targetSubjectsOf),
    ('objectsOf', 'ngsild:hasObject', SH.targetObjectsOf),
])
def test_each_target_kind_is_written(fresh, kind, target, predicate):
    root, _ = fresh
    with open(f'{root}/shacl.ttl') as handle:
        before = handle.read()
    made = add_shape(load(root), 'NewShape', kind, target)
    with open(f'{root}/shacl.ttl') as handle:
        after = handle.read()
    assert after.startswith(before), 'appended; the rest of the file untouched'
    assert (URIRef(made['iri']), predicate, None) in _graph(root)
    assert made['iri'].rsplit('/', 1)[-1] == 'NewShape'
    # In the namespace the package's other shapes use.
    assert made['iri'].startswith(
        next(str(s) for s in _graph(root).subjects(SH.targetClass, None)).rsplit('/', 1)[0])
    assert 'NewShape' in [r['label'].split(':')[-1] for r in build_shapes(load(root))]
    assert not validate_package(load(root), strict=False).violations


@pytest.mark.parametrize('name, kind, target, said', [
    ('MachineShape', 'class', 'Machine', 'already exists'),
    ('PumpShape', 'class', 'Nope', 'not an entity type'),
    ('PumpShape', 'subjectsOf', 'hasNothing', 'not an attribute'),
    ('OneShape', 'node', 'not an iri', 'not an IRI'),
    ('1Shape', 'class', 'Pump', 'not a usable name'),
    ('PumpShape', 'or', 'Pump', 'not a target'),
])
def test_what_it_cannot_write_is_refused(fresh, name, kind, target, said):
    root, _ = fresh
    with pytest.raises(PackageError, match=said):
        add_shape(load(root), name, kind, target)


def test_a_new_type_gets_its_shape_and_then_its_attributes(fresh):
    """The type page's "Create its shape", then + Attribute."""
    root, space = fresh
    pump = space + 'Pump'
    assert not build_type_page(load(root), pump)['ownShape']
    made = add_shape(load(root), 'PumpShape', 'class', pump)
    assert own_shape(load(root), pump) == made['iri']
    assert build_type_page(load(root), pump)['ownShape'] == made['iri']
    add_attribute_term(load(root), 'hasFlow', 'Property', pump)
    add_attribute_constraint(load(root), made['iri'], 'hasFlow', required=True,
                             datatype='xsd:double')
    rows = build_type_page(load(root), pump)['attributes']
    assert [r['label'] for r in rows] == ['hasFlow']
