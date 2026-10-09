"""Add attribute on an entity that already has it: another instance.

An attribute is (entity, name, datasetId), so adding one the entity already
carries is not a mistake -- it is another instance, and the question is only
under which datasetId. The dialog asks for it every time (empty: the default
instance), and only a datasetId the attribute already has is refused.
"""

import json
import os
import shutil
import subprocess

import pytest

from semforge.cooked.examples import add_attribute
from semforge.errors import PackageError
from semforge.package import load

STRENGTH = 'iffBaseEntities:hasStrength'


@pytest.fixture
def kms(tmp_path, corpus_path):
    target = tmp_path / 'kms'
    shutil.copytree(corpus_path, target, symlinks=False,
                    ignore=shutil.ignore_patterns('.semforge'))
    return target


def _strength(kms):
    document = json.load(open(kms / 'model-instance.jsonld'))
    entity = next(e for e in document if e.get('id') == 'urn:filter:1')
    value = entity[STRENGTH]
    return value if isinstance(value, list) else [value]


def test_another_datasetid_adds_an_instance(kms):
    before = _strength(kms)
    path, kind = add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=0.7,
                               datasetId='urn:sensor:second')
    after = _strength(kms)
    assert after[:len(before)] == before, 'the existing instances stay as they were'
    assert after[-1] == {'type': kind, 'value': 0.7, 'datasetId': 'urn:sensor:second'}


def test_the_kind_is_the_one_already_written(kms):
    _, kind = add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=1,
                            kind='Relationship', datasetId='urn:sensor:x')
    assert kind == _strength(kms)[0]['type'] == 'Property'


def test_the_same_datasetid_is_refused_and_nothing_written(kms):
    add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=0.7, datasetId='urn:sensor:b')
    text = open(kms / 'model-instance.jsonld').read()
    with pytest.raises(PackageError, match='with datasetId urn:sensor:b'):
        add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=0.8,
                      datasetId='urn:sensor:b')
    assert open(kms / 'model-instance.jsonld').read() == text


@pytest.mark.parametrize('bad, says', [('left', 'not an IRI'), ('@none', 'default instance')])
def test_a_datasetid_must_be_an_iri(kms, bad, says):
    with pytest.raises(PackageError, match=says):
        add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=1, datasetId=bad)


def test_a_new_attribute_with_a_datasetid_carries_it(kms):
    document = json.load(open(kms / 'model-instance.jsonld'))
    entity = next(e for e in document if e.get('id') == 'urn:filter:1')
    entity.pop(STRENGTH)
    json.dump(document, open(kms / 'model-instance.jsonld', 'w'), indent=2)
    add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=1, datasetId='urn:sensor:a')
    assert _strength(kms) == [{'type': 'Property', 'value': 1, 'datasetId': 'urn:sensor:a'}]


def test_an_empty_datasetid_is_the_default_instance(kms):
    document = json.load(open(kms / 'model-instance.jsonld'))
    entity = next(e for e in document if e.get('id') == 'urn:filter:1')
    entity[STRENGTH] = dict(_strength(kms)[0], datasetId='urn:sensor:only')
    json.dump(document, open(kms / 'model-instance.jsonld', 'w'), indent=2)
    add_attribute(load(str(kms)), 'urn:filter:1', STRENGTH, value=0.5, datasetId='')
    assert 'datasetId' not in _strength(kms)[-1]


# --- the dialog ------------------------------------------------------------------------

DRIVE = os.path.join(os.path.dirname(__file__), '..', 'harness', 'drive.js')
SRC = os.path.join(os.path.dirname(__file__), '..', '..', 'vscode', 'src')
ATTRIBUTES = {'attributes': [{'term': 'e:hasStrength', 'kind': 'Property', 'constrained': True,
                              'domains': ['e:Filter'], 'comment': ''}]}


def _entity(children):
    return {'raw': {'kind': 'entity', 'entity': 'urn:filter:1', 'entityType': 'e:Filter',
                    'file': 'case.jsonld', 'label': 'urn:filter:1', 'children': children},
            'packageUri': 'file:///pkg/shacl.ttl'}


def _drive(tmp_path, node, inputs):
    executable = shutil.which('node')
    if executable is None:
        pytest.skip('node is not installed')
    for name in ('shacl.ttl', 'knowledge.ttl', 'model-instance.jsonld'):
        (tmp_path / name).write_text('')
    path = tmp_path / 'scenario.json'
    path.write_text(json.dumps({
        'command': 'semforge.addAttribute', 'node': node, 'pick': 'e:hasStrength',
        'inputs': inputs,
        'replies': {'semforge/attributes': ATTRIBUTES, 'semforge/valueChoices': {'choices': []},
                    'semforge/addAttribute': {'ok': True, 'kind': 'Property'}}}))
    out = subprocess.run([executable, DRIVE, str(tmp_path), os.path.join(SRC, 'extension.js'),
                          str(path)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-1500:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def _sent(seen):
    return [r['params'] for r in seen['requests'] if r['method'] == 'semforge/addAttribute']


def test_a_new_attribute_asks_and_empty_is_the_default(tmp_path):
    seen = _drive(tmp_path, _entity([]), ['', '0.5'])
    asked = seen['inputs'][0]
    assert asked['title'] == 'e:hasStrength on urn:filter:1: datasetId'
    assert asked['value'] == '' and 'Empty for the default instance' in asked['prompt']
    assert _sent(seen)[0]['datasetId'] is None


def test_one_already_there_suggests_another_datasetid(tmp_path):
    present = {'kind': 'attribute', 'attributePath': ['e:hasStrength'], 'datasetId': '@none',
               'datasets': ['@none']}
    seen = _drive(tmp_path, _entity([present]), ['urn:sensor:b', '0.5'])
    asked = seen['inputs'][0]
    assert asked['value'] == 'urn:filter:1:hasStrength:2'
    assert 'It has 1 instance(s) already (default)' in asked['prompt']
    assert _sent(seen)[0]['datasetId'] == 'urn:sensor:b'


def test_cancelling_the_datasetid_adds_nothing(tmp_path):
    seen = _drive(tmp_path, _entity([]), [])
    assert _sent(seen) == [] and len(seen['inputs']) == 1
