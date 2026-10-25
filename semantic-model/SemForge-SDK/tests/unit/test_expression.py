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

"""A value that is more than one set of conditions: read, said, edited.

One plain value stays one plain value -- the picker edits it, and nothing here
is offered unless asked for. A value that already is an expression is read as
a tree; every edit is one rewrite of the value layer, read back before kept.
"""

import shutil

import pytest
from rdflib import Graph, URIRef
from rdflib.namespace import SH

from semforge.cooked.expression import (Leaf, Op, describe, edit, normalize, normalize_root,
                                        read_layer)
from semforge.errors import PackageError

FILTER = 'https://industryfusion.github.io/contexts/example/v0/base_shacl/FilterShape'
STRENGTH = ['iffBaseEntities:hasStrength']
EXTRA = '''
<https://example.org/ExprShape> a sh:NodeShape ;
    sh:targetClass iffBaseEntities:Filter ;
    sh:property [ sh:path iffBaseEntities:hasNoteX ; sh:minCount 0 ; sh:maxCount 1 ;
                  sh:property [ sh:path ngsild:hasValue ; sh:minCount 1 ; sh:maxCount 1 ;
                                sh:datatype xsd:string ] ] ,
                [ sh:path iffBaseEntities:hasNodeX ; sh:minCount 0 ; sh:maxCount 1 ;
                  sh:property [ sh:path ngsild:hasValue ;
                                sh:or ( [ sh:node <https://example.org/Other> ]
                                        [ sh:datatype xsd:string ] ) ] ] ,
                [ sh:path iffBaseEntities:hasCommentX ; sh:minCount 0 ; sh:maxCount 1 ;
                  sh:property [ sh:path ngsild:hasValue ;
                                sh:or ( [ sh:datatype xsd:string ]   # text
                                        [ sh:datatype xsd:integer ] ) ] ] .
'''
EXPR = 'https://example.org/ExprShape'
KNOWLEDGE = ''.join(
    f'\n<https://industryfusion.github.io/contexts/example/v0/base_entities/{name}> '
    f'a <http://www.w3.org/2002/07/owl#ObjectProperty> ; '
    f'<http://www.w3.org/2000/01/rdf-schema#domain> '
    f'<https://industryfusion.github.io/contexts/example/v0/base_entities/Filter> .\n'
    for name in ('hasNoteX', 'hasNodeX', 'hasCommentX'))


@pytest.fixture
def root(tmp_path, corpus):
    root = tmp_path / 'pkg'
    shutil.copytree(corpus.path, root, ignore=shutil.ignore_patterns('.semforge'))
    shapes = root / 'shacl.ttl'
    shapes.write_text(shapes.read_text() + EXTRA)
    knowledge = root / 'knowledge.ttl'
    knowledge.write_text(knowledge.read_text() + KNOWLEDGE)
    return root


def _layer(root, shape=FILTER, chain=STRENGTH):
    from semforge.package import load

    return read_layer(load(str(root)), (root / 'shacl.ttl').read_text(), shape, chain)


def _edit(root, action, shape=FILTER, chain=STRENGTH):
    from semforge.package import load

    return edit(load(str(root)), shape, chain, action)


def _row(root, label):
    from semforge.cooked.typepage import PENDING, build_type_page
    from semforge.package import load

    page = build_type_page(load(str(root)), 'iffBaseEntities:Filter', PENDING)
    return next(r for r in page['attributes'] if r['label'] == label)


# --- the shape of a tree -----------------------------------------------------------------

def test_an_empty_set_is_anything_and_only_an_all_of_may_drop_it():
    text = Leaf((('sh:datatype', 'xsd:string'),))
    assert normalize(Op('and', (Leaf(), text))) == text
    assert normalize(Op('or', (Leaf(), text))) == Op('or', (Leaf(), text))
    assert normalize(Op('or', (text,))) == text
    assert normalize(Op('not', (text,))) == Op('not', (text,))


def test_top_level_conditions_join_the_layers_own_unless_they_clash():
    double = Leaf((('sh:datatype', 'xsd:double'),))
    bounded = Leaf((('sh:maxInclusive', '100'),))
    integer = Leaf((('sh:datatype', 'xsd:integer'),))
    root = normalize_root(Op('and', (double, bounded, integer)))
    assert root.children[0] == Leaf((('sh:datatype', 'xsd:double'), ('sh:maxInclusive', '100')))
    assert root.children[1:] == (integer,)


# --- reading ---------------------------------------------------------------------------------

def test_the_kms_number_is_read_as_an_expression(root):
    layer = _layer(root)
    assert layer.complex and layer.editable
    assert describe(layer) == '0 – 100 · any of: number (double) | number (integer)'


def test_one_plain_value_is_not_an_expression(root):
    layer = _layer(root, EXPR, ['iffBaseEntities:hasNoteX'])
    assert not layer.complex
    row = _row(root, 'hasNoteX')
    assert row['expression'] is None and row['combinable'] and row['valueEditable']
    # The kms number keeps its plain words on the page, and is an expression.
    strength = _row(root, 'hasStrength')
    assert strength['expression'] and not strength['combinable']
    assert strength['value'] == 'number · 0 – 100'


def test_a_branch_it_cannot_say_is_kept_and_the_rest_edited(root):
    chain = ['iffBaseEntities:hasNodeX']
    layer = _layer(root, EXPR, chain)
    assert layer.editable
    branches = layer.root.children[1].children
    assert branches[0].text == '[ sh:node <https://example.org/Other> ]'
    _edit(root, {'op': 'add', 'node': [1], 'parameter': 'sh:datatype', 'value': 'xsd:integer'},
          EXPR, chain)
    after = _layer(root, EXPR, chain).root.children[1].children
    assert after[0] == branches[0] and len(after) == 3


def test_a_comment_inside_keeps_it_read_only(root):
    layer = _layer(root, EXPR, ['iffBaseEntities:hasCommentX'])
    assert layer.complex and not layer.editable and 'comment' in layer.reason
    assert _row(root, 'hasCommentX')['valueEditable'] is False
    with pytest.raises(PackageError, match='comment'):
        _edit(root, {'op': 'remove', 'node': [1, 0]}, EXPR, ['iffBaseEntities:hasCommentX'])


# --- editing ---------------------------------------------------------------------------------

def test_branches_are_added_and_removed_and_one_left_is_a_plain_value_again(root):
    _edit(root, {'op': 'add', 'node': [1], 'parameter': 'sh:datatype', 'value': 'xsd:decimal'})
    assert describe(_layer(root)).endswith('| number (decimal)')
    _edit(root, {'op': 'remove', 'node': [1, 2]})
    _edit(root, {'op': 'remove', 'node': [1, 1]})
    layer = _layer(root)
    assert not layer.complex
    assert describe(layer) == 'number (double) · 0 – 100'
    assert _row(root, 'hasStrength')['expression'] is None


def test_combine_turns_one_value_into_any_of(root):
    chain = ['iffBaseEntities:hasNoteX']
    _edit(root, {'op': 'combine', 'connective': 'or', 'parameter': 'sh:datatype',
                 'value': 'xsd:integer'}, EXPR, chain)
    layer = _layer(root, EXPR, chain)
    assert describe(layer) == 'any of: text | number (integer)'
    row = _row(root, 'hasNoteX')
    assert row['expression'] and not row['combinable']


def test_combine_needs_a_value_to_combine_with(root, tmp_path):
    from semforge.package import load

    shapes = root / 'shacl.ttl'
    shapes.write_text(shapes.read_text().replace(
        'sh:maxCount 1 ;\n                                sh:datatype xsd:string ] ] ,',
        'sh:maxCount 1 ] ] ,'))
    with pytest.raises(PackageError, match='any value so far'):
        edit(load(str(root)), EXPR, ['iffBaseEntities:hasNoteX'],
             {'op': 'combine', 'connective': 'or', 'parameter': 'sh:datatype',
              'value': 'xsd:integer'})


def test_wrap_retype_and_unwrap(root):
    _edit(root, {'op': 'retype', 'node': [1], 'connective': 'xone'})
    assert 'exactly one of' in describe(_layer(root))
    _edit(root, {'op': 'wrap', 'node': [1, 0], 'connective': 'not'})
    assert 'not (number (double))' in describe(_layer(root))
    _edit(root, {'op': 'unwrap', 'node': [1, 0]})
    assert describe(_layer(root)) == '0 – 100 · exactly one of: number (double) | number (integer)'


def test_set_and_unset_a_condition_of_a_branch(root):
    _edit(root, {'op': 'set', 'node': [1, 1], 'parameter': 'sh:maxInclusive', 'value': '10'})
    assert 'number (integer) · ≤ 10' in describe(_layer(root))
    _edit(root, {'op': 'unset', 'node': [1, 1], 'parameter': 'sh:maxInclusive'})
    assert describe(_layer(root)) == '0 – 100 · any of: number (double) | number (integer)'


def test_what_is_written_validates_as_meant(root):
    """'n/a', or a number from 0 to 100: both pass; 150 and "other" do not."""
    import pyshacl

    from semforge.package import load
    from semforge.validate.shapes import subgraph_for

    _edit(root, {'op': 'combine', 'connective': 'or', 'parameter': 'sh:hasValue',
                 'value': '"n/a"'})
    shapes = subgraph_for(load(str(root)).shapes, [URIRef(FILTER)])

    def fails(value):
        data = Graph().parse(data=f'''
            @prefix ngsild: <https://uri.etsi.org/ngsi-ld/> .
            @prefix e: <https://industryfusion.github.io/contexts/example/v0/base_entities/> .
            <urn:f:1> a e:Filter ; e:hasStrength [ ngsild:hasValue {value} ] .''', format='turtle')
        _, report, _ = pyshacl.validate(data, shacl_graph=shapes)
        return any('hasStrength' in str(report.value(r, SH.resultPath)) or
                   'hasValue' in str(report.value(r, SH.resultPath))
                   for r in report.objects(None, SH.result)
                   if str(report.value(r, SH.focusNode)) != 'urn:f:1' or
                   'hasStrength' in str(report.value(r, SH.resultPath)))

    assert not fails('"50"^^<http://www.w3.org/2001/XMLSchema#double>')
    assert not fails('"n/a"')
    assert fails('"150"^^<http://www.w3.org/2001/XMLSchema#double>')
    assert fails('"other"')


def test_the_editor_lists_every_part_indented():
    import json
    import os
    import subprocess

    node = shutil.which('node')
    if node is None:
        pytest.skip('node is not installed')
    sdk = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    out = subprocess.run([node, os.path.join(sdk, 'tests', 'harness', 'expression.js'),
                          os.path.join(sdk, 'vscode', 'src')],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-1500:]
    full, empty = json.loads(out.stdout.strip().splitlines()[-1])
    assert [i['address'] for i in full] == [[0], [1], [1, 0], [1, 1], [1, 1, 0], [1, 2]]
    assert full[0]['description'] == 'and always'
    assert full[4]['label'].startswith('  $(symbol-field)')
    assert full[5]['description'].startswith('kept as written')
    # No conditions of its own: the value starts at its connective.
    assert [i['address'] for i in empty] == [[1], [1, 0], [1, 1]]
