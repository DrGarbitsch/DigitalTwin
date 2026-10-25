#
# Copyright (c) 2026 IndustryFusion Foundation
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

"""The forms a value may take: a scalar, a list, or a choice of them.

The OPC UA tools write every Variable as `sh:or ( scalar | list )` -- its
ValueRank decides which an instance may be -- and as `ngsi-ld:`, not `ngsild:`.
The cooked views showed "any value" with the sh:or verbatim, and every
relationship's `ngsi-ld:hasObject` as a sub-attribute named hasObject.
"""

import shutil

import pytest

from semforge.cooked.payloads import alternatives, describe, list_form
from semforge.cooked.typepage import _words
from semforge.ngsild.kinds import SPELLINGS, payload_of

PREFIXES = [('sh', 'http://www.w3.org/ns/shacl#'), ('xsd', 'http://www.w3.org/2001/XMLSchema#'),
            ('rdf', 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'),
            ('ngsi-ld', 'https://uri.etsi.org/ngsi-ld/'), ('ex', 'https://example.org/')]

LIST_OF = ('( [ sh:nodeKind sh:BlankNode ; sh:property [ {member} ; '
           'sh:path ( [ sh:zeroOrMorePath rdf:rest ] rdf:first ) ] ] [ sh:hasValue () ] )')


def scalar_or_list(member, scalar_extra='sh:nodeKind sh:Literal ;'):
    return (f'( [ sh:property [ {member} ; sh:maxCount 1 ; sh:minCount 1 ; {scalar_extra} '
            f'sh:path ngsi-ld:hasValue ] ] '
            f'[ sh:property [ sh:maxCount 1 ; sh:minCount 1 ; '
            f'sh:or {LIST_OF.format(member=member)} ; sh:path ngsi-ld:hasValueList ] ] )')


@pytest.mark.parametrize('text, name', [
    ('ngsild:hasValue', 'hasValue'), ('ngsi-ld:hasObject', 'hasObject'),
    ('<https://uri.etsi.org/ngsi-ld/hasValueList>', 'hasValueList'),
    ('ex:hasValue', ''), ('ngsi-ld:hasCategory', ''), ('', ''),
])
def test_every_spelling_of_a_payload_is_one(text, name):
    assert payload_of(text) == name
    assert (text in SPELLINGS) is bool(name)


@pytest.mark.parametrize('member, said', [
    ('sh:datatype xsd:string', 'text, or a list of them (possibly empty)'),
    ('sh:datatype xsd:double', 'number, or a list of them (possibly empty)'),
    ('sh:class ex:PortDirectionEnum', 'one of PortDirectionEnum, or a list of them (possibly empty)'),
])
def test_a_scalar_or_a_list_is_read_and_said(member, said):
    found = alternatives(scalar_or_list(member), PREFIXES)
    assert [a.kind for a in found] == ['Property', 'ListProperty']
    assert [a.payload for a in found] == ['hasValue', 'hasValueList']
    assert found[1].may_be_empty and not found[0].may_be_empty
    assert describe(found, _words) == said


def test_a_list_whose_members_differ_says_both():
    text = ('( [ sh:property [ sh:datatype xsd:string ; sh:path ngsi-ld:hasValue ] ] '
            '[ sh:property [ sh:path ngsi-ld:hasValueList ; sh:nodeKind sh:BlankNode ; '
            'sh:property [ sh:datatype xsd:double ; '
            'sh:path ( [ sh:zeroOrMorePath rdf:rest ] rdf:first ) ] ] ] )')
    found = alternatives(text, PREFIXES)
    assert not found[1].may_be_empty
    assert describe(found, _words) == 'text, or a list of: number'


def test_the_value_of_a_list_payload_is_read():
    assert list_form(LIST_OF.format(member='sh:datatype xsd:string'), PREFIXES) == \
        ((('sh:datatype', 'xsd:string'),), True)


@pytest.mark.parametrize('text', [
    # A choice of datatypes, not of value layers: the type page says "number".
    '( [ sh:datatype xsd:double ] [ sh:datatype xsd:integer ] )',
    # Not a payload.
    '( [ sh:property [ sh:path ex:other ; sh:datatype xsd:string ] ] )',
    # Something this does not say in words, on the value.
    '( [ sh:property [ sh:path ngsi-ld:hasValue ; sh:node ex:Shape ] ] )',
    # A value layer with more beside it.
    '( [ sh:property [ sh:path ngsi-ld:hasValue ] ; sh:minCount 1 ] )',
    # A list whose members are reached some other way.
    '( [ sh:property [ sh:path ngsi-ld:hasValueList ; sh:nodeKind sh:BlankNode ; '
    'sh:property [ sh:path rdf:first ; sh:datatype xsd:string ] ] ] )',
    'not turtle at all (',
])
def test_anything_else_is_not_guessed_at(text):
    assert alternatives(text, PREFIXES) is None


SHAPES = '''
<https://example.org/FormsShape> a sh:NodeShape ;
    sh:targetClass iffBaseEntities:Filter ;
    sh:property [ sh:path iffBaseEntities:hasCategoryX ; sh:minCount 0 ; sh:maxCount 1 ;
                  sh:nodeKind sh:BlankNode ; sh:or {forms} ] ,
                [ sh:path iffBaseEntities:hasLinkX ; sh:minCount 0 ; sh:maxCount 1 ;
                  sh:property [ sh:path ngsi-ld:hasObject ; sh:class iffBaseEntities:Filter ] ] ,
                [ sh:path iffBaseEntities:hasListX ;
                  sh:property [ sh:path ngsi-ld:hasValueList ; sh:minCount 1 ; sh:maxCount 1 ;
                                sh:or {listed} ] ] .
'''


def test_the_type_page_says_the_forms(tmp_path, corpus):
    from semforge.cooked.tree import build_tree
    from semforge.cooked.typepage import PENDING, build_type_page
    from semforge.package import load

    root = tmp_path / 'pkg'
    shutil.copytree(corpus.path, root, ignore=shutil.ignore_patterns('.semforge'))
    shapes = root / 'shacl.ttl'
    shapes.write_text('@prefix ngsi-ld: <https://uri.etsi.org/ngsi-ld/> .\n' +
                      shapes.read_text() + SHAPES.format(
                          forms=scalar_or_list('sh:datatype xsd:string'),
                          listed=LIST_OF.format(member='sh:datatype xsd:double')))
    package = load(str(root))
    page = build_type_page(package, 'iffBaseEntities:Filter', PENDING)
    rows = {r['label']: r for r in page['attributes']}

    category = rows['hasCategoryX']
    assert category['kinds'] == ['Property', 'ListProperty']
    assert category['value'] == 'text, or a list of them (possibly empty)'
    assert not any(v.startswith('sh:or') for v in category['verbatim'])
    assert [a['payload'] for a in category['alternatives']] == ['hasValue', 'hasValueList']

    # ngsi-ld:hasObject is the relationship's value, not a sub-attribute.
    link = rows['hasLinkX']
    assert link['kind'] == 'Relationship' and link['value'] == '→ Filter'
    assert 'hasObject' not in rows

    listed = rows['hasListX']
    assert listed['kinds'] == ['ListProperty']
    assert listed['value'] == 'a list of: number (possibly empty)'

    # And the constraints tree names the sh:or by what it says.
    def nodes(node):
        yield node
        for child in node.children:
            yield from nodes(child)
    said = [n for top in build_tree(package) for n in nodes(top)
            if n.kind == 'raw' and n.label.startswith('value: ')]
    assert {n.label for n in said} >= {'value: Property or ListProperty', 'value: ListProperty'}
