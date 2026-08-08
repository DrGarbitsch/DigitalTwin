#
# Copyright (c) 2022 Intel Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
End-to-end extractor coverage for the SHACL logical connectives.

Before this was supported, a shape using sh:and / sh:not / sh:xone produced
ZERO constraints and no error -- it was accepted and silently never validated.
These tests exist mainly to keep that from regressing, so they assert both that
the connectives are extracted AND that each one reaches the circuit.
"""

import os
import tempfile

import rdflib
import pytest

import lib.shacl_properties_to_sql as props
from shacl_normalization import wrap_property_or


SHAPES = """
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix iff: <https://industry-fusion.com/types/v0.9/> .

iff:ConnectiveShape
    a sh:NodeShape ;
    sh:targetClass iff:machine ;

    sh:property [
        sh:path iff:plainState ;
        sh:property [ sh:path <https://uri.etsi.org/ngsi-ld/hasValue> ;
                      sh:minInclusive 10 ] ;
    ] ;

    sh:property [
        sh:path iff:andState ;
        sh:and (
            [ sh:property [ sh:path <https://uri.etsi.org/ngsi-ld/hasValue> ;
                            sh:minInclusive 5 ] ]
            [ sh:property [ sh:path <https://uri.etsi.org/ngsi-ld/hasValue> ;
                            sh:maxInclusive 50 ] ]
        ) ;
    ] ;

    sh:property [
        sh:path iff:notState ;
        sh:not [ sh:property [ sh:path <https://uri.etsi.org/ngsi-ld/hasValue> ;
                               sh:in ( "FORBIDDEN" ) ] ] ;
    ] ;

    sh:property [
        sh:path iff:xoneState ;
        sh:xone (
            [ sh:property [ sh:path <https://uri.etsi.org/ngsi-ld/hasValue> ;
                            sh:minInclusive 100 ] ]
            [ sh:property [ sh:path <https://uri.etsi.org/ngsi-ld/hasValue> ;
                            sh:maxInclusive 10 ] ]
        ) ;
    ] .
"""

KNOWLEDGE = """
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix iff: <https://industry-fusion.com/types/v0.9/> .
iff:machine a rdfs:Class .
"""

PREFIXES = {
    'sh': rdflib.Namespace('http://www.w3.org/ns/shacl#'),
    'rdfs': rdflib.Namespace('http://www.w3.org/2000/01/rdf-schema#'),
    'rdf': rdflib.Namespace('http://www.w3.org/1999/02/22-rdf-syntax-ns#'),
    'ngsi-ld': rdflib.Namespace('https://uri.etsi.org/ngsi-ld/'),
    'iff': rdflib.Namespace('https://industry-fusion.com/types/v0.9/'),
    'base': rdflib.Namespace('https://industry-fusion.com/base/v0.9/'),
}


@pytest.fixture(scope='module')
def extracted(tmp_path_factory):
    """Normalise the shapes the way the build does, then extract."""
    tmp = tmp_path_factory.mktemp('connectives')
    shapes, knowledge = tmp / 'shacl.ttl', tmp / 'knowledge.ttl'
    shapes.write_text(SHAPES)
    knowledge.write_text(KNOWLEDGE)

    graph = rdflib.Graph()
    graph.parse(str(shapes))
    wrap_property_or(graph)
    normalized = tmp / 'shacl_normalized.ttl'
    graph.serialize(destination=str(normalized), format='turtle')

    cwd = os.getcwd()
    os.chdir(tempfile.mkdtemp())          # translate() writes into ./output
    try:
        _, (_, _, _, _, postgres) = props.translate(
            str(normalized), str(knowledge), PREFIXES)
    finally:
        os.chdir(cwd)
    return postgres


@pytest.mark.parametrize('operation', ['AND', 'XONE', 'NOT'])
def test_connective_reaches_the_circuit(extracted, operation):
    """Each connective becomes an edge in the constraint combination table."""
    assert f"'{operation}'" in extracted, \
        f'sh:{operation.lower()} produced no {operation} edge -- the shape ' \
        f'would be silently unvalidated'


@pytest.mark.parametrize('path', ['plainState', 'andState', 'notState', 'xoneState'])
def test_every_property_yields_constraints(extracted, path):
    """
    No shape may be silently dropped.

    A property that extracts to nothing is worse than an error: validation
    reports conformant for something it never checked.
    """
    assert path in extracted, f'{path} produced no constraint rows'


def test_not_is_never_published_directly(extracted):
    """
    NOT must own a circuit node even with a single member.

    OR/AND/XONE at arity 1 reduce to 'violated iff the member violated', so
    publishing the member directly is equivalent. NOT does not reduce that way
    -- publishing directly would emit the inner verdict instead of its negation.
    """
    assert "'NOT'" in extracted


def test_connective_operation_mapping():
    sh = rdflib.Namespace('http://www.w3.org/ns/shacl#')
    assert props.connective_operation(sh['or']) == 'OR'
    assert props.connective_operation(sh['and']) == 'AND'
    assert props.connective_operation(sh.xone) == 'XONE'
    assert props.connective_operation(sh['not']) == 'NOT'
    assert props.connective_operation(None) == 'OR'
